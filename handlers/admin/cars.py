from aiogram import types
from aiogram.fsm.context import FSMContext
from loguru import logger
from ..db.database import Database
from .admin import check_admin
from .keyboards import get_cars_keyboard, get_admin_keyboard, get_car_edit_keyboard, get_car_status_keyboard
from ..fsm_states import AdminCarStates
import os

async def show_cars(callback: types.CallbackQuery, db: Database):
    """Показывает список автомобилей"""
    user_id = callback.from_user.id
    
    if not await check_admin(user_id):
        logger.warning(f"Unauthorized admin access attempt from user {user_id}")
        await callback.answer("⛔️ У вас нет доступа к админ-панели.")
        return
        
    cars = await db.get_all_cars()
    
    if not cars:
        await callback.message.edit_text(
            "🚗 <b>Доступные автомобили</b>\n\n"
            "Автомобили не найдены",
            reply_markup=get_cars_keyboard(),
            parse_mode="HTML"
        )
        return
        
    text = ["🚗 <b>Все автомобили</b>\n"]
    active_count = 0
    
    for car in cars:
        logger.debug(f"Car status: {car['status']}, type: {type(car['status'])}")
        status_emoji = {
            'available': '✅',
            'unavailable': '❌',
            'booked': '📅'
        }.get(car['status'], '❓')
        
        status_text = {
            'available': 'Доступен',
            'unavailable': 'В ремонте',
            'booked': 'Забронирован'
        }.get(car['status'], 'Неизвестно')
        
        is_enabled = car.get('is_enable', True)
        enabled_text = "🟢 Активен" if is_enabled else "⚫ Отключен"
        
        if is_enabled:
            active_count += 1
        
        text.append(
            f"<blockquote>"
            f"🚘 Марка/модель: <b>{car['model']}</b>\n"
            f"📃 Гос.номер: <code>{car['number_plate']}</code>\n"
            f"📊 Статус: <b>{status_emoji} {status_text}</b>\n"
            f"🔌 Состояние: <b>{enabled_text}</b>"
            f"</blockquote>\n"
        )
    
    text.append(f"<b>Всего автомобилей:</b> {len(cars)} (активных: {active_count})")
    
    await callback.message.edit_text(
        "\n".join(text),
        reply_markup=get_cars_keyboard(),
        parse_mode="HTML"
    )

async def start_delete_car(callback: types.CallbackQuery, state: FSMContext):
    """Начинает процесс удаления автомобиля"""
    user_id = callback.from_user.id
    
    if not await check_admin(user_id):
        await callback.answer("⛔️ У вас нет доступа к админ-панели.")
        return
        
    await state.set_state(AdminCarStates.waiting_for_number_plate_delete)
    await callback.message.edit_text(
        "🚗 <b>Удаление автомобиля</b>\n\n"
        "Введите государственный номер автомобиля для удаления:",
        parse_mode="HTML"
    )

async def process_delete_car(message: types.Message, state: FSMContext, db: Database):
    """Обрабатывает отключение автомобиля"""
    if not await check_admin(message.from_user.id):
        return
        
    number_plate = message.text.upper()
    success = await db.disable_car(number_plate)
    
    if success:
        await message.answer(
            "✅ Автомобиль успешно отключен и больше не будет отображаться в списке",
            reply_markup=get_cars_keyboard()
        )
    else:
        await message.answer(
            "❌ Автомобиль не найден или не может быть отключен",
            reply_markup=get_cars_keyboard()
        )
    
    await state.clear()

async def start_edit_car(callback: types.CallbackQuery, state: FSMContext):
    """Начинает процесс редактирования автомобиля"""
    user_id = callback.from_user.id
    
    if not await check_admin(user_id):
        await callback.answer("⛔️ У вас нет доступа к админ-панели.")
        return
        
    await state.set_state(AdminCarStates.waiting_for_number_plate_edit)
    await callback.message.edit_text(
        "🚗 <b>Редактирование автомобиля</b>\n\n"
        "Введите государственный номер автомобиля для редактирования:",
        parse_mode="HTML"
    )

