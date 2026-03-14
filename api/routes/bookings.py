from datetime import datetime
from typing import Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.routes.auth import verify_token
from handlers.db.database import Database

router = APIRouter()
db: Database = None

ALLOWED_BOOKING_STATUSES = {"active", "canceled", "completed"}
ALLOWED_ADMIN_UPDATE_STATUSES = {"canceled", "completed"}


class CreateBooking(BaseModel):
    car_id: int
    start_time: datetime
    end_time: datetime


class UpdateBookingStatus(BaseModel):
    status: Literal["canceled", "completed"]


@router.get("/bookings")
async def get_bookings(
    status: Optional[str] = None, user: Dict = Depends(verify_token)
) -> List[Dict]:
    """Получение списка бронирований пользователя."""
    if status and status not in ALLOWED_BOOKING_STATUSES:
        raise HTTPException(status_code=400, detail="Недопустимый фильтр статуса")

    bookings = await db.get_user_bookings(user["telegram_id"])
    booking_dicts = [dict(item) for item in bookings]

    if status:
        return [item for item in booking_dicts if item["status"] == status]
    return booking_dicts


@router.post("/bookings/create")
async def create_booking(booking: CreateBooking, user: Dict = Depends(verify_token)):
    """Создание нового бронирования."""
    try:
        if booking.end_time <= booking.start_time:
            raise HTTPException(
                status_code=400,
                detail="Время окончания должно быть позже времени начала",
            )

        if booking.start_time < datetime.now(booking.start_time.tzinfo):
            raise HTTPException(
                status_code=400,
                detail="Нельзя создать бронирование в прошлом",
            )

        user_data = await db.get_user_by_telegram_id(user["telegram_id"])
        if not user_data:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        if not await db.check_car_availability(booking.car_id, booking.start_time):
            raise HTTPException(
                status_code=400,
                detail="Автомобиль недоступен на указанное время",
            )

        if not await db.check_booking_overlap(
            booking.car_id, booking.start_time, booking.end_time
        ):
            raise HTTPException(
                status_code=400,
                detail="Выбранное время пересекается с другим бронированием",
            )

        success = await db.create_web_booking(
            user_data["id"], booking.car_id, booking.start_time, booking.end_time
        )

        if not success:
            raise HTTPException(status_code=500, detail="Ошибка при создании бронирования")

        return {"status": "success", "message": "Бронирование успешно создано"}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.get("/bookings/active")
async def get_active_bookings(user: Dict = Depends(verify_token)) -> List[Dict]:
    """Получение списка активных бронирований пользователя."""
    bookings = await db.get_user_bookings(user["telegram_id"])
    return [dict(item) for item in bookings if item["status"] == "active"]


@router.get("/bookings/canceled")
async def get_canceled_bookings(user: Dict = Depends(verify_token)) -> List[Dict]:
    """Получение списка отмененных бронирований пользователя."""
    bookings = await db.get_user_bookings(user["telegram_id"])
    return [dict(item) for item in bookings if item["status"] == "canceled"]


@router.get("/bookings/completed")
async def get_completed_bookings(user: Dict = Depends(verify_token)) -> List[Dict]:
    """Получение списка завершенных бронирований пользователя."""
    bookings = await db.get_user_bookings(user["telegram_id"])
    return [dict(item) for item in bookings if item["status"] == "completed"]


@router.get("/bookings/calendar")
async def get_calendar_bookings(_: Dict = Depends(verify_token)) -> List[Dict]:
    """Получение бронирований для календаря с фотографиями."""
    try:
        bookings = await db.get_all_bookings()
        result: List[Dict] = []

        for raw_booking in bookings:
            booking = dict(raw_booking)
            photos = await db.get_booking_photos(booking["id"])

            booking["photos"] = {
                "before": [photo["file_path"] for photo in photos if photo["stage"] == "before"],
                "after": [photo["file_path"] for photo in photos if photo["stage"] == "after"],
            }

            for field in ("start_time", "end_time"):
                value = booking.get(field)
                if isinstance(value, datetime):
                    booking[field] = value.isoformat()
                elif value is not None:
                    booking[field] = str(value)

            result.append(booking)

        return result
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Ошибка при получении данных календаря",
        )


@router.get("/cars/available")
async def get_available_cars(_: Dict = Depends(verify_token)) -> List[Dict]:
    """Получение списка доступных автомобилей."""
    try:
        cars = await db.get_cars()
        return [dict(car) for car in cars if car["status"] != "unavailable"]
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Ошибка при получении списка автомобилей",
        )


@router.put("/bookings/{booking_id}/status")
async def update_booking_status(
    booking_id: int,
    status_update: UpdateBookingStatus,
    user: Dict = Depends(verify_token),
):
    """Обновление статуса бронирования (только для админов)."""
    try:
        if not user.get("admin"):
            raise HTTPException(
                status_code=403,
                detail="Недостаточно прав для выполнения операции",
            )

        if status_update.status not in ALLOWED_ADMIN_UPDATE_STATUSES:
            raise HTTPException(
                status_code=400,
                detail="Недопустимый статус бронирования",
            )

        booking_info = await db.update_booking_status(booking_id, status_update.status)
        if not booking_info:
            raise HTTPException(status_code=404, detail="Бронирование не найдено")

        return {
            "status": "success",
            "message": f"Статус бронирования успешно обновлен на {status_update.status}",
            "booking": booking_info,
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.delete("/bookings/{booking_id}/cancel")
async def cancel_user_booking(booking_id: int, user: Dict = Depends(verify_token)):
    """Отмена бронирования пользователем."""
    try:
        booking_info = await db.get_booking_by_id(booking_id)
        if not booking_info:
            raise HTTPException(status_code=404, detail="Бронирование не найдено")

        if booking_info["user_id"] != user["id"]:
            raise HTTPException(
                status_code=403,
                detail="У вас нет прав на отмену этого бронирования",
            )

        if booking_info["status"] != "active":
            raise HTTPException(
                status_code=400,
                detail="Можно отменить только активные бронирования",
            )

        success = await db.cancel_booking(booking_id)
        if not success:
            raise HTTPException(status_code=500, detail="Не удалось отменить бронирование")

        return {
            "status": "success",
            "message": "Бронирование успешно отменено",
            "booking": booking_info,
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
