import asyncio
import os
from datetime import datetime, timedelta
from typing import Dict

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from loguru import logger

from handlers.db.database import Database


class BookingNotifier:
    def __init__(self, bot: Bot, db: Database):
        self.bot = bot
        self.db = db
        self.notified_bookings: Dict[int, bool] = {}
        self.check_interval = int(os.getenv("CHECK_INTERVAL", 60))
        self.notify_time = int(os.getenv("NOTIFY_TIME", 1))
        self.timezone = os.getenv("TIMEZONE", "UTC")
        self.web_app_url = os.getenv("WEB_APP_URL", "http://localhost:8000/dashboard")
        self.cleanup_grace_minutes = int(os.getenv("NOTIFICATION_CLEANUP_GRACE_MINUTES", 10))

        logger.info(
            "BookingNotifier initialized with notify_time={}m, check_interval={}s, timezone={}, web_app_url={}",
            self.notify_time,
            self.check_interval,
            self.timezone,
            self.web_app_url,
        )

    async def get_upcoming_bookings(self) -> list:
        """Получает бронирования, которые начнутся в ближайшее время."""
        try:
            async with self.db.pool.acquire() as conn:
                current_time = datetime.now()
                check_window_end = current_time + timedelta(minutes=self.notify_time)

                query = """
                    SELECT b.id, b.start_time, b.end_time, u.telegram_id, c.model, c.number_plate
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
                return await conn.fetch(query, current_time, check_window_end)
        except Exception as e:
            logger.error(f"Error getting upcoming bookings: {e}")
            return []

    async def get_ending_bookings(self) -> list:
        """Получает бронирования, которые скоро закончатся."""
        try:
            async with self.db.pool.acquire() as conn:
                current_time = datetime.now()
                check_window_end = current_time + timedelta(minutes=self.notify_time)

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

                return await conn.fetch(query, current_time, check_window_end)
        except Exception as e:
            logger.error(f"Error getting ending bookings: {e}")
            return []

    def _keyboard(self, booking_id: int, is_end: bool = False) -> InlineKeyboardMarkup:
        action_text = "📸 Сделать финальные фото" if is_end else "📸 Сделать фото до поездки"
        action_data = f"end_photos:{booking_id}" if is_end else f"start_photos:{booking_id}"

        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=action_text, callback_data=action_data)],
                [InlineKeyboardButton(text="🌐 Открыть веб-приложение", url=self.web_app_url)],
            ]
        )

    async def _schedule_delete(self, chat_id: int, message_id: int, delay_seconds: int):
        """Удаляет уведомление через delay_seconds (самоуничтожение)."""
        if delay_seconds <= 0:
            delay_seconds = 1

        await asyncio.sleep(delay_seconds)
        try:
            await self.bot.delete_message(chat_id=chat_id, message_id=message_id)
            logger.info(f"Deleted notification message_id={message_id} for chat_id={chat_id}")
        except Exception as e:
            logger.warning(f"Could not delete notification message_id={message_id}: {e}")

    async def check_bookings(self):
        """Проверяет бронирования и отправляет уведомления."""
        logger.info("Starting booking check loop")
        while True:
            try:
                now = datetime.now()
                logger.info(f"Server time: {now.strftime('%Y-%m-%d %H:%M:%S')}")

                upcoming = await self.get_upcoming_bookings()
                for booking in upcoming:
                    booking_id = booking["id"]
                    if booking_id in self.notified_bookings:
                        continue

                    text = (
                        "⚠️ <b>Внимание!</b>\n\n"
                        f"Через {self.notify_time} минут начнется ваше бронирование:\n"
                        f"🚗 Автомобиль: <b>{booking['model']}</b>\n"
                        f"🏷️ Гос. номер: <b>{booking['number_plate']}</b>\n\n"
                        "Откройте веб-приложение для управления поездкой и сделайте фото перед стартом."
                    )

                    try:
                        msg = await self.bot.send_message(
                            chat_id=booking["telegram_id"],
                            text=text,
                            reply_markup=self._keyboard(booking_id, is_end=False),
                            parse_mode="HTML",
                        )
                        self.notified_bookings[booking_id] = True

                        end_time = booking.get("end_time")
                        if isinstance(end_time, datetime):
                            delete_at = end_time + timedelta(minutes=self.cleanup_grace_minutes)
                            delay = int((delete_at - datetime.now()).total_seconds())
                            asyncio.create_task(
                                self._schedule_delete(booking["telegram_id"], msg.message_id, delay)
                            )
                    except Exception as e:
                        logger.error(f"Error sending notification for booking {booking_id}: {e}")

                ending = await self.get_ending_bookings()
                for booking in ending:
                    booking_id = booking["id"]
                    key = f"end_{booking_id}"
                    if key in self.notified_bookings:
                        continue

                    text = (
                        "⚠️ <b>Внимание!</b>\n\n"
                        f"Через {self.notify_time} минут закончится ваше бронирование:\n"
                        f"🚗 Автомобиль: <b>{booking['model']}</b>\n"
                        f"🏷️ Гос. номер: <b>{booking['number_plate']}</b>\n\n"
                        "Завершите поездку в веб-приложении и сделайте финальные фото."
                    )

                    try:
                        msg = await self.bot.send_message(
                            chat_id=booking["telegram_id"],
                            text=text,
                            reply_markup=self._keyboard(booking_id, is_end=True),
                            parse_mode="HTML",
                        )
                        self.notified_bookings[key] = True

                        end_time = booking.get("end_time")
                        if isinstance(end_time, datetime):
                            delete_at = end_time + timedelta(minutes=self.cleanup_grace_minutes)
                            delay = int((delete_at - datetime.now()).total_seconds())
                        else:
                            delay = self.cleanup_grace_minutes * 60

                        asyncio.create_task(
                            self._schedule_delete(booking["telegram_id"], msg.message_id, delay)
                        )
                    except Exception as e:
                        logger.error(f"Error sending end notification for booking {booking_id}: {e}")
            except Exception as e:
                logger.error(f"Error in booking check loop: {e}")

            await asyncio.sleep(self.check_interval)

    async def start(self):
        """Запускает проверку бронирований."""
        logger.info("Starting BookingNotifier service")
        asyncio.create_task(self.check_bookings())