async def process_edit_car(message: types.Message, state: FSMContext, db: Database):
    """Обрабатывает выбор автомобиля для редактирования"""
    if not await check_admin(message.from_user.id):
        return
        
    number_plate = message.text.upper()
    car = await db.get_car_by_number(number_plate)
    
    if not car:
        await message.answer(
            "❌ Автомобиль не найден",
            reply_markup=get_cars_keyboard()
        )
        await state.clear()
        return
    
    await message.answer(
        f"🚗 <b>Редактирование автомобиля</b>\n\n"
        f"🚘 Модель: <b>{car['model']}</b>\n"
        f"📃 Гос.номер: <code>{car['number_plate']}</code>\n"
        f"📊 Статус: <b>{car['status']}</b>\n\n"
        f"Выберите, что хотите изменить:",
        reply_markup=get_car_edit_keyboard(car['id']),
        parse_mode="HTML"
    )
    await state.clear()

async def edit_car_model(callback: types.CallbackQuery, state: FSMContext):
    """Запрашивает новую модель автомобиля"""
    car_id = int(callback.data.split(':')[-1])
    await state.update_data(car_id=car_id)
    await state.set_state(AdminCarStates.waiting_for_new_model)
    await callback.message.edit_text(
        "✏️ Введите новую модель автомобиля:",
        parse_mode="HTML"
    )

async def process_new_model(message: types.Message, state: FSMContext, db: Database):
    """Обрабатывает новую модель автомобиля"""
    if not await check_admin(message.from_user.id):
        return
        
    data = await state.get_data()
    car_id = data.get('car_id')
    
    if not car_id:
        await message.answer("❌ Ошибка: автомобиль не найден")
        await state.clear()
        return
        
    success = await db.update_car_model(car_id, message.text)
    
    if success:
        car = await db.get_car_by_id(car_id)
        await message.answer(
            f"✅ Модель успешно изменена\n\n"
            f"🚘 Модель: <b>{car['model']}</b>\n"
            f"📃 Гос.номер: <code>{car['number_plate']}</code>\n"
            f"📊 Статус: <b>{car['status']}</b>",
            reply_markup=get_car_edit_keyboard(car_id),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "❌ Не удалось изменить модель",
            reply_markup=get_cars_keyboard()
        )
    
    await state.clear()

async def edit_car_number(callback: types.CallbackQuery, state: FSMContext):
    """Запрашивает новый номер автомобиля"""
    car_id = int(callback.data.split(':')[-1])
    await state.update_data(car_id=car_id)
    await state.set_state(AdminCarStates.waiting_for_new_number)
    await callback.message.edit_text(
        "🔄 Введите новый государственный номер автомобиля:",
        parse_mode="HTML"
    )

async def process_new_number(message: types.Message, state: FSMContext, db: Database):
    """Обрабатывает новый номер автомобиля"""
    if not await check_admin(message.from_user.id):
        return
        
    data = await state.get_data()
    car_id = data.get('car_id')
    
    if not car_id:
        await message.answer("❌ Ошибка: автомобиль не найден")
        await state.clear()
        return
        
    success = await db.update_car_number(car_id, message.text.upper())
    
    if success:
        car = await db.get_car_by_id(car_id)
        await message.answer(
            f"✅ Номер успешно изменен\n\n"
            f"🚘 Модель: <b>{car['model']}</b>\n"
            f"📃 Гос.номер: <code>{car['number_plate']}</code>\n"
            f"📊 Статус: <b>{car['status']}</b>",
            reply_markup=get_car_edit_keyboard(car_id),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "❌ Не удалось изменить номер",
            reply_markup=get_cars_keyboard()
        )
    
    await state.clear()

