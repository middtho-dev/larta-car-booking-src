import asyncpg
from datetime import datetime
from loguru import logger
import os
from dotenv import load_dotenv
import secrets
import string

load_dotenv()

class Database:
    def __init__(self):
        self.pool = None
        
    async def create_pool(self):
        self.pool = await asyncpg.create_pool(
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASS'),
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT'),
            database=os.getenv('DB_NAME')
        )
        
    async def register_user(self, telegram_id: int, full_name: str, phone_number: str = None) -> bool:
        try:
            async with self.pool.acquire() as conn:
                user = await conn.fetchrow(
                    """
                    INSERT INTO users (telegram_id, full_name, phone_number, created_at)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (telegram_id) 
                    DO UPDATE SET full_name = $2, phone_number = $3
                    RETURNING id
                    """,
                    telegram_id, full_name, phone_number, datetime.now()
                )
                logger.debug(f"User registered/updated: {telegram_id}")
                return True
        except Exception as e:
            logger.error(f"Error registering user: {e}")
            return False
            
    async def get_start_message(self) -> tuple:
        try:
            async with self.pool.acquire() as conn:
                message = await conn.fetchrow(
                    """
                    SELECT text, image_path
                    FROM bot_message
                    WHERE command = 'start'
                    """
                )
                return message['text'], message['image_path'] if message else (None, None)
        except Exception as e:
            logger.error(f"Error getting start message: {e}")
            return None, None

    async def get_cars(self) -> list:
        try:
            async with self.pool.acquire() as conn:
                cars = await conn.fetch(
                    """
                    SELECT id, model, number_plate, status
                    FROM cars
                    WHERE is_enable = TRUE
                    ORDER BY model
                    """
                )
                return cars
        except Exception as e:
            logger.error(f"Error getting cars: {e}")
            return []

    async def get_car_by_id(self, car_id: int) -> dict:
        try:
            async with self.pool.acquire() as conn:
                car = await conn.fetchrow(
                    """
                    SELECT id, model, number_plate, status
                    FROM cars
                    WHERE id = $1 AND is_enable = TRUE
                    """,
                    car_id
                )
                return dict(car) if car else None
        except Exception as e:
            logger.error(f"Error getting car by id: {e}")
            return None

    async def check_car_availability(self, car_id: int, start_time: datetime) -> bool:
        try:
            async with self.pool.acquire() as conn:
                car = await conn.fetchrow(
                    """
                    SELECT status
                    FROM cars
                    WHERE id = $1
                    AND status != 'unavailable'  -- Исключаем только полностью недоступные авто
                    """,
                    car_id
                )
                
                if not car:
                    return False
                
                booking = await conn.fetchrow(
                    """
                    SELECT id
                    FROM bookings
                    WHERE car_id = $1
                    AND status = 'active'
                    AND (
                        ($2 BETWEEN start_time AND end_time)
                    )
                    """,
                    car_id, start_time
                )
                
                return booking is None
                
        except Exception as e:
            logger.error(f"Error checking car availability: {e}")
            return False

    async def update_car_status(self, car_id: int, new_status: str = None) -> bool:
        """
        Обновляет статус автомобиля.
        Если new_status не указан, статус обновляется на основе текущих бронирований
        """
        try:
            async with self.pool.acquire() as conn:
                if new_status:
                    await conn.execute("""
                        UPDATE cars
                        SET status = $2::car_status
                        WHERE id = $1
                    """, car_id, new_status)
                else:
                    bookings = await conn.fetch("""
                        SELECT start_time, end_time
                        FROM bookings
                        WHERE car_id = $1
                        AND status = 'active'
                        ORDER BY start_time
                    """, car_id)
                    
                    if not bookings:
                        await conn.execute("""
                            UPDATE cars
                            SET status = 'available'
                            WHERE id = $1
                        """, car_id)
                    else:
                        now = datetime.now()
                        current_booking = next(
                            (b for b in bookings if b['start_time'] <= now <= b['end_time']),
                            None
                        )
                        
                        if current_booking:
                            await conn.execute("""
                                UPDATE cars
                                SET status = 'unavailable'
                                WHERE id = $1
                            """, car_id)
                        else:
                            await conn.execute("""
                                UPDATE cars
                                SET status = 'booked'
                                WHERE id = $1
                            """, car_id)
                return True
        except Exception as e:
            logger.error(f"Error updating car status: {e}")
            return False

    async def check_booking_overlap(self, car_id: int, start_time: datetime, end_time: datetime) -> bool:
        """Проверяет, нет ли пересечений с существующими бронированиями"""
        try:
            async with self.pool.acquire() as conn:
                booking = await conn.fetchrow(
                    """
                    SELECT id
                    FROM bookings
                    WHERE car_id = $1
                    AND status = 'active'
                    AND (
                        ($2 BETWEEN start_time AND end_time)
                        OR ($3 BETWEEN start_time AND end_time)
                        OR (start_time BETWEEN $2 AND $3)
                        OR (end_time BETWEEN $2 AND $3)
                    )
                    """,
                    car_id, start_time, end_time
                )
                return booking is None
                
        except Exception as e:
            logger.error(f"Error checking booking overlap: {e}")
            return False

    async def create_booking(self, user_id: int, car_id: int, start_time: datetime, end_time: datetime) -> bool:
        try:
            async with self.pool.acquire() as conn:
                user = await conn.fetchrow(
                    """
                    SELECT id
                    FROM users
                    WHERE telegram_id = $1
                    """,
                    user_id
                )
                
                if not user:
                    return False
                
                await conn.execute(
                    """
                    INSERT INTO bookings (user_id, car_id, start_time, end_time, status)
                    VALUES ($1, $2, $3, $4, 'active')
                    """,
                    user['id'], car_id, start_time, end_time
                )
                
                await self.update_car_status(car_id)
                
                return True
                
        except Exception as e:
            logger.error(f"Error creating booking: {e}")
            return False

    async def get_user_bookings(self, telegram_id: int) -> list:
        """Получает все брони пользователя"""
        try:
            async with self.pool.acquire() as conn:
                telegram_id_str = str(telegram_id)
                bookings = await conn.fetch(
                    """
                    SELECT b.id, b.start_time, b.end_time, b.status,
                           c.model, c.number_plate,
                           (SELECT COUNT(*) FROM photos WHERE booking_id = b.id AND stage = 'before') as before_photos,
                           (SELECT COUNT(*) FROM photos WHERE booking_id = b.id AND stage = 'after') as after_photos
                    FROM bookings b
                    JOIN users u ON b.user_id = u.id
                    JOIN cars c ON b.car_id = c.id
                    WHERE u.telegram_id::text = $1
                    ORDER BY b.start_time DESC
                    """,
                    telegram_id_str
                )
                return bookings
        except Exception as e:
            logger.error(f"Error getting user bookings: {e}")
            return []

    async def get_booking_for_photos(self, booking_id: int) -> dict:
        """Получает информацию о бронировании для процесса фотографирования"""
        try:
            async with self.pool.acquire() as conn:
                booking = await conn.fetchrow(
                    """
                    SELECT b.id, b.start_time, b.end_time, c.model, c.number_plate
                    FROM bookings b
                    JOIN cars c ON b.car_id = c.id
                    WHERE b.id = $1 AND b.status = 'active'
                    """,
                    booking_id
                )
                return dict(booking) if booking else None
        except Exception as e:
            logger.error(f"Error getting booking for photos: {e}")
            return None

    async def save_booking_photo(self, booking_id: int, stage: str, angle: str, file_path: str) -> bool:
        """Сохраняет информацию о фотографии в базу данных"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO photos (booking_id, stage, angle, file_path)
                    VALUES ($1, $2, $3, $4)
                    """,
                    booking_id, stage, angle, file_path
                )
                return True
        except Exception as e:
            logger.error(f"Error saving booking photo: {e}")
            return False

    async def get_booking_completion_info(self, booking_id: int) -> dict:
        """Получает полную информацию о бронировании для завершения"""
        try:
            async with self.pool.acquire() as conn:
                booking_info = await conn.fetchrow(
                    """
                    SELECT b.id, b.start_time, b.end_time, b.car_id,
                           u.full_name, u.telegram_id,
                           c.model, c.number_plate
                    FROM bookings b
                    JOIN users u ON b.user_id = u.id
                    JOIN cars c ON b.car_id = c.id
                    WHERE b.id = $1
                    """,
                    booking_id
                )
                return dict(booking_info) if booking_info else None
        except Exception as e:
            logger.error(f"Error getting booking completion info: {e}")
            return None

    async def complete_booking(self, booking_id: int) -> bool:
        """Завершает бронирование"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE bookings 
                    SET status = 'completed' 
                    WHERE id = $1
                    """,
                    booking_id
                )
                return True
        except Exception as e:
            logger.error(f"Error completing booking: {e}")
            return False

    async def get_user_by_telegram_id(self, telegram_id: int) -> dict:
        """Получает данные пользователя по его telegram_id"""
        try:
            async with self.pool.acquire() as conn:
                user = await conn.fetchrow(
                    """
                    SELECT id, telegram_id, full_name, phone_number, created_at
                    FROM users
                    WHERE telegram_id = $1
                    """,
                    telegram_id
                )
                return dict(user) if user else None
        except Exception as e:
            logger.error(f"Error getting user by telegram_id: {e}")
            return None

    async def get_users_count(self) -> int:
        """Получает общее количество пользователей"""
        try:
            async with self.pool.acquire() as conn:
                count = await conn.fetchval(
                    """
                    SELECT COUNT(*)
                    FROM users
                    """
                )
                return count
        except Exception as e:
            logger.error(f"Error getting users count: {e}")
            return 0

    async def get_users_list(self) -> list:
        """Получает список всех пользователей с их данными"""
        try:
            async with self.pool.acquire() as conn:
                users = await conn.fetch(
                    """
                    SELECT telegram_id, full_name, description, phone_number
                    FROM users
                    ORDER BY created_at DESC
                    """
                )
                return [dict(user) for user in users]
        except Exception as e:
            logger.error(f"Error getting users list: {e}")
            return []

    async def search_users(self, search_query: str) -> list:
        """Поиск пользователей по различным параметрам"""
        try:
            async with self.pool.acquire() as conn:
                users = await conn.fetch(
                    """
                    SELECT id, telegram_id, full_name, phone_number, description
                    FROM users
                    WHERE 
                        LOWER(full_name) LIKE LOWER($1) OR
                        LOWER(phone_number) LIKE LOWER($1) OR
                        LOWER(description) LIKE LOWER($1)
                    """,
                    f"%{search_query}%"
                )
                return [dict(user) for user in users]
        except Exception as e:
            logger.error(f"Error searching users: {e}")
            return []

    async def update_user_description(self, user_id: int, description: str) -> bool:
        """Обновляет описание пользователя"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE users
                    SET description = $2
                    WHERE id = $1
                    """,
                    user_id, description
                )
                return True
        except Exception as e:
            logger.error(f"Error updating user description: {e}")
            return False

    async def get_user_bookings(self, user_id: int) -> list:
        """Получает все брони пользователя"""
        try:
            async with self.pool.acquire() as conn:
                bookings = await conn.fetch(
                    """
                    SELECT b.id, b.start_time, b.end_time, b.status,
                           c.model, c.number_plate
                    FROM bookings b
                    JOIN cars c ON b.car_id = c.id
                    WHERE b.user_id = $1
                    ORDER BY b.start_time DESC
                    """,
                    user_id
                )
                return [dict(booking) for booking in bookings]
        except Exception as e:
            logger.error(f"Error getting user bookings: {e}")
            return []

    async def cancel_booking(self, booking_id: int) -> bool:
        """Отменяет бронирование"""
        try:
            async with self.pool.acquire() as conn:
                booking = await conn.fetchrow(
                    """
                    SELECT car_id
                    FROM bookings
                    WHERE id = $1
                    """,
                    booking_id
                )
                
                if not booking:
                    return False
                    
                await conn.execute(
                    """
                    UPDATE bookings
                    SET status = 'canceled'
                    WHERE id = $1
                    """,
                    booking_id
                )
                
                await self.update_car_status(booking['car_id'])
                return True
        except Exception as e:
            logger.error(f"Error canceling booking: {e}")
            return False

    async def get_car_by_number(self, number_plate: str) -> dict:
        """Получает информацию об автомобиле по номеру"""
        try:
            async with self.pool.acquire() as conn:
                car = await conn.fetchrow(
                    """
                    SELECT id, model, number_plate, status
                    FROM cars
                    WHERE number_plate = $1 AND is_enable = TRUE
                    """,
                    number_plate
                )
                return dict(car) if car else None
        except Exception as e:
            logger.error(f"Error getting car by number: {e}")
            return None

    async def delete_car(self, number_plate: str) -> bool:
        """Удаляет автомобиль по номеру"""
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute(
                    """
                    DELETE FROM cars
                    WHERE number_plate = $1
                    AND NOT EXISTS (
                        SELECT 1 FROM bookings
                        WHERE car_id = cars.id
                        AND status = 'active'
                    )
                    """,
                    number_plate
                )
                return result == "DELETE 1"
        except Exception as e:
            logger.error(f"Error deleting car: {e}")
            return False

    async def update_car_model(self, car_id: int, new_model: str) -> bool:
        """Обновляет модель автомобиля"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE cars
                    SET model = $2
                    WHERE id = $1
                    """,
                    car_id, new_model
                )
                return True
        except Exception as e:
            logger.error(f"Error updating car model: {e}")
            return False

    async def update_car_number(self, car_id: int, new_number: str) -> bool:
        """Обновляет номер автомобиля"""
        try:
            async with self.pool.acquire() as conn:
                existing = await conn.fetchval(
                    """
                    SELECT id FROM cars
                    WHERE number_plate = $1 AND id != $2
                    """,
                    new_number, car_id
                )
                
                if existing:
                    return False
                    
                await conn.execute(
                    """
                    UPDATE cars
                    SET number_plate = $2
                    WHERE id = $1
                    """,
                    car_id, new_number
                )
                return True
        except Exception as e:
            logger.error(f"Error updating car number: {e}")
            return False

    async def add_car(self, model: str, number_plate: str) -> bool:
        """Добавляет новый автомобиль"""
        try:
            async with self.pool.acquire() as conn:
                existing = await conn.fetchval(
                    """
                    SELECT id FROM cars
                    WHERE number_plate = $1
                    """,
                    number_plate
                )
                
                if existing:
                    return False
                    
                await conn.execute(
                    """
                    INSERT INTO cars (model, number_plate, status, is_enable)
                    VALUES ($1, $2, 'available', TRUE)
                    """,
                    model, number_plate
                )
                return True
        except Exception as e:
            logger.error(f"Error adding new car: {e}")
            return False

    async def get_most_booked_car(self) -> dict:
        """Получает информацию о самом арендуемом автомобиле"""
        try:
            async with self.pool.acquire() as conn:
                car = await conn.fetchrow("""
                    SELECT c.model, c.number_plate, COUNT(*) as booking_count
                    FROM bookings b
                    JOIN cars c ON b.car_id = c.id
                    GROUP BY c.id, c.model, c.number_plate
                    ORDER BY booking_count DESC
                    LIMIT 1
                """)
                return dict(car) if car else None
        except Exception as e:
            logger.error(f"Error getting most booked car: {e}")
            return None

    async def get_most_active_user(self) -> dict:
        """Получает информацию о самом активном пользователе"""
        try:
            async with self.pool.acquire() as conn:
                user = await conn.fetchrow("""
                    SELECT u.full_name, u.phone_number, u.description, COUNT(*) as booking_count
                    FROM bookings b
                    JOIN users u ON b.user_id = u.id
                    GROUP BY u.id, u.full_name, u.phone_number, u.description
                    ORDER BY booking_count DESC
                    LIMIT 1
                """)
                return dict(user) if user else None
        except Exception as e:
            logger.error(f"Error getting most active user: {e}")
            return None

    async def get_cars_count(self) -> int:
        """Получает общее количество автомобилей"""
        try:
            async with self.pool.acquire() as conn:
                return await conn.fetchval("SELECT COUNT(*) FROM cars")
        except Exception as e:
            logger.error(f"Error getting cars count: {e}")
            return 0

    async def get_active_token(self, user_id: int) -> str | None:
        """Получает активный токен пользователя"""
        try:
            async with self.pool.acquire() as conn:
                token = await conn.fetchrow("""
                    SELECT token, expires_at
                    FROM tokens
                    WHERE user_id = $1 
                    AND status = 'active'
                    LIMIT 1
                    """, user_id)

                if not token:
                    return None

                if token['expires_at'] <= datetime.now():
                    await conn.execute("""
                        UPDATE tokens 
                        SET status = 'expired'
                        WHERE user_id = $1 
                        AND status = 'active'
                    """, user_id)
                    return None

                return token['token']

        except Exception as e:
            logger.error(f"Error getting active token: {e}")
            return None

    async def create_token(self, user_id: int) -> str | None:
        """Создает новый токен для пользователя"""
        try:
            import secrets
            import string
            from datetime import datetime, timedelta

            # alphabet = string.ascii_letters + string.digits
            # token = ''.join(secrets.choice(alphabet) for _ in range(32))
            token = ''.join(secrets.choice(string.digits) for _ in range(6))
            expires_at = datetime.now() + timedelta(days=3650)

            async with self.pool.acquire() as conn:
                await conn.execute("""
                    UPDATE tokens 
                    SET status = 'expired'
                    WHERE user_id = $1
                    """, user_id)
                
                await conn.execute("""
                    INSERT INTO tokens (user_id, token, expires_at, status)
                    VALUES ($1, $2, $3, 'active')
                    """, user_id, token, expires_at)
                
                return token
        except Exception as e:
            logger.error(f"Error creating token: {e}")
            return None

    async def verify_token(self, token: str) -> bool:
        """Проверяет валидность токена"""
        try:
            async with self.pool.acquire() as conn:
                token_data = await conn.fetchrow("""
                    SELECT t.expires_at, t.status, u.id
                    FROM tokens t
                    JOIN users u ON t.user_id = u.id
                    WHERE t.token = $1
                    """, token)

                if not token_data:
                    logger.debug(f"Token not found: {token}")
                    return False

                if token_data['status'] != 'active':
                    logger.debug(f"Token is not active: {token}")
                    return False

                if token_data['expires_at'] <= datetime.now():
                    await conn.execute("""
                        UPDATE tokens 
                        SET status = 'expired'
                        WHERE token = $1
                        """, token)
                    logger.debug(f"Token expired: {token}")
                    return False

                logger.info(f"Token verified successfully for user {token_data['id']}")
                return True

        except Exception as e:
            logger.error(f"Database error while verifying token: {e}")
            return False

    async def get_booking_by_id(self, booking_id: int) -> dict:
        """Получает информацию о бронировании по его ID"""
        try:
            async with self.pool.acquire() as conn:
                booking = await conn.fetchrow("""
                    SELECT b.id, b.start_time, b.end_time, b.status,
                           b.car_id, c.model, c.number_plate,
                           b.user_id, u.full_name, u.telegram_id
                    FROM bookings b
                    JOIN cars c ON b.car_id = c.id
                    JOIN users u ON b.user_id = u.id
                    WHERE b.id = $1
                """, booking_id)
                
                return dict(booking) if booking else None
                
        except Exception as e:
            logger.error(f"Error getting booking by id: {e}")
            return None

    async def get_all_bookings(self) -> list:
        """Получает все бронирования с информацией об автомобилях и пользователях"""
        try:
            async with self.pool.acquire() as conn:
                bookings = await conn.fetch("""
                    SELECT 
                        b.id, b.start_time, b.end_time, b.status,
                        c.model, c.number_plate, c.status as car_status,
                        u.full_name, u.phone_number, u.telegram_id, u.description
                    FROM bookings b
                    JOIN cars c ON b.car_id = c.id
                    JOIN users u ON b.user_id = u.id
                    ORDER BY b.start_time DESC
                """)
                return [dict(b) for b in bookings]
        except Exception as e:
            logger.error(f"Error getting all bookings: {e}")
            return []

    async def get_booking_photos(self, booking_id: int) -> list:
        """Получает все фотографии для конкретного бронирования"""
        try:
            async with self.pool.acquire() as conn:
                photos = await conn.fetch("""
                    SELECT id, booking_id, stage, angle, file_path, uploaded_at
                    FROM photos
                    WHERE booking_id = $1
                    ORDER BY uploaded_at
                """, booking_id)
                return [dict(p) for p in photos]
        except Exception as e:
            logger.error(f"Error getting booking photos: {e}")
            return []

    async def create_web_booking(self, user_id: int, car_id: int, start_time: datetime, end_time: datetime) -> bool:
        """Создает бронирование через веб-интерфейс"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO bookings (user_id, car_id, start_time, end_time, status)
                    VALUES ($1, $2, $3, $4, 'active')
                    """,
                    user_id, car_id, start_time, end_time
                )
                
                await self.update_car_status(car_id)
                
                return True
                
        except Exception as e:
            logger.error(f"Error creating web booking: {e}")
            return False

    async def deactivate_token(self, token: str) -> bool:
        """Деактивирует токен пользователя"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    UPDATE tokens 
                    SET status = 'expired'
                    WHERE token = $1
                    """, token)
                return True
        except Exception as e:
            logger.error(f"Error deactivating token: {e}")
            return False

    async def update_booking_status(self, booking_id: int, new_status: str) -> dict:
        """Обновляет статус бронирования и возвращает информацию о бронировании"""
        try:
            async with self.pool.acquire() as conn:
                booking_info = await conn.fetchrow("""
                    SELECT b.id, b.car_id, b.status,
                           u.telegram_id, u.full_name,
                           c.model, c.number_plate
                    FROM bookings b
                    JOIN users u ON b.user_id = u.id
                    JOIN cars c ON b.car_id = c.id
                    WHERE b.id = $1
                """, booking_id)
                
                if not booking_info:
                    return None
                    
                await conn.execute("""
                    UPDATE bookings
                    SET status = $2::booking_status
                    WHERE id = $1
                """, booking_id, new_status)
                
                await self.update_car_status(booking_info['car_id'])
                
                return dict(booking_info)
                
        except Exception as e:
            logger.error(f"Error updating booking status: {e}")
            return None

    async def disable_car(self, number_plate: str) -> bool:
        """Отключает автомобиль, устанавливая is_enable = False"""
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute(
                    """
                    UPDATE cars
                    SET is_enable = FALSE
                    WHERE number_plate = $1
                    """,
                    number_plate
                )
                return result != "UPDATE 0"
        except Exception as e:
            logger.error(f"Error disabling car: {e}")
            return False

    async def get_all_cars(self) -> list:
        """Получает список всех автомобилей, включая отключенные"""
        try:
            async with self.pool.acquire() as conn:
                cars = await conn.fetch(
                    """
                    SELECT id, model, number_plate, status, is_enable
                    FROM cars
                    ORDER BY model
                    """
                )
                return cars
        except Exception as e:
            logger.error(f"Error getting all cars: {e}")
            return []

    async def enable_car(self, number_plate: str) -> bool:
        """Включает автомобиль, устанавливая is_enable = True"""
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute(
                    """
                    UPDATE cars
                    SET is_enable = TRUE
                    WHERE number_plate = $1
                    """,
                    number_plate
                )
                return result != "UPDATE 0"
        except Exception as e:
            logger.error(f"Error enabling car: {e}")
            return False



    async def set_admin_by_telegram_id(self, telegram_id: int, is_admin: bool = True) -> bool:
        """Назначает/снимает админ-роль по telegram_id."""
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute(
                    """
                    UPDATE users
                    SET admin = $2
                    WHERE telegram_id = $1
                    """,
                    telegram_id,
                    is_admin,
                )
                return result != "UPDATE 0"
        except Exception as e:
            logger.error(f"Error setting admin by telegram_id: {e}")
            return False

    async def get_users_for_admin_panel(self) -> list:
        """Возвращает пользователей для управления правами админов."""
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, telegram_id, full_name, phone_number, admin, created_at
                    FROM users
                    ORDER BY created_at DESC
                    """
                )
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting users for admin panel: {e}")
            return []

    async def set_user_admin(self, user_id: int, is_admin: bool) -> bool:
        """Назначает/снимает права администратора пользователю."""
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute(
                    """
                    UPDATE users
                    SET admin = $2
                    WHERE id = $1
                    """,
                    user_id,
                    is_admin,
                )
                return result != "UPDATE 0"
        except Exception as e:
            logger.error(f"Error setting user admin role: {e}")
            return False

    async def add_review(self, telegram_id: int, car_id: int, booking_id: int, review: str) -> bool:
        """Добавляет отзыв пользователя о бронировании"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO reviews (telegram_id, car_id, booking_id, review, created_at)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    telegram_id, car_id, booking_id, review, datetime.now()
                )
                return True
        except Exception as e:
            logger.error(f"Error adding review: {e}")
            return False

    async def get_booking_review(self, booking_id: int) -> dict:
        """Получает отзыв по ID бронирования"""
        try:
            async with self.pool.acquire() as conn:
                review = await conn.fetchrow(
                    """
                    SELECT id, telegram_id, car_id, booking_id, review, created_at
                    FROM reviews
                    WHERE booking_id = $1
                    """,
                    booking_id
                )
                return dict(review) if review else None
        except Exception as e:
            logger.error(f"Error getting booking review: {e}")
            return None

    async def get_car_reviews(self, car_id: int) -> list:
        """Получает все отзывы о конкретном автомобиле"""
        try:
            async with self.pool.acquire() as conn:
                reviews = await conn.fetch(
                    """
                    SELECT r.id, r.telegram_id, r.car_id, r.booking_id, r.review, r.created_at,
                           u.full_name, b.start_time, b.end_time
                    FROM reviews r
                    JOIN users u ON r.telegram_id = u.telegram_id
                    JOIN bookings b ON r.booking_id = b.id
                    WHERE r.car_id = $1
                    ORDER BY r.created_at DESC
                    """,
                    car_id
                )
                return [dict(review) for review in reviews]
        except Exception as e:
            logger.error(f"Error getting car reviews: {e}")
            return []

    async def get_user_reviews(self, telegram_id: int) -> list:
        """Получает все отзывы конкретного пользователя"""
        try:
            async with self.pool.acquire() as conn:
                reviews = await conn.fetch(
                    """
                    SELECT r.id, r.telegram_id, r.car_id, r.booking_id, r.review, r.created_at,
                           c.model, c.number_plate, b.start_time, b.end_time
                    FROM reviews r
                    JOIN cars c ON r.car_id = c.id
                    JOIN bookings b ON r.booking_id = b.id
                    WHERE r.telegram_id = $1
                    ORDER BY r.created_at DESC
                    """,
                    telegram_id
                )
                return [dict(review) for review in reviews]
        except Exception as e:
            logger.error(f"Error getting user reviews: {e}")
            return []

    async def delete_review(self, review_id: int) -> bool:
        """Удаляет отзыв по его ID"""
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute(
                    """
                    DELETE FROM reviews
                    WHERE id = $1
                    """,
                    review_id
                )
                return result != "DELETE 0"
        except Exception as e:
            logger.error(f"Error deleting review: {e}")
            return False

    async def get_month_report(self, year: int, month: int) -> list:
        """Получает отчет о бронированиях за указанный месяц и год"""
        try:
            async with self.pool.acquire() as conn:
                from datetime import datetime
                
                start_date = datetime(year, month, 1)
                
                if month == 12:
                    next_month_year = year + 1
                    next_month = 1
                else:
                    next_month_year = year
                    next_month = month + 1
                    
                end_date = datetime(next_month_year, next_month, 1)
                
                report = await conn.fetch(
                    """
                    SELECT 
                        u.full_name AS user_name,
                        u.description AS description,
                        u.phone_number AS user_phone,
                        c.model AS car_model,
                        c.number_plate AS car_plate,
                        b.start_time,
                        b.end_time,
                        b.status AS booking_status
                    FROM bookings b
                    JOIN users u ON b.user_id = u.id
                    JOIN cars c ON b.car_id = c.id
                    WHERE 
                        (b.start_time >= $1 AND b.start_time < $2)
                        OR (b.end_time >= $1 AND b.end_time < $2)
                        OR (b.start_time < $1 AND b.end_time >= $2)
                    ORDER BY b.start_time DESC
                    """,
                    start_date, end_date
                )
                
                return [dict(row) for row in report]
                
        except Exception as e:
            logger.error(f"Error getting month report: {e}")
            return [] 