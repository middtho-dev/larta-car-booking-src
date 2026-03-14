import asyncio
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
from loguru import logger
from handlers.db.database import Database
from handlers.db.db_create import create_database
from handlers.users.keyboards import get_start_keyboard
from handlers.users.book_car import show_available_cars, back_to_start
from handlers.fsm_states import AuthStates, BookingStates
from os import path
from handlers.users.booking import (
    process_car_selection,
    process_start_time,
    process_end_time,
    cancel_booking,
    start_photo_process,
    process_photo,
    cancel_photos,
    PhotoStates,
    EndPhotoStates,
    end_photo_process,
    process_end_photo,
    ReviewStates,
    start_review_process,
    process_review
)
from handlers.middleware import BookingNotifier
from handlers.users.history import show_user_bookings as user_show_bookings
from handlers.users.history import cancel_user_booking as user_cancel_booking
from handlers.users.help import show_help
from handlers.admin.admin import admin_command, check_admin
from handlers.admin.users import show_users_list, handle_admin_back
from handlers.admin.search import (
    start_user_search, process_search_query, edit_user_description,
    process_new_description, show_user_bookings, cancel_user_booking,
    AdminSearchStates
)
from handlers.admin.cars import (
    show_cars, start_delete_car, process_delete_car,
    start_edit_car, process_edit_car, edit_car_model,
    process_new_model, edit_car_number, process_new_number,
    show_status_keyboard, update_car_status, AdminCarStates,
    start_add_car, process_car_model, process_car_number
)
from handlers.admin.broadcast import start_broadcast, process_broadcast_message, BroadcastStates
from handlers.admin.stats import show_stats
from handlers.users.tokens import show_calendar_token, refresh_calendar_token

load_dotenv()

logger.add(
    path.join("logs", "main.log"),
    format="{time} {level} {message}",
    level="DEBUG",
    rotation="1 MB",
    compression="zip"
)

bot = Bot(token=os.getenv('BOT_TOKEN'))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
db = Database()

@dp.message(Command("start"), StateFilter(None))
async def start_command(message: types.Message, state: FSMContext):
    logger.debug(f"User {message.from_user.id} started authentication process")
    await message.answer("👋 Пожалуйста, введите пароль для доступа к боту:")
    await state.set_state(AuthStates.waiting_for_password)

@dp.message(StateFilter(AuthStates.waiting_for_password))
async def check_password(message: types.Message, state: FSMContext):
    if message.text == os.getenv('ACCESS_PASSWORD'):
        logger.debug(f"User {message.from_user.id} provided correct password")
        
        user_data = await db.get_user_by_telegram_id(message.from_user.id)
        
        if user_data and user_data['phone_number']:
            logger.debug(f"User {message.from_user.id} already has phone number")
            await state.clear()
            
            await db.register_user(
                telegram_id=message.from_user.id,
                full_name=message.from_user.full_name,
                phone_number=user_data['phone_number']
            )
            
            text, image_path = await db.get_start_message()
            
            if not text:
                text = "Добро пожаловать в сервис бронирования автомобилей! 🚗"
                
            if image_path and path.exists(path.join('static', image_path)):
                await message.answer_photo(
                    photo=types.FSInputFile(path.join('static', image_path)),
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=get_start_keyboard()
                )
            else:
                await message.answer(
                    text=text,
                    parse_mode="HTML",
                    reply_markup=get_start_keyboard()
                )
        else:
            keyboard = types.ReplyKeyboardMarkup(
                keyboard=[[types.KeyboardButton(text="📱 Отправить номер телефона", request_contact=True)]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            await message.answer(
                "Для завершения регистрации, пожалуйста, поделитесь своим номером телефона:",
                reply_markup=keyboard
            )
            await state.set_state(AuthStates.waiting_for_phone)
    else:
        logger.debug(f"User {message.from_user.id} provided incorrect password")
        await message.answer("❌ Неверный пароль. Попробуйте еще раз или используйте /start для перезапуска.")

@dp.message(StateFilter(AuthStates.waiting_for_phone))
async def process_phone_number(message: types.Message, state: FSMContext):
    if not message.contact:
        await message.answer(
            "Пожалуйста, используйте кнопку 'Отправить номер телефона'",
            reply_markup=types.ReplyKeyboardMarkup(
                keyboard=[[types.KeyboardButton(text="📱 Отправить номер телефона", request_contact=True)]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
        )
        return

    phone_number = message.contact.phone_number
    logger.debug(f"User {message.from_user.id} provided phone number")
    
    await message.answer(
        "Спасибо! Регистрация завершена.",
        reply_markup=types.ReplyKeyboardRemove()
    )
    
    await state.clear()
    
    await db.register_user(
        telegram_id=message.from_user.id,
        full_name=message.from_user.full_name,
        phone_number=phone_number
    )
    
    text, image_path = await db.get_start_message()
    
    if not text:
        text = "Добро пожаловать в сервис бронирования автомобилей! 🚗"
        
    if image_path and path.exists(path.join('static', image_path)):
        await message.answer_photo(
            photo=types.FSInputFile(path.join('static', image_path)),
            caption=text,
            parse_mode="HTML",
            reply_markup=get_start_keyboard()
        )
    else:
        await message.answer(
            text=text,
            parse_mode="HTML",
            reply_markup=get_start_keyboard()
        )

@dp.message(Command("start"))
async def already_authenticated(message: types.Message):
    text, image_path = await db.get_start_message()
    
    if not text:
        text = "Добро пожаловать в сервис бронирования автомобилей! 🚗"
        
    if image_path and path.exists(path.join('static', image_path)):
        await message.answer_photo(
            photo=types.FSInputFile(path.join('static', image_path)),
            caption=text,
            parse_mode="HTML",
            reply_markup=get_start_keyboard()
        )
    else:
        await message.answer(
            text=text,
            parse_mode="HTML",
            reply_markup=get_start_keyboard()
        )

@dp.callback_query(F.data == "book_car")
async def process_book_car(callback: types.CallbackQuery):
    logger.debug(f"User {callback.from_user.id} requested car list")
    await show_available_cars(callback, db)

@dp.callback_query(F.data == "back_to_start")
async def process_back_to_start(callback: types.CallbackQuery):
    logger.debug(f"User {callback.from_user.id} returned to start menu")
    await back_to_start(callback, db)

@dp.callback_query(F.data == "my_bookings")
async def process_my_bookings(callback: types.CallbackQuery):
    logger.debug(f"User {callback.from_user.id} requested booking history")
    await user_show_bookings(callback, db)

@dp.callback_query(F.data.startswith("cancel_user_booking:"))
async def process_cancel_user_booking(callback: types.CallbackQuery):
    logger.debug(f"User {callback.from_user.id} requested to cancel booking")
    await user_cancel_booking(callback, db)

@dp.callback_query(F.data == "help")
async def process_help(callback: types.CallbackQuery):
    logger.debug(f"User {callback.from_user.id} requested help")
    await show_help(callback)

@dp.callback_query(F.data.startswith("select_car:"))
async def handle_car_selection(callback: types.CallbackQuery, state: FSMContext):
    await process_car_selection(callback, state, db)

@dp.callback_query(F.data == "cancel_booking")
async def handle_cancel_booking(callback: types.CallbackQuery, state: FSMContext):
    await cancel_booking(callback, state, db)

@dp.message(BookingStates.waiting_for_start_time)
async def handle_start_time(message: types.Message, state: FSMContext):
    await process_start_time(message, state, db)

@dp.message(BookingStates.waiting_for_end_time)
async def handle_end_time(message: types.Message, state: FSMContext):
    await process_end_time(message, state, db)

@dp.callback_query(F.data.startswith("start_photos:"))
async def handle_start_photos(callback: types.CallbackQuery, state: FSMContext):
    await start_photo_process(callback, state, db)

@dp.callback_query(F.data == "cancel_photos")
async def handle_cancel_photos(callback: types.CallbackQuery, state: FSMContext):
    await cancel_photos(callback, state)

@dp.message(PhotoStates.waiting_for_front_interior)
async def handle_front_interior(message: types.Message, state: FSMContext):
    await process_photo(message, state, db)

@dp.message(PhotoStates.waiting_for_rear_interior)
async def handle_rear_interior(message: types.Message, state: FSMContext):
    await process_photo(message, state, db)

@dp.message(PhotoStates.waiting_for_front_view)
async def handle_front_view(message: types.Message, state: FSMContext):
    await process_photo(message, state, db)

@dp.message(PhotoStates.waiting_for_rear_view)
async def handle_rear_view(message: types.Message, state: FSMContext):
    await process_photo(message, state, db)

@dp.message(PhotoStates.waiting_for_left_side)
async def handle_left_side(message: types.Message, state: FSMContext):
    await process_photo(message, state, db)

@dp.message(PhotoStates.waiting_for_right_side)
async def handle_right_side(message: types.Message, state: FSMContext):
    await process_photo(message, state, db)

async def start_using_car(callback: types.CallbackQuery, state: FSMContext, Database: Database):
    """Обработчик кнопки 'Начать использование'"""
    booking_id = int(callback.data.split(":")[1])
    logger.info(f"User {callback.from_user.id} started using car for booking {booking_id}")
    
    async with Database.pool.acquire() as conn:
        booking_info = await conn.fetchrow(
            """
            SELECT b.id, b.start_time, b.end_time, b.user_id,
                   u.full_name, u.telegram_id,
                   c.model, c.number_plate
            FROM bookings b
            JOIN users u ON b.user_id = u.id
            JOIN cars c ON b.car_id = c.id
            WHERE b.id = $1 AND b.status = 'active'
            """,
            booking_id
        )
        
        if not booking_info:
            await callback.answer("Бронирование не найдено или уже неактивно")
            return
        
    await callback.message.edit_text(
        "✅ <b>Вы начали использование автомобиля!</b>\n\n"
        f"🚗 Автомобиль: <b>{booking_info['model']}</b>\n"
        f"🏷️ Гос. номер: <b>{booking_info['number_plate']}</b>\n\n"
        "Приятной поездки! За 10 минут до окончания бронирования "
        "вам придет уведомление о необходимости сделать финальные фотографии.",
        parse_mode="HTML"
    )
    await callback.answer("Начато использование автомобиля!")
    
    admin_ids = os.getenv('ADMIN_ID', '').split(',')
    if admin_ids:
        admin_notification = (
            "🚗 <b>Новое использование автомобиля</b>\n\n"
            f"👤 Пользователь: <b>{booking_info['full_name']}</b>\n"
            f"🆔 ID: <code>{booking_info['telegram_id']}</code>\n\n"
            f"🚘 Автомобиль: <b>{booking_info['model']}</b>\n"
            f"🏷️ Гос. номер: <b>{booking_info['number_plate']}</b>\n\n"
            f"📅 Начало: <b>{booking_info['start_time'].strftime('%d.%m.%Y %H:%M')}</b>\n"
            f"📅 Окончание: <b>{booking_info['end_time'].strftime('%d.%m.%Y %H:%M')}</b>\n\n"
            f"✅ Все фотографии перед началом использования получены."
        )
        
        for admin_id in admin_ids:
            try:
                await callback.bot.send_message(
                    chat_id=int(admin_id.strip()),
                    text=admin_notification,
                    parse_mode="HTML"
                )
                logger.info(f"Sent admin notification about booking {booking_id} to admin {admin_id}")
            except Exception as e:
                logger.error(f"Failed to send admin notification for booking {booking_id} to admin {admin_id}: {e}")

@dp.callback_query(F.data.startswith("start_using:"))
async def handle_start_using(callback: types.CallbackQuery, state: FSMContext):
    await start_using_car(callback, state, db)

@dp.callback_query(F.data.startswith("end_photos:"))
async def handle_end_photos(callback: types.CallbackQuery, state: FSMContext):
    await end_photo_process(callback, state, db)

@dp.message(EndPhotoStates.waiting_for_front_interior)
async def handle_end_front_interior(message: types.Message, state: FSMContext):
    await process_end_photo(message, state, db)

@dp.message(EndPhotoStates.waiting_for_rear_interior)
async def handle_end_rear_interior(message: types.Message, state: FSMContext):
    await process_end_photo(message, state, db)

@dp.message(EndPhotoStates.waiting_for_front_view)
async def handle_end_front_view(message: types.Message, state: FSMContext):
    await process_end_photo(message, state, db)

@dp.message(EndPhotoStates.waiting_for_rear_view)
async def handle_end_rear_view(message: types.Message, state: FSMContext):
    await process_end_photo(message, state, db)

@dp.message(EndPhotoStates.waiting_for_left_side)
async def handle_end_left_side(message: types.Message, state: FSMContext):
    await process_end_photo(message, state, db)

@dp.message(EndPhotoStates.waiting_for_right_side)
async def handle_end_right_side(message: types.Message, state: FSMContext):
    await process_end_photo(message, state, db)

@dp.callback_query(F.data.startswith("add_reviews:"))
async def handle_add_review(callback: types.CallbackQuery, state: FSMContext):
    await start_review_process(callback, state, db)

@dp.message(ReviewStates.waiting_for_review)
async def handle_review_message(message: types.Message, state: FSMContext):
    await process_review(message, state, db)

@dp.message(Command("admin"))
async def handle_admin_command(message: types.Message):
    """Обработчик команды /admin"""
    await admin_command(message)

@dp.callback_query(F.data == "admin:users")
async def process_admin_users(callback: types.CallbackQuery):
    logger.debug(f"Admin {callback.from_user.id} requested users list")
    await show_users_list(callback, db)

@dp.callback_query(F.data == "admin:back")
async def process_admin_back(callback: types.CallbackQuery):
    logger.debug(f"Admin {callback.from_user.id} returned to admin menu")
    await handle_admin_back(callback, db)

@dp.callback_query(F.data == "admin:users:search")
async def handle_user_search(callback: types.CallbackQuery, state: FSMContext):
    logger.debug(f"Admin {callback.from_user.id} started user search")
    await start_user_search(callback, state)

@dp.message(AdminSearchStates.waiting_for_search_query)
async def handle_search_query(message: types.Message, state: FSMContext):
    logger.debug(f"Admin {message.from_user.id} provided search query")
    await process_search_query(message, state, db)

@dp.callback_query(F.data.startswith("admin:users:edit:"))
async def handle_edit_description(callback: types.CallbackQuery, state: FSMContext):
    logger.debug(f"Admin {callback.from_user.id} started editing user description")
    await edit_user_description(callback, state)

@dp.message(AdminSearchStates.waiting_for_description)
async def handle_new_description(message: types.Message, state: FSMContext):
    logger.debug(f"Admin {message.from_user.id} provided new description")
    await process_new_description(message, state, db)

@dp.callback_query(F.data.startswith("admin:users:bookings:"))
async def handle_user_bookings(callback: types.CallbackQuery):
    logger.debug(f"Admin {callback.from_user.id} requested user bookings")
    await show_user_bookings(callback, db)

@dp.callback_query(F.data.startswith("admin:booking:cancel:"))
async def handle_booking_cancel(callback: types.CallbackQuery):
    logger.debug(f"Admin {callback.from_user.id} canceled booking")
    await cancel_user_booking(callback, db)

@dp.callback_query(F.data == "admin:cars")
async def process_admin_cars(callback: types.CallbackQuery):
    logger.debug(f"Admin {callback.from_user.id} requested cars list")
    await show_cars(callback, db)

@dp.callback_query(F.data == "admin:cars:delete")
async def handle_car_delete(callback: types.CallbackQuery, state: FSMContext):
    logger.debug(f"Admin {callback.from_user.id} started car deletion")
    await start_delete_car(callback, state)

@dp.message(AdminCarStates.waiting_for_number_plate_delete)
async def handle_delete_car_number(message: types.Message, state: FSMContext):
    logger.debug(f"Admin {message.from_user.id} provided car number for deletion")
    await process_delete_car(message, state, db)

@dp.callback_query(F.data == "admin:cars:edit")
async def handle_car_edit(callback: types.CallbackQuery, state: FSMContext):
    logger.debug(f"Admin {callback.from_user.id} started car editing")
    await start_edit_car(callback, state)

@dp.message(AdminCarStates.waiting_for_number_plate_edit)
async def handle_edit_car_number(message: types.Message, state: FSMContext):
    logger.debug(f"Admin {message.from_user.id} provided car number for editing")
    await process_edit_car(message, state, db)

@dp.callback_query(F.data.startswith("admin:cars:edit:model:"))
async def handle_edit_model(callback: types.CallbackQuery, state: FSMContext):
    logger.debug(f"Admin {callback.from_user.id} started editing car model")
    await edit_car_model(callback, state)

@dp.message(AdminCarStates.waiting_for_new_model)
async def handle_new_model(message: types.Message, state: FSMContext):
    logger.debug(f"Admin {message.from_user.id} provided new car model")
    await process_new_model(message, state, db)

@dp.callback_query(F.data.startswith("admin:cars:edit:number:"))
async def handle_edit_number(callback: types.CallbackQuery, state: FSMContext):
    logger.debug(f"Admin {callback.from_user.id} started editing car number")
    await edit_car_number(callback, state)

@dp.message(AdminCarStates.waiting_for_new_number)
async def handle_new_number(message: types.Message, state: FSMContext):
    logger.debug(f"Admin {message.from_user.id} provided new car number")
    await process_new_number(message, state, db)

@dp.callback_query(F.data.startswith("admin:cars:edit:status:"))
async def handle_edit_status(callback: types.CallbackQuery):
    logger.debug(f"Admin {callback.from_user.id} started editing car status")
    await show_status_keyboard(callback, db)

@dp.callback_query(F.data.startswith("admin:cars:status:"))
async def handle_new_status(callback: types.CallbackQuery):
    logger.debug(f"Admin {callback.from_user.id} selected new car status")
    await update_car_status(callback, db)

@dp.callback_query(F.data == "admin:cars:add")
async def handle_car_add(callback: types.CallbackQuery, state: FSMContext):
    logger.debug(f"Admin {callback.from_user.id} started adding new car")
    await start_add_car(callback, state)

@dp.message(AdminCarStates.waiting_for_model)
async def handle_car_model(message: types.Message, state: FSMContext):
    logger.debug(f"Admin {message.from_user.id} provided car model")
    await process_car_model(message, state)

@dp.message(AdminCarStates.waiting_for_number)
async def handle_car_number(message: types.Message, state: FSMContext):
    logger.debug(f"Admin {message.from_user.id} provided car number")
    await process_car_number(message, state, db)

@dp.callback_query(F.data == "admin:mailing")
async def handle_broadcast_start(callback: types.CallbackQuery, state: FSMContext):
    logger.debug(f"Admin {callback.from_user.id} started broadcast")
    await start_broadcast(callback, state, db)

@dp.message(BroadcastStates.waiting_for_message)
async def handle_broadcast_message(message: types.Message, state: FSMContext):
    logger.debug(f"Admin {message.from_user.id} sent broadcast message")
    await process_broadcast_message(message, state, db)

@dp.callback_query(F.data == "admin:stats")
async def handle_admin_stats(callback: types.CallbackQuery):
    logger.debug(f"Admin {callback.from_user.id} requested statistics")
    await show_stats(callback, db)

@dp.callback_query(F.data == "calendar")
async def process_calendar(callback: types.CallbackQuery):
    logger.debug(f"User {callback.from_user.id} requested calendar access")
    await show_calendar_token(callback, db)

@dp.callback_query(F.data == "refresh_calendar")
async def process_refresh_calendar(callback: types.CallbackQuery):
    logger.debug(f"User {callback.from_user.id} refreshed calendar token")
    await refresh_calendar_token(callback, db)

def register_handlers(dp: Dispatcher) -> None:

    dp.callback_query.register(show_cars, F.data == "admin:cars")
    

async def main():
    try:
        logger.debug("Initializing database...")
        if not await create_database():
            logger.error("Failed to initialize database")
            return
            
        logger.debug("Creating database pool...")
        await db.create_pool()

        bootstrap_admin_id = os.getenv("FIRST_ADMIN_TELEGRAM_ID", "").strip()
        if bootstrap_admin_id:
            try:
                ok = await db.set_admin_by_telegram_id(int(bootstrap_admin_id), True)
                if ok:
                    logger.info(f"Bootstrap admin ensured for telegram_id={bootstrap_admin_id}")
                else:
                    logger.warning(
                        "FIRST_ADMIN_TELEGRAM_ID is set, but user not found in DB yet. "
                        "User must open /start once, then restart bot."
                    )
            except ValueError:
                logger.error("FIRST_ADMIN_TELEGRAM_ID must be an integer")
        
        logger.debug("Starting booking notifier...")
        notifier = BookingNotifier(bot, db)
        await notifier.start()
        
        logger.debug("Starting bot...")
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"Error in main function: {e}")
    finally:
        if db.pool:
            await db.pool.close()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main()) 