async def show_status_keyboard(callback: types.CallbackQuery, db: Database):
    """Показывает клавиатуру выбора статуса"""
    car_id = int(callback.data.split(':')[-1])
    car = await db.get_car_by_id(car_id)
    
    if not car:
        await callback.answer("❌ Автомобиль не найден")
        return
        
    status_text = {
        'available': 'Доступен',
        'unavailable': 'В ремонте',
        'booked': 'Забронирован'
    }.get(car['status'], 'Неизвестно')
    
    await callback.message.edit_text(
        f"🚗 <b>Изменение статуса</b>\n\n"
        f"🚘 Модель: <b>{car['model']}</b>\n"
        f"📃 Гос.номер: <code>{car['number_plate']}</code>\n"
        f"📊 Текущий статус: <b>{status_text}</b>\n\n"
        f"Выберите новый статус:",
        reply_markup=get_car_status_keyboard(car_id),
        parse_mode="HTML"
    )

async def update_car_status(callback: types.CallbackQuery, db: Database):
    """Обновляет статус автомобиля"""
    car_id = int(callback.data.split(':')[-2])
    new_status = callback.data.split(':')[-1]
    
    success = await db.update_car_status(car_id, new_status)
    
    if success:
        car = await db.get_car_by_id(car_id)
        await callback.message.edit_text(
            f"✅ Статус успешно изменен\n\n"
            f"🚘 Модель: <b>{car['model']}</b>\n"
            f"📃 Гос.номер: <code>{car['number_plate']}</code>\n"
            f"📊 Статус: <b>{car['status']}</b>",
            reply_markup=get_car_edit_keyboard(car_id),
            parse_mode="HTML"
        )
    else:
        await callback.answer("❌ Не удалось изменить статус")

async def start_add_car(callback: types.CallbackQuery, state: FSMContext):
    """Начинает процесс добавления автомобиля"""
    user_id = callback.from_user.id
    
    if not await check_admin(user_id):
        await callback.answer("⛔️ У вас нет доступа к админ-панели.")
        return
        
    await state.set_state(AdminCarStates.waiting_for_model)
    await callback.message.edit_text(
        "🚗 <b>Добавление нового автомобиля</b>\n\n"
        "Введите марку и модель автомобиля\n"
        "Пример: <code>Toyota Camry</code>",
        parse_mode="HTML"
    )

async def process_car_model(message: types.Message, state: FSMContext):
    """Обрабатывает ввод модели автомобиля"""
    if not await check_admin(message.from_user.id):
        return
        
    await state.update_data(model=message.text)
    await state.set_state(AdminCarStates.waiting_for_number)
    
    await message.answer(
        "🚙 Введите государственный номер автомобиля\n"
        "Пример: <code>А123ВС</code>",
        parse_mode="HTML"
    )

async def process_car_number(message: types.Message, state: FSMContext, db: Database):
    """Обрабатывает ввод номера автомобиля и создает новый автомобиль"""
    if not await check_admin(message.from_user.id):
        return
        
    data = await state.get_data()
    model = data.get('model')
    number_plate = message.text.upper()
    
    success = await db.add_car(model, number_plate)
    
    if success:
        await message.answer(
            f"✅ Автомобиль успешно добавлен\n\n"
            f"🚘 Модель: <b>{model}</b>\n"
            f"📃 Гос.номер: <code>{number_plate}</code>\n"
            f"📊 Статус: <b>Доступен</b>",
            reply_markup=get_cars_keyboard(),
            parse_mode="HTML"
        )
        
        admin_ids = os.getenv('ADMIN_ID', '').split(',')
        if admin_ids:
            admin_notification = (
                "🆕 <b>Добавлен новый автомобиль</b>\n\n"
                f"🚘 Модель: <b>{model}</b>\n"
                f"📃 Гос.номер: <code>{number_plate}</code>\n"
                f"📊 Статус: <b>Доступен</b>\n\n"
                f"👤 Добавил: <b>{message.from_user.full_name}</b>"
            )
            
            for admin_id in admin_ids:
                try:
                    if str(message.from_user.id) != admin_id.strip():
                        await message.bot.send_message(
                            chat_id=int(admin_id.strip()),
                            text=admin_notification,
                            parse_mode="HTML"
                        )
                except Exception as e:
                    logger.error(f"Failed to send admin notification to {admin_id}: {e}")
    else:
        await message.answer(
            "❌ Не удалось добавить автомобиль. Возможно, автомобиль с таким номером уже существует.",
            reply_markup=get_cars_keyboard()
        )
    
    await state.clear() 