from datetime import datetime
from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger
from handlers.users.keyboards import (
    get_cars_keyboard, get_back_keyboard,
    get_cancel_keyboard, get_start_keyboard,
    get_ending_keyboard
)
from handlers.fsm_states import BookingStates
from handlers.users.book_car import show_available_cars
from handlers.db.database import Database
from utils.time_helpers import parse_datetime
from typing import Annotated
import os

class PhotoStates(StatesGroup):
    waiting_for_front_interior = State()
    waiting_for_rear_interior = State()
    waiting_for_front_view = State()
    waiting_for_rear_view = State()
    waiting_for_left_side = State()
    waiting_for_right_side = State()

class EndPhotoStates(StatesGroup):
    waiting_for_front_interior = State()
    waiting_for_rear_interior = State()
    waiting_for_front_view = State()
    waiting_for_rear_view = State()
    waiting_for_left_side = State()
    waiting_for_right_side = State()

class ReviewStates(StatesGroup):
    waiting_for_review = State()

def get_photo_keyboard() -> types.InlineKeyboardMarkup:
    """Создает клавиатуру для процесса фотографирования"""
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(
            text="❌ Отменить",
            callback_data="cancel_photos"
        )]
    ])

def get_start_using_keyboard(booking_id: int) -> types.InlineKeyboardMarkup:
    """Создает клавиатуру для начала использования автомобиля"""
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(
            text="✅ Начать использование",
            callback_data=f"start_using:{booking_id}"
        )]
    ])

async def process_car_selection(
    callback: types.CallbackQuery,
    state: FSMContext,
    Database: Database
):
    car_id = int(callback.data.split(":")[1])
    car = await Database.get_car_by_id(car_id)
    
    if not car:
        await callback.answer("Автомобиль не найден")
        return
        
    if car['status'] == 'unavailable':
        await callback.answer("Этот автомобиль сейчас используется")
        return
        
    await state.update_data(selected_car_id=car_id)
    await state.set_state(BookingStates.waiting_for_start_time)
    
    text = (
        "🚗 <b>Бронирование автомобиля</b>\n\n"
        f"🔹 <b>Марка:</b> <i>{car['model']}</i>\n"
        f"🔹 <b>Гос. номер:</b> <i>{car['number_plate']}</i>\n\n"
        "📅 Пожалуйста, укажите дату и время, на которые хотите забронировать автомобиль.\n"
        "Например: <b>30.07.2025 13:00</b>"
    )
    
    if callback.message.photo:
        await callback.message.edit_caption(
            caption=text,
            reply_markup=get_back_keyboard(),
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_back_keyboard(),
            parse_mode="HTML"
        )

async def process_start_time(message: types.Message, state: FSMContext, Database: Database):
    try:
        start_time = parse_datetime(message.text)
        if start_time < datetime.now():
            await message.answer(
                "❌ Нельзя выбрать дату в прошлом. Пожалуйста, укажите будущую дату и время.",
                reply_markup=get_cancel_keyboard()
            )
            return
            
        data = await state.get_data()
        car_id = data['selected_car_id']
        car = await Database.get_car_by_id(car_id)
        
        if not car:
            await message.answer(
                "❌ Ошибка: автомобиль не найден.",
                reply_markup=get_start_keyboard()
            )
            await state.clear()
            return
            
        is_available = await Database.check_car_availability(car_id, start_time)
        
        if not is_available:
            await message.answer(
                "❌ Извините, автомобиль недоступен на это время. Пожалуйста, выберите другое время.",
                reply_markup=get_cancel_keyboard()
            )
            return
            
        await state.update_data(start_time=start_time)
        await state.set_state(BookingStates.waiting_for_end_time)
        
        text = (
            "✅ <b>Отлично!</b>\n"
            f"На выбранную дату автомобиль\n"
            f"🚗 <b>{car['model']}</b> | 🏷️ <b>гос. номер: {car['number_plate']}</b> — <b>свободен</b>.\n\n"
            "📌 Для продолжения, пожалуйста, укажите дату и время <b>возвращения автомобиля на парковку</b>.\n"
            "Например: <b>30.07.2025 21:00</b>"
        )
        
        await message.answer(
            text,
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML"
        )
        
    except ValueError:
        await message.answer(
            "❌ Неверный формат даты и времени. Пожалуйста, используйте формат ДД.ММ.ГГГГ ЧЧ:ММ\n"
            "Например: 30.07.2025 13:00",
            reply_markup=get_cancel_keyboard()
        )

async def process_end_time(
    message: types.Message,
    state: FSMContext,
    Database: Database
):
    try:
        end_time = parse_datetime(message.text)
        data = await state.get_data()
        start_time = data["start_time"]
        
        if end_time <= start_time:
            await message.answer(
                "❌ Время возврата должно быть позже времени начала бронирования.",
                reply_markup=get_cancel_keyboard()
            )
            return
            
        car_id = data["selected_car_id"]
        car = await Database.get_car_by_id(car_id)
        
        no_overlap = await Database.check_booking_overlap(car_id, start_time, end_time)
        if not no_overlap:
            await message.answer(
                "❌ На выбранное время уже есть бронирование. Пожалуйста, выберите другое время.",
                reply_markup=get_cancel_keyboard()
            )
            return
            
        booking_created = await Database.create_booking(
            message.from_user.id,
            car_id,
            start_time,
            end_time
        )
        
        if booking_created:
            text = (
                "✅ <b>Бронирование успешно создано!</b>\n\n"
                f"🚗 Автомобиль: <b>{car['model']}</b>\n"
                f"🏷️ Гос. номер: <b>{car['number_plate']}</b>\n"
                f"📅 Начало: <b>{start_time.strftime('%d.%m.%Y %H:%M')}</b>\n"
                f"📅 Окончание: <b>{end_time.strftime('%d.%m.%Y %H:%M')}</b>"
            )
            
            await message.answer(
                text,
                reply_markup=get_start_keyboard(),
                parse_mode="HTML"
            )
        else:
            await message.answer(
                "❌ Не удалось создать бронирование. Пожалуйста, попробуйте позже.",
                reply_markup=get_start_keyboard()
            )
            
        await state.clear()
        
    except ValueError:
        await message.answer(
            "❌ Неверный формат даты и времени. Пожалуйста, используйте формат ДД.ММ.ГГГГ ЧЧ:ММ\n"
            "Например: 30.07.2025 21:00",
            reply_markup=get_cancel_keyboard()
        )

async def cancel_booking(callback: types.CallbackQuery, state: FSMContext, Database: Database):
    await state.clear()
    await show_available_cars(callback, Database)

async def start_photo_process(callback: types.CallbackQuery, state: FSMContext, Database: Database):
    """Начинает процесс фотографирования"""
    booking_id = int(callback.data.split(":")[1])
    logger.info(f"Starting photo process for booking {booking_id}")
    
    booking = await Database.get_booking_for_photos(booking_id)
    
    if not booking:
        logger.warning(f"Booking {booking_id} not found or inactive")
        await callback.answer("Бронирование не найдено или уже неактивно")
        return
        
    await state.update_data(booking_id=booking_id)
    await state.set_state(PhotoStates.waiting_for_front_interior)
    logger.debug(f"Set state to waiting_for_front_interior for booking {booking_id}")
    
    text = (
        "📸 <b>Фотографирование автомобиля</b>\n\n"
        f"🚗 Автомобиль: <b>{booking['model']}</b>\n"
        f"🏷️ Гос. номер: <b>{booking['number_plate']}</b>\n\n"
        "Пожалуйста, сделайте фотографию <b>передней части салона</b>.\n"
        "Убедитесь, что фото четкое и хорошо освещено."
    )
    
    await callback.message.answer(
        text,
        reply_markup=get_photo_keyboard(),
        parse_mode="HTML"
    )
    logger.info(f"Started photo process for booking {booking_id}")

async def process_photo(message: types.Message, state: FSMContext, Database: Database):
    """Обрабатывает полученные фотографии"""
    if not message.photo:
        logger.warning(f"User {message.from_user.id} sent message without photo")
        await message.answer(
            "❌ Пожалуйста, отправьте фотографию.",
            reply_markup=get_photo_keyboard()
        )
        return
        
    current_state = await state.get_state()
    data = await state.get_data()
    booking_id = data['booking_id']
    logger.debug(f"Processing photo for booking {booking_id}, state: {current_state}")
    
    angle_mapping = {
        'PhotoStates:waiting_for_front_interior': 'front_interior',
        'PhotoStates:waiting_for_rear_interior': 'rear_interior',
        'PhotoStates:waiting_for_front_view': 'front_view',
        'PhotoStates:waiting_for_rear_view': 'rear_view',
        'PhotoStates:waiting_for_left_side': 'left_side',
        'PhotoStates:waiting_for_right_side': 'right_side'
    }
    
    current_angle = angle_mapping[current_state]
    logger.debug(f"Current angle: {current_angle}")
    
    try:
        file_id = message.photo[-1].file_id
        file = await message.bot.get_file(file_id)
        file_path = f"photos/before_{booking_id}_{current_angle}.jpg"
        await message.bot.download_file(file.file_path, file_path)
        logger.info(f"Saved photo for booking {booking_id}, angle: {current_angle}")
        
        await Database.save_booking_photo(booking_id, 'before', current_angle, file_path)
        logger.debug(f"Saved photo info to database for booking {booking_id}")
        
        next_states = {
            'PhotoStates:waiting_for_front_interior': (
                PhotoStates.waiting_for_rear_interior,
                "Отлично! Теперь сделайте фотографию <b>задней части салона</b>."
            ),
            'PhotoStates:waiting_for_rear_interior': (
                PhotoStates.waiting_for_front_view,
                "Отлично! Теперь сделайте фотографию <b>спереди автомобиля</b>."
            ),
            'PhotoStates:waiting_for_front_view': (
                PhotoStates.waiting_for_rear_view,
                "Отлично! Теперь сделайте фотографию <b>сзади автомобиля</b>."
            ),
            'PhotoStates:waiting_for_rear_view': (
                PhotoStates.waiting_for_left_side,
                "Отлично! Теперь сделайте фотографию <b>левой стороны</b> автомобиля."
            ),
            'PhotoStates:waiting_for_left_side': (
                PhotoStates.waiting_for_right_side,
                "Отлично! Теперь сделайте фотографию <b>правой стороны</b> автомобиля."
            )
        }
        
        if current_state in next_states:
            next_state, message_text = next_states[current_state]
            await state.set_state(next_state)
            logger.debug(f"Set next state: {next_state} for booking {booking_id}")
            await message.answer(
                message_text,
                reply_markup=get_photo_keyboard(),
                parse_mode="HTML"
            )
        else:
            await state.clear()
            logger.info(f"Completed photo process for booking {booking_id}")
            
            await message.answer(
                "✅ <b>Отлично! Все фотографии получены.</b>\n\n"
                "Теперь вы можете начать использовать автомобиль.\n"
                "За 10 минут до окончания бронирования вам придет уведомление "
                "о необходимости сделать финальные фотографии.",
                reply_markup=get_start_using_keyboard(booking_id),
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Error processing photo for booking {booking_id}: {e}")
        await message.answer(
            "❌ Произошла ошибка при сохранении фотографии. Пожалуйста, попробуйте еще раз.",
            reply_markup=get_photo_keyboard()
        )

async def cancel_photos(callback: types.CallbackQuery, state: FSMContext):
    """Отменяет процесс фотографирования"""
    current_state = await state.get_state()
    data = await state.get_data()
    booking_id = data.get('booking_id')
    logger.info(f"Canceling photo process for booking {booking_id} at state {current_state}")
    
    await state.clear()
    await callback.message.edit_text(
        "❌ Процесс фотографирования отменен. Пожалуйста, начните заново, когда будете готовы.",
        reply_markup=get_start_keyboard()
    )
    logger.debug(f"Photo process canceled for booking {booking_id}")

async def end_photo_process(callback: types.CallbackQuery, state: FSMContext, Database: Database):
    """Начинает процесс финального фотографирования"""
    booking_id = int(callback.data.split(":")[1])
    logger.info(f"Starting end photo process for booking {booking_id}")
    
    async with Database.pool.acquire() as conn:
        booking = await conn.fetchrow(
            """
            SELECT b.id, b.end_time, c.model, c.number_plate
            FROM bookings b
            JOIN cars c ON b.car_id = c.id
            WHERE b.id = $1 AND b.status = 'active'
            """,
            booking_id
        )
        
    if not booking:
        logger.warning(f"Booking {booking_id} not found or inactive")
        await callback.answer("Бронирование не найдено или уже неактивно")
        return
        
    await state.update_data(booking_id=booking_id)
    await state.set_state(EndPhotoStates.waiting_for_front_interior)
    logger.debug(f"Set state to EndPhotoStates.waiting_for_front_interior for booking {booking_id}")
    
    text = (
        "📸 <b>Финальное фотографирование автомобиля</b>\n\n"
        f"🚗 Автомобиль: <b>{booking['model']}</b>\n"
        f"🏷️ Гос. номер: <b>{booking['number_plate']}</b>\n\n"
        "Пожалуйста, сделайте фотографию <b>передней части салона</b>.\n"
        "Убедитесь, что фото четкое и хорошо освещено."
    )
    
    await callback.message.answer(
        text,
        reply_markup=get_photo_keyboard(),
        parse_mode="HTML"
    )
    logger.info(f"Started end photo process for booking {booking_id}")

async def process_end_photo(message: types.Message, state: FSMContext, Database: Database):
    """Обрабатывает полученные финальные фотографии"""
    if not message.photo:
        logger.warning(f"User {message.from_user.id} sent message without photo")
        await message.answer(
            "❌ Пожалуйста, отправьте фотографию.",
            reply_markup=get_photo_keyboard()
        )
        return
        
    current_state = await state.get_state()
    data = await state.get_data()
    booking_id = data['booking_id']
    logger.debug(f"Processing end photo for booking {booking_id}, state: {current_state}")
    
    angle_mapping = {
        'EndPhotoStates:waiting_for_front_interior': 'front_interior',
        'EndPhotoStates:waiting_for_rear_interior': 'rear_interior',
        'EndPhotoStates:waiting_for_front_view': 'front_view',
        'EndPhotoStates:waiting_for_rear_view': 'rear_view',
        'EndPhotoStates:waiting_for_left_side': 'left_side',
        'EndPhotoStates:waiting_for_right_side': 'right_side'
    }
    
    current_angle = angle_mapping[current_state]
    logger.debug(f"Current angle: {current_angle}")
    
    try:
        file_id = message.photo[-1].file_id
        file = await message.bot.get_file(file_id)
        file_path = f"photos/after_{booking_id}_{current_angle}.jpg"
        await message.bot.download_file(file.file_path, file_path)
        logger.info(f"Saved end photo for booking {booking_id}, angle: {current_angle}")
        
        await Database.save_booking_photo(booking_id, 'after', current_angle, file_path)
        logger.debug(f"Saved end photo info to database for booking {booking_id}")
        
        next_states = {
            'EndPhotoStates:waiting_for_front_interior': (
                EndPhotoStates.waiting_for_rear_interior,
                "Отлично! Теперь сделайте фотографию <b>задней части салона</b>."
            ),
            'EndPhotoStates:waiting_for_rear_interior': (
                EndPhotoStates.waiting_for_front_view,
                "Отлично! Теперь сделайте фотографию <b>спереди автомобиля</b>."
            ),
            'EndPhotoStates:waiting_for_front_view': (
                EndPhotoStates.waiting_for_rear_view,
                "Отлично! Теперь сделайте фотографию <b>сзади автомобиля</b>."
            ),
            'EndPhotoStates:waiting_for_rear_view': (
                EndPhotoStates.waiting_for_left_side,
                "Отлично! Теперь сделайте фотографию <b>левой стороны</b> автомобиля."
            ),
            'EndPhotoStates:waiting_for_left_side': (
                EndPhotoStates.waiting_for_right_side,
                "Отлично! Теперь сделайте фотографию <b>правой стороны</b> автомобиля."
            )
        }
        
        if current_state in next_states:
            next_state, message_text = next_states[current_state]
            await state.set_state(next_state)
            logger.debug(f"Set next state: {next_state} for booking {booking_id}")
            await message.answer(
                message_text,
                reply_markup=get_photo_keyboard(),
                parse_mode="HTML"
            )
        else:
            await state.clear()
            logger.info(f"Completed end photo process for booking {booking_id}")
            
            booking_info = await Database.get_booking_completion_info(booking_id)
            
            if booking_info:
                await Database.complete_booking(booking_id)
                logger.info(f"Updated booking {booking_id} status to completed")
                
                await Database.update_car_status(booking_info['car_id'])
                logger.info(f"Updated car {booking_info['car_id']} status after completing booking")
                
                await message.answer(
                    "✅ <b>Отлично! Все финальные фотографии получены.</b>\n\n"
                    "Ваша аренда успешно завершена. Благодарим за использование нашего сервиса!",
                    reply_markup=get_ending_keyboard(booking_id),
                    parse_mode="HTML"
                )
                
                admin_ids = os.getenv('ADMIN_ID', '').split(',')
                if admin_ids:
                    admin_notification = (
                        "🚗 <b>Завершена аренда автомобиля</b>\n\n"
                        f"👤 Пользователь: <b>{booking_info['full_name']}</b>\n"
                        f"🆔 ID: <code>{booking_info['telegram_id']}</code>\n\n"
                        f"🚘 Автомобиль: <b>{booking_info['model']}</b>\n"
                        f"🏷️ Гос. номер: <b>{booking_info['number_plate']}</b>\n\n"
                        f"📅 Начало: <b>{booking_info['start_time'].strftime('%d.%m.%Y %H:%M')}</b>\n"
                        f"📅 Окончание: <b>{booking_info['end_time'].strftime('%d.%m.%Y %H:%M')}</b>\n\n"
                        f"✅ Все финальные фотографии получены."
                    )
                    
                    for admin_id in admin_ids:
                        try:
                            await message.bot.send_message(
                                chat_id=int(admin_id.strip()),
                                text=admin_notification,
                                parse_mode="HTML"
                            )
                            logger.info(f"Sent admin notification about booking completion {booking_id} to admin {admin_id}")
                        except Exception as e:
                            logger.error(f"Failed to send admin notification for booking completion {booking_id} to admin {admin_id}: {e}")
    except Exception as e:
        logger.error(f"Error processing end photo for booking {booking_id}: {e}")
        await message.answer(
            "❌ Произошла ошибка при сохранении фотографии. Пожалуйста, попробуйте еще раз.",
            reply_markup=get_photo_keyboard()
        )

async def start_review_process(callback: types.CallbackQuery, state: FSMContext, Database: Database):
    """Начинает процесс сбора отзывов"""
    booking_id = int(callback.data.split(":")[1])
    logger.info(f"Starting review process for booking {booking_id}")
    
    booking_info = await Database.get_booking_by_id(booking_id)
    
    if not booking_info:
        logger.warning(f"Booking {booking_id} not found for review")
        await callback.answer("Бронирование не найдено", show_alert=True)
        return
    
    await state.update_data(
        booking_id=booking_id,
        car_id=booking_info['car_id'],
        telegram_id=callback.from_user.id
    )
    await state.set_state(ReviewStates.waiting_for_review)
    
    text = (
        "🚗 <b>Спасибо, что выбрали наш сервис!</b>\n"
        "Нам очень важно знать, как прошла ваша аренда. Это помогает нам становиться лучше "
        "и делать будущий опыт ещё комфортнее для вас и других пользователей.\n\n"
        "📝 Пожалуйста, напишите, что вам понравилось, и что, по вашему мнению, можно улучшить.\n"
        "💡 Вы можете рассказать об автомобиле, процессе бронирования, поддержке или любых других деталях.\n\n"
        "Мы внимательно читаем каждый отзыв \n"
        "Заранее благодарим за обратную связь!"
    )
    
    await callback.message.edit_text(
        text=text,
        reply_markup=get_back_keyboard(),
        parse_mode="HTML"
    )
    logger.debug(f"Set state to waiting_for_review for booking {booking_id}")

async def process_review(message: types.Message, state: FSMContext, Database: Database):
    """Обрабатывает отзыв пользователя"""
    current_state = await state.get_state()
    
    if current_state != "ReviewStates:waiting_for_review":
        return
    
    data = await state.get_data()
    booking_id = data.get('booking_id')
    car_id = data.get('car_id')
    telegram_id = data.get('telegram_id')
    review_text = message.text
    
    logger.info(f"Processing review for booking {booking_id} from user {telegram_id}")
    
    review_saved = await Database.add_review(telegram_id, car_id, booking_id, review_text)
    
    if review_saved:
        await message.answer(
            "✅ <b>Большое спасибо за ваш отзыв!</b>\n\n"
            "Мы ценим ваше мнение и обязательно учтем его в нашей работе.",
            reply_markup=get_start_keyboard(),
            parse_mode="HTML"
        )
        
        user_info = await Database.get_user_by_telegram_id(telegram_id)
        car_info = await Database.get_car_by_id(car_id)
        
        admin_ids = os.getenv('ADMIN_ID', '').split(',')
        if admin_ids and user_info and car_info:
            admin_notification = (
                "📋 <b>Новый отзыв о поездке</b>\n\n"
                f"👤 Пользователь: <b>{user_info.get('full_name', 'Неизвестно')}</b>\n"
                f"🆔 ID: <code>{telegram_id}</code>\n"
                f"🚘 Автомобиль: <b>{car_info.get('model', 'Неизвестно')}</b>\n"
                f"🏷️ Гос. номер: <b>{car_info.get('number_plate', 'Неизвестно')}</b>\n"
                f"🔢 ID бронирования: <b>{booking_id}</b>\n\n"
                f"📝 <b>Отзыв:</b>\n<i>{review_text}</i>"
            )
            
            for admin_id in admin_ids:
                try:
                    await message.bot.send_message(
                        chat_id=int(admin_id.strip()),
                        text=admin_notification,
                        parse_mode="HTML"
                    )
                    logger.info(f"Sent admin notification about new review for booking {booking_id} to admin {admin_id}")
                except Exception as e:
                    logger.error(f"Failed to send admin notification about review for booking {booking_id} to admin {admin_id}: {e}")
    else:
        await message.answer(
            "❌ <b>К сожалению, произошла ошибка при сохранении отзыва.</b>\n"
            "Пожалуйста, попробуйте позже или обратитесь в поддержку.",
            reply_markup=get_start_keyboard(),
            parse_mode="HTML"
        )
        logger.error(f"Failed to save review for booking {booking_id} from user {telegram_id}")
    
    await state.clear()
    logger.debug(f"Cleared state after review for booking {booking_id}") 