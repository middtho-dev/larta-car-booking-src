from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger
from ..db.database import Database
from .admin import check_admin
from .keyboards import get_users_keyboard, get_user_details_keyboard, get_user_bookings_keyboard

class AdminSearchStates(StatesGroup):
    waiting_for_search_query = State()
    waiting_for_description = State()

async def start_user_search(callback: types.CallbackQuery, state: FSMContext):
    """Начинает процесс поиска пользователя"""
    user_id = callback.from_user.id
    
    if not await check_admin(user_id):
        logger.warning(f"Unauthorized admin access attempt from user {user_id}")
        await callback.answer("⛔️ У вас нет доступа к админ-панели.")
        return
        
    await state.set_state(AdminSearchStates.waiting_for_search_query)
    await callback.message.edit_text(
        "🔍 <b>Поиск пользователей</b>\n\n"
        "Введите данные, которые вам известны:\n"
        "- номер телефона\n"
        "- имя пользователя\n"
        "- текст из описания",
        reply_markup=get_users_keyboard(),
        parse_mode="HTML"
    )

async def process_search_query(message: types.Message, state: FSMContext, db: Database):
    """Обрабатывает поисковый запрос"""
    if not await check_admin(message.from_user.id):
        return
        
    search_query = message.text
    users = await db.search_users(search_query)
    
    if not users:
        await message.answer(
            "❌ Пользователи не найдены",
            reply_markup=get_users_keyboard()
        )
        await state.clear()
        return
        
    if len(users) == 1:
        user = users[0]
        text = (
            "👤 <b>Информация о пользователе:</b>\n\n"
            f"🆔 Telegram ID: {user['telegram_id']}\n"
            f"🙍‍♂️ Имя пользователя: {user['full_name']}\n"
            f"📝 ФИО: {user['description'] or 'Не указано'}\n"
            f"📞 Номер телефона: {user['phone_number'] or 'Не указан'}"
        )
        await message.answer(
            text,
            reply_markup=get_user_details_keyboard(user['id']),
            parse_mode="HTML"
        )
    else:
        text = ["👥 <b>Найденные пользователи:</b>\n"]
        for user in users:
            text.append(
                f"<blockquote>"
                f"🆔 Telegram ID: {user['telegram_id']}\n"
                f"🙍‍♂️ Имя: {user['full_name']}\n"
                f"📞 Телефон: {user['phone_number'] or 'Не указан'}"
                f"</blockquote>\n"
            )
        await message.answer(
            "\n".join(text),
            reply_markup=get_users_keyboard(),
            parse_mode="HTML"
        )
    
    await state.clear()

async def edit_user_description(callback: types.CallbackQuery, state: FSMContext):
    """Начинает процесс редактирования описания пользователя"""
    user_id = int(callback.data.split(':')[-1])
    await state.update_data(edit_user_id=user_id)
    await state.set_state(AdminSearchStates.waiting_for_description)
    
    await callback.message.edit_text(
        "✏️ Введите новое описание для пользователя:",
        reply_markup=get_users_keyboard(),
        parse_mode="HTML"
    )

async def process_new_description(message: types.Message, state: FSMContext, db: Database):
    """Обрабатывает новое описание пользователя"""
    if not await check_admin(message.from_user.id):
        return
        
    data = await state.get_data()
    user_id = data.get('edit_user_id')
    
    if not user_id:
        await message.answer("❌ Ошибка: пользователь не найден")
        await state.clear()
        return
        
    success = await db.update_user_description(user_id, message.text)
    
    if success:
        await message.answer(
            "✅ Описание пользователя обновлено",
            reply_markup=get_user_details_keyboard(user_id)
        )
    else:
        await message.answer(
            "❌ Не удалось обновить описание",
            reply_markup=get_user_details_keyboard(user_id)
        )
    
    await state.clear()

async def show_user_bookings(callback: types.CallbackQuery, db: Database):
    """Показывает брони пользователя"""
    user_id = int(callback.data.split(':')[-1])
    bookings = await db.get_user_bookings(user_id)
    
    if not bookings:
        await callback.message.edit_text(
            "📋 У пользователя нет броней",
            reply_markup=get_user_details_keyboard(user_id),
            parse_mode="HTML"
        )
        return
        
    text = ["📋 <b>Брони пользователя:</b>\n"]
    has_active_bookings = False
    active_booking_id = None
    
    for booking in bookings:
        status_emoji = {
            'active': '✅',
            'completed': '✔️',
            'canceled': '❌'
        }.get(booking['status'], '❓')
        
        text.append(
            f"<blockquote>"
            f"{status_emoji} <b>{booking['model']}</b> | {booking['number_plate']}\n"
            f"📅 {booking['start_time'].strftime('%d.%m.%Y %H:%M')} - "
            f"{booking['end_time'].strftime('%d.%m.%Y %H:%M')}\n"
            f"Статус: {booking['status']}"
            f"</blockquote>\n"
        )
        
        if booking['status'] == 'active':
            has_active_bookings = True
            active_booking_id = booking['id']
    
    keyboard = get_user_bookings_keyboard(active_booking_id) if has_active_bookings else get_user_details_keyboard(user_id)
    
    await callback.message.edit_text(
        "\n".join(text),
        reply_markup=keyboard,
        parse_mode="HTML"
    )

async def cancel_user_booking(callback: types.CallbackQuery, db: Database):
    """Отменяет бронь пользователя"""
    booking_id = int(callback.data.split(':')[-1])
    success = await db.cancel_booking(booking_id)
    
    if success:
        await callback.answer("✅ Бронь успешно отменена")
        
        booking_info = await db.get_booking_by_id(booking_id)
        if booking_info:
            user_id = booking_info['user_id']
            
            bookings = await db.get_user_bookings(user_id)
            
            if not bookings:
                await callback.message.edit_text(
                    "📋 У пользователя нет броней",
                    reply_markup=get_user_details_keyboard(user_id),
                    parse_mode="HTML"
                )
                return
            
            text = ["📋 <b>Брони пользователя:</b>\n"]
            has_active_bookings = False
            active_booking_id = None
            
            for booking in bookings:
                status_emoji = {
                    'active': '✅',
                    'completed': '✔️',
                    'canceled': '❌'
                }.get(booking['status'], '❓')
                
                text.append(
                    f"<blockquote>"
                    f"{status_emoji} <b>{booking['model']}</b> | {booking['number_plate']}\n"
                    f"📅 {booking['start_time'].strftime('%d.%m.%Y %H:%M')} - "
                    f"{booking['end_time'].strftime('%d.%m.%Y %H:%M')}\n"
                    f"Статус: {booking['status']}"
                    f"</blockquote>\n"
                )
                
                if booking['status'] == 'active':
                    has_active_bookings = True
                    active_booking_id = booking['id']
            
            keyboard = get_user_bookings_keyboard(active_booking_id) if has_active_bookings else get_user_details_keyboard(user_id)
            
            await callback.message.edit_text(
                "\n".join(text),
                reply_markup=keyboard,
                parse_mode="HTML"
            )
    else:
        await callback.answer("❌ Не удалось отменить бронь") 