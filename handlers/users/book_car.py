from aiogram import types
from aiogram.fsm.context import FSMContext
from loguru import logger
from handlers.users.keyboards import get_cars_keyboard, get_start_keyboard
import os

async def show_available_cars(callback: types.CallbackQuery, db) -> None:
    try:
        cars = await db.get_cars()
        
        if not cars:
            text = "😔 К сожалению, сейчас нет доступных автомобилей."
        else:
            text = (
                "🚗 <b>Доступные автомобили для аренды:</b>\n\n"
                "Выберите подходящую модель из списка ниже:\n"
                "🟢 — доступен для аренды\n"
                "🟡 — уже кто-то забронировал\n"
                "🔴 — временно недоступен\n\n"
            )
            for car in cars:
                status_emoji = {
                    'available': '🟢',
                    'booked': '🟡',
                    'unavailable': '🔴'
                }.get(car['status'], '🔴')
                
                status_text = {
                    'available': 'Доступен',
                    'booked': 'Есть бронирования',
                    'unavailable': 'В ремонте'
                }.get(car['status'], 'Недоступен')
                text += f"<blockquote>"
                text += f"{status_emoji} <b>{car['model']}</b>\n"
                text += f"🔢 Номер: {car['number_plate']}\n"
                text += f"📍 Статус: {status_text}\n"
                text += f"</blockquote>\n"
                #text += "🚘──────────────\n"

        
        if callback.message.photo:
            await callback.message.edit_caption(
                caption=text,
                reply_markup=get_cars_keyboard(cars) if cars else get_start_keyboard(),
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                text=text,
                reply_markup=get_cars_keyboard(cars) if cars else get_start_keyboard(),
                parse_mode="HTML"
            )
            
    except Exception as e:
        logger.error(f"Error showing available cars: {e}")
        error_text = "😔 Произошла ошибка при получении списка автомобилей."
        
        try:
            if callback.message.photo:
                await callback.message.edit_caption(
                    caption=error_text,
                    reply_markup=get_start_keyboard()
                )
            else:
                await callback.message.edit_text(
                    text=error_text,
                    reply_markup=get_start_keyboard()
                )
        except Exception as e:
            logger.error(f"Error handling error message: {e}")

async def back_to_start(callback: types.CallbackQuery, Database):
    """Возвращает пользователя в главное меню"""
    logger.debug(f"User {callback.from_user.id} returns to start")
    
    text, image_path = await Database.get_start_message()
    
    if not text:
        text = "Добро пожаловать в сервис бронирования автомобилей! 🚗"
    
    keyboard = get_start_keyboard()
    
    try:
        has_photo = callback.message.photo
        
        if has_photo and image_path and os.path.exists(os.path.join('static', image_path)):
            try:
                await callback.message.edit_caption(
                    caption=text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                return
            except Exception as e:
                logger.warning(f"Could not edit caption: {e}")
        
        if image_path and os.path.exists(os.path.join('static', image_path)):
            await callback.message.answer_photo(
                photo=types.FSInputFile(os.path.join('static', image_path)),
                caption=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
    except Exception as e:
        logger.warning(f"Error returning to start: {e}")
        try:
            if image_path and os.path.exists(os.path.join('static', image_path)):
                await callback.message.answer_photo(
                    photo=types.FSInputFile(os.path.join('static', image_path)),
                    caption=text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                await callback.message.answer(
                    text=text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
        except Exception as e2:
            logger.error(f"Failed to send fallback message: {e2}") 