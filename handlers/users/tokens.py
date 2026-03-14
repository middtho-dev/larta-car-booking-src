from aiogram import types
from loguru import logger
from handlers.users.keyboards import get_calendar_keyboard
from aiogram.exceptions import TelegramBadRequest

async def show_calendar_token(callback: types.CallbackQuery, db):
    """Показывает токен для доступа к календарю"""
    try:
        user = await db.get_user_by_telegram_id(callback.from_user.id)
        if not user:
            error_text = "❌ Ошибка: пользователь не найден. Пожалуйста, перезапустите бота командой /start"
            error_keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="🔄 Перезапустить", callback_data="back_to_start")]
            ])
            
            if callback.message.photo:
                await callback.message.edit_caption(
                    caption=error_text,
                    reply_markup=error_keyboard
                )
            else:
                await callback.message.edit_text(
                    text=error_text,
                    reply_markup=error_keyboard
                )
            return

        token = await db.get_active_token(user['id'])
        
        if not token:
            token = await db.create_token(user['id'])
            if not token:
                error_text = "❌ Произошла ошибка при создании токена. Пожалуйста, попробуйте позже."
                if callback.message.photo:
                    await callback.message.edit_caption(
                        caption=error_text,
                        reply_markup=get_calendar_keyboard()
                    )
                else:
                    await callback.message.edit_text(
                        text=error_text,
                        reply_markup=get_calendar_keyboard()
                    )
                return

        text = (
            "📅 <b>Доступ к веб-версии календаря</b>\n\n"
            "Для перехода к веб-интерфейсу календаря нажмите кнопку ниже ⬇️.\n\n"
            "🔐 При входе используйте ваш персональный токен для авторизации. "
            "Он обеспечивает безопасный доступ к вашим данным.\n"
            "Если у вас возникли вопросы — обратитесь к администратору.\n\n"
            f"Ваш токен: <code>{token}</code>"
        )

        try:
            if callback.message.photo:
                await callback.message.edit_caption(
                    caption=text,
                    reply_markup=get_calendar_keyboard(),
                    parse_mode="HTML"
                )
            else:
                await callback.message.edit_text(
                    text=text,
                    reply_markup=get_calendar_keyboard(),
                    parse_mode="HTML"
                )
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                await callback.answer(
                    "Сообщение не обновлено. Ваш токен всё ещё активен и не требует замены",
                    show_alert=True
                )
            else:
                raise e
        
        logger.debug(f"Showed calendar token to user {callback.from_user.id}")
        
    except Exception as e:
        logger.error(f"Error showing calendar token: {e}")
        if not isinstance(e, TelegramBadRequest) or "message is not modified" not in str(e):
            error_text = "❌ Произошла ошибка при получении токена. Пожалуйста, попробуйте позже."
            if callback.message.photo:
                await callback.message.edit_caption(
                    caption=error_text,
                    reply_markup=get_calendar_keyboard()
                )
            else:
                await callback.message.edit_text(
                    text=error_text,
                    reply_markup=get_calendar_keyboard()
                )

async def refresh_calendar_token(callback: types.CallbackQuery, db):
    """Обновляет сообщение с токеном календаря"""
    await show_calendar_token(callback, db) 