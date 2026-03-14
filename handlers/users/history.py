from aiogram import types
from loguru import logger
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from handlers.users.keyboards import get_start_keyboard
import os

async def show_user_bookings(callback: types.CallbackQuery, Database):
    """Показывает историю бронирований пользователя"""
    logger.info(f"User {callback.from_user.id} requested booking history")
    
    try:
        async with Database.pool.acquire() as conn:
            user = await conn.fetchrow(
                """
                SELECT id FROM users WHERE telegram_id::text = $1
                """,
                str(callback.from_user.id)
            )
            
            if not user:
                await callback.message.answer(
                    "❌ Пользователь не найден. Пожалуйста, перезапустите бота командой /start.",
                    reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                        [types.InlineKeyboardButton(text="Перезапустить", callback_data="back_to_start")]
                    ])
                )
                return
                
            bookings = await conn.fetch(
                """
                SELECT b.id, b.start_time, b.end_time, b.status,
                       c.model, c.number_plate, c.id as car_id,
                       (SELECT COUNT(*) FROM photos WHERE booking_id = b.id AND stage = 'before') as before_photos,
                       (SELECT COUNT(*) FROM photos WHERE booking_id = b.id AND stage = 'after') as after_photos
                FROM bookings b
                JOIN cars c ON b.car_id = c.id
                WHERE b.user_id = $1
                ORDER BY b.start_time DESC
                """,
                user['id']
            )
        

        if not bookings:
            message_text = "📋 <b>История бронирований</b>\n\n" \
                          "У вас пока нет бронирований."
            keyboard = get_start_keyboard()

            has_error = False
            if callback.message.photo:
                try:
                    await callback.message.edit_caption(
                        caption=message_text,
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.debug(f"Could not edit caption, sending new message: {str(e)}")
                    has_error = True
            else:
                try:
                    await callback.message.edit_text(
                        message_text,
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.debug(f"Could not edit text, sending new message: {str(e)}")
                    has_error = True
            
            if has_error:
                await callback.message.answer(
                    message_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            return
        
        text = "📋 <b>История бронирований</b>\n\n"
        
        keyboard_buttons = []
        active_bookings_exist = False
        
        for i, booking in enumerate(bookings, 1):
            status_emoji = {
                'active': '🟢 Активно',
                'completed': 'Завершено',
                'cancelled': '❌ Отменено'
            }.get(booking['status'], '❓ Неизвестно')
            
            before_photos_status = "✅" if booking['before_photos'] >= 6 else "❌"
            after_photos_status = "✅" if booking['after_photos'] >= 6 else "❌"
            
            text += (
                f"<blockquote>"
                f"<b>{i}. {booking['model']} ({booking['number_plate']})</b>\n"
                f"📅 Начало: <b>{booking['start_time'].strftime('%d.%m.%Y %H:%M')}</b>\n"
                f"📅 Окончание: <b>{booking['end_time'].strftime('%d.%m.%Y %H:%M')}</b>\n"
                f"📱 Статус: <b>{status_emoji}</b>\n"
                f"📸 Фото до: <b>{before_photos_status}</b>\n"
                f"📸 Фото после: <b>{after_photos_status}</b>\n"
                f"</blockquote>"
            )
            
            if booking['status'] == 'active':
                active_bookings_exist = True
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=f"❌ Отменить бронь {booking['model']} {booking['number_plate']}",
                        callback_data=f"cancel_user_booking:{booking['id']}"
                    )
                ])
        
        if len(text) > 4000:
            text = text[:4000] + "...\n\n<i>История слишком длинная и была обрезана</i>"
        
        keyboard_buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_start")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        has_error = False
        if callback.message.photo:
            try:
                await callback.message.edit_caption(
                    caption=text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.debug(f"Could not edit caption for bookings list, sending new message: {str(e)}")
                has_error = True
        else:
            try:
                await callback.message.edit_text(
                    text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.debug(f"Could not edit text for bookings list, sending new message: {str(e)}")
                has_error = True
        
        if has_error:
            await callback.message.answer(
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            
        logger.debug(f"Showed booking history to user {callback.from_user.id}")
    
    except Exception as e:
        logger.error(f"Error showing booking history: {e}")
        try:
            await callback.message.answer(
                "❌ Произошла ошибка при получении истории бронирований. Пожалуйста, попробуйте позже.",
                reply_markup=get_start_keyboard()
            )
        except Exception:
            logger.error("Failed to send error message")
            pass

async def cancel_user_booking(callback: types.CallbackQuery, Database):
    """Обрабатывает отмену бронирования пользователем"""
    booking_id = int(callback.data.split(":")[1])
    logger.info(f"User {callback.from_user.id} cancelling booking {booking_id}")
    
    try:
        booking_info = await Database.get_booking_by_id(booking_id)
        
        if not booking_info:
            await callback.answer("Бронирование не найдено", show_alert=True)
            return
            
        if booking_info['telegram_id'] != callback.from_user.id:
            await callback.answer("У вас нет прав на отмену этого бронирования", show_alert=True)
            return
            
        if booking_info['status'] != 'active':
            await callback.answer("Можно отменить только активные бронирования", show_alert=True)
            return
            
        success = await Database.cancel_booking(booking_id)
        
        if success:
            await callback.answer("Бронирование успешно отменено", show_alert=True)
            
            admin_ids = os.getenv('ADMIN_ID', '').split(',')
            if admin_ids:
                admin_notification = (
                    "❌ <b>Пользователь отменил бронирование</b>\n\n"
                    f"👤 Пользователь: <b>{booking_info['full_name']}</b>\n"
                    f"🆔 ID: <code>{booking_info['telegram_id']}</code>\n\n"
                    f"🚘 Автомобиль: <b>{booking_info['model']}</b>\n"
                    f"🏷️ Гос. номер: <b>{booking_info['number_plate']}</b>\n\n"
                    f"📅 Начало: <b>{booking_info['start_time'].strftime('%d.%m.%Y %H:%M')}</b>\n"
                    f"📅 Окончание: <b>{booking_info['end_time'].strftime('%d.%m.%Y %H:%M')}</b>\n\n"
                    f"❌ Бронирование отменено пользователем."
                )
                
                for admin_id in admin_ids:
                    try:
                        await callback.bot.send_message(
                            chat_id=int(admin_id.strip()),
                            text=admin_notification,
                            parse_mode="HTML"
                        )
                        logger.info(f"Sent admin notification about booking cancellation {booking_id} to admin {admin_id}")
                    except Exception as e:
                        logger.error(f"Failed to send admin notification for booking cancellation {booking_id} to admin {admin_id}: {e}")
            
            await show_user_bookings(callback, Database)
        else:
            await callback.answer("Не удалось отменить бронирование. Попробуйте позже.", show_alert=True)
    
    except Exception as e:
        logger.error(f"Error cancelling booking {booking_id}: {e}")
        await callback.answer("Произошла ошибка при отмене бронирования", show_alert=True) 