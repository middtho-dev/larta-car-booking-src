import asyncio
from datetime import datetime, timedelta
from typing import Dict
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from loguru import logger
import os
from handlers.db.database import Database

class BookingNotifier:
    def __init__(self, bot: Bot, db: Database):
        self.bot = bot
        self.db = db
        self.notified_bookings: Dict[int, bool] = {}  
        self.check_interval = int(os.getenv('CHECK_INTERVAL', 60)) 
        self.notify_time = int(os.getenv('NOTIFY_TIME', 1)) 
        self.timezone = os.getenv('TIMEZONE', 'UTC') 
        logger.info(f"BookingNotifier initialized with notify_time={self.notify_time}m, check_interval={self.check_interval}s, timezone={self.timezone}")
        
    async def get_upcoming_bookings(self) -> list:
        """Получает бронирования, которые начнутся в ближайшее время"""
        try:
            logger.debug("Fetching upcoming bookings...")
            async with self.db.pool.acquire() as conn:
                all_active = await conn.fetch(
                    """
                    SELECT b.id, b.start_time, u.telegram_id, c.model, c.number_plate
                    FROM bookings b
                    JOIN users u ON b.user_id = u.id
                    JOIN cars c ON b.car_id = c.id
                    WHERE b.status = 'active'
                    """
                )
                logger.debug(f"All active bookings: {all_active}")

                current_time = datetime.now()
                check_window_end = current_time + timedelta(minutes=self.notify_time)
                
                logger.debug(f"Current server time (local): {current_time}")
                logger.debug(f"Looking for bookings between {current_time} and {check_window_end}")
                
                query = """
                    SELECT b.id, b.start_time, u.telegram_id, c.model, c.number_plate
                    FROM bookings b
                    JOIN users u ON b.user_id = u.id
                    JOIN cars c ON b.car_id = c.id
                    WHERE b.status = 'active'
                    AND b.start_time BETWEEN $1 AND $2
                    AND b.id NOT IN (
                        SELECT booking_id 
                        FROM photos 
                        WHERE stage = 'before'
                        GROUP BY booking_id 
                        HAVING COUNT(*) >= 6
                    )
                """
                logger.debug(f"Executing query with time range: {current_time} to {check_window_end}")
                logger.debug(query)
                
                bookings = await conn.fetch(query, current_time, check_window_end)
                
                logger.debug(f"Found {len(bookings)} upcoming bookings")
                logger.debug(f"Bookings found: {bookings}")
                return bookings
        except Exception as e:
            logger.error(f"Error getting upcoming bookings: {e}")
            logger.error(f"Full error details: {str(e)}")
            return []
            
    async def get_ending_bookings(self) -> list:
        """Получает бронирования, которые скоро закончатся"""
        try:
            logger.debug("Fetching ending bookings...")
            async with self.db.pool.acquire() as conn:
                current_time = datetime.now()
                check_window_end = current_time + timedelta(minutes=self.notify_time)
                
                logger.debug(f"Current server time (local): {current_time}")
                logger.debug(f"Looking for ending bookings between {current_time} and {check_window_end}")
                
                query = """
                    SELECT b.id, b.end_time, u.telegram_id, c.model, c.number_plate
                    FROM bookings b
                    JOIN users u ON b.user_id = u.id
                    JOIN cars c ON b.car_id = c.id
                    WHERE b.status = 'active'
                    AND b.end_time BETWEEN $1 AND $2
                    AND b.id NOT IN (
                        SELECT booking_id 
                        FROM photos 
                        WHERE stage = 'after'
                        GROUP BY booking_id 
                        HAVING COUNT(*) >= 6
                    )
                """
                
                bookings = await conn.fetch(query, current_time, check_window_end)
                
                logger.debug(f"Found {len(bookings)} ending bookings")
                logger.debug(f"Ending bookings: {bookings}")
                return bookings
        except Exception as e:
            logger.error(f"Error getting ending bookings: {e}")
            logger.error(f"Full error details: {str(e)}")
            return []
            
    def get_start_photos_keyboard(self, booking_id: int) -> InlineKeyboardMarkup:
        """Создает клавиатуру для начала фотографирования"""
        logger.debug(f"Creating photo keyboard for booking {booking_id}")
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="📸 Продолжить",
                callback_data=f"start_photos:{booking_id}"
            )]
        ])
        
    def get_end_photos_keyboard(self, booking_id: int) -> InlineKeyboardMarkup:
        """Создает клавиатуру для завершения фотографирования"""
        logger.debug(f"Creating end photo keyboard for booking {booking_id}")
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="📸 Сделать финальные фото",
                callback_data=f"end_photos:{booking_id}"
            )]
        ])
        
    async def check_bookings(self):
        """Проверяет бронирования и отправляет уведомления"""
        logger.info("Starting booking check loop")
        while True:
            try:
                now = datetime.now()
                next_check = now + timedelta(seconds=self.check_interval)
                logger.info(f"Server time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
                logger.info(f"Next check scheduled at: {next_check.strftime('%Y-%m-%d %H:%M:%S')}")
                logger.debug("Checking bookings...")
                
                bookings = await self.get_upcoming_bookings()
                
                for booking in bookings:
                    booking_id = booking['id']
                    if booking_id in self.notified_bookings:
                        logger.debug(f"Booking {booking_id} already notified, skipping")
                        continue
                        
                    logger.info(f"Sending notification for booking {booking_id} (car: {booking['model']} {booking['number_plate']})")
                    text = (
                        "⚠️ <b>Внимание!</b>\n\n"
                        f"Через {self.notify_time} минут начнется ваше бронирование:\n"
                        f"🚗 Автомобиль: <b>{booking['model']}</b>\n"
                        f"🏷️ Гос. номер: <b>{booking['number_plate']}</b>\n\n"
                        "Пожалуйста, сделайте фотографии автомобиля для продолжения."
                    )
                    
                    try:
                        await self.bot.send_message(
                            chat_id=booking['telegram_id'],
                            text=text,
                            reply_markup=self.get_start_photos_keyboard(booking_id),
                            parse_mode="HTML"
                        )
                        self.notified_bookings[booking_id] = True
                        logger.info(f"Successfully sent notification for booking {booking_id}")
                    except Exception as e:
                        logger.error(f"Error sending notification for booking {booking_id}: {e}")
                        
                ending_bookings = await self.get_ending_bookings()
                
                for booking in ending_bookings:
                    booking_id = booking['id']
                    notification_key = f"end_{booking_id}"
                    if notification_key in self.notified_bookings:
                        logger.debug(f"End notification for booking {booking_id} already sent, skipping")
                        continue
                        
                    logger.info(f"Sending end notification for booking {booking_id} (car: {booking['model']} {booking['number_plate']})")
                    text = (
                        "⚠️ <b>Внимание!</b>\n\n"
                        f"Через {self.notify_time} минут закончится ваше бронирование:\n"
                        f"🚗 Автомобиль: <b>{booking['model']}</b>\n"
                        f"🏷️ Гос. номер: <b>{booking['number_plate']}</b>\n\n"
                        "Пожалуйста, сделайте финальные фотографии автомобиля для завершения аренды."
                    )
                    
                    try:
                        await self.bot.send_message(
                            chat_id=booking['telegram_id'],
                            text=text,
                            reply_markup=self.get_end_photos_keyboard(booking_id),
                            parse_mode="HTML"
                        )
                        self.notified_bookings[notification_key] = True
                        logger.info(f"Successfully sent end notification for booking {booking_id}")
                    except Exception as e:
                        logger.error(f"Error sending end notification for booking {booking_id}: {e}")
                    
            except Exception as e:
                logger.error(f"Error in booking check loop: {e}")
                
            logger.debug("Booking check completed, sleeping...")
            await asyncio.sleep(self.check_interval)
            
    async def start(self):
        """Запускает проверку бронирований"""
        logger.info("Starting BookingNotifier service")
        asyncio.create_task(self.check_bookings()) 