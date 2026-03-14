from aiogram import types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger
from handlers.admin.keyboards import get_admin_keyboard

class BroadcastStates(StatesGroup):
    waiting_for_message = State()

async def start_broadcast(callback: types.CallbackQuery, state: FSMContext, db):
    """Начинает процесс рассылки сообщений"""
    try:
        async with db.pool.acquire() as conn:
            total_users = await conn.fetchval("SELECT COUNT(*) FROM users")
        
        await state.set_state(BroadcastStates.waiting_for_message)
        
        text = (
            "📢 <b>Меню рассылки сообщений</b>\n\n"
            f"Ваше сообщение будет отправлено <b>{total_users}</b> пользователям.\n\n"
            "Вы можете:\n"
            "• использовать <b>HTML-форматирование</b>\n"
            "• добавлять <b>эмодзи</b> 😊🚀🔥\n"
            "• прикреплять <b>изображения</b>\n\n"
            "✏️ Введите текст сообщения или отправьте изображение с подписью."
        )
        
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🔙 Назад", callback_data="admin:back")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error starting broadcast: {e}")
        await callback.message.edit_text(
            "❌ Произошла ошибка при подготовке рассылки",
            reply_markup=get_admin_keyboard()
        )

async def process_broadcast_message(message: types.Message, state: FSMContext, db):
    """Обрабатывает сообщение для рассылки"""
    try:
        async with db.pool.acquire() as conn:
            users = await conn.fetch("SELECT telegram_id FROM users")
        
        sent_count = 0
        error_count = 0
        
        for user in users:
            try:
                if message.photo:
                    await message.bot.send_photo(
                        chat_id=user['telegram_id'],
                        photo=message.photo[-1].file_id,
                        caption=message.caption,
                        parse_mode="HTML" if message.caption else None
                    )
                else:
                    await message.bot.send_message(
                        chat_id=user['telegram_id'],
                        text=message.text,
                        parse_mode="HTML"
                    )
                sent_count += 1
            except Exception as e:
                logger.error(f"Error sending broadcast to {user['telegram_id']}: {e}")
                error_count += 1
        
        report = (
            "📊 <b>Отчет о рассылке</b>\n\n"
            f"✅ Успешно отправлено: <b>{sent_count}</b>\n"
            f"❌ Ошибок отправки: <b>{error_count}</b>\n"
            f"📊 Всего пользователей: <b>{len(users)}</b>"
        )
        
        await message.answer(report, reply_markup=get_admin_keyboard(), parse_mode="HTML")
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error processing broadcast: {e}")
        await message.answer(
            "❌ Произошла ошибка при выполнении рассылки",
            reply_markup=get_admin_keyboard()
        )
        await state.clear() 