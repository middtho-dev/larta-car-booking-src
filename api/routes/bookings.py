from fastapi import APIRouter, Depends, HTTPException
from handlers.db.database import Database
from api.routes.auth import verify_token
from typing import List, Dict, Optional
from datetime import datetime
from pydantic import BaseModel

router = APIRouter()
db: Database = None

class CreateBooking(BaseModel):
    car_id: int
    start_time: datetime
    end_time: datetime

class UpdateBookingStatus(BaseModel):
    status: str

@router.get("/bookings")
async def get_bookings(
    status: Optional[str] = None, user: Dict = Depends(verify_token)
) -> List[Dict]:
    """
    Получение списка бронирований
    
    При указании status возвращаются только бронирования с указанным статусом
    """
    bookings = await db.get_user_bookings(user['id'])
    
    if status:
        return [dict(b) for b in bookings if b['status'] == status]
    return [dict(b) for b in bookings]

@router.post("/bookings/create")
async def create_booking(booking: CreateBooking, user: Dict = Depends(verify_token)):
    """Создание нового бронирования"""
    try:
        user_data = await db.get_user_by_telegram_id(user['telegram_id'])
        if not user_data:
            raise HTTPException(
                status_code=404,
                detail="Пользователь не найден"
            )
            
        if not await db.check_car_availability(booking.car_id, booking.start_time):
            raise HTTPException(
                status_code=400,
                detail="Автомобиль недоступен на указанное время"
            )
            
        if not await db.check_booking_overlap(booking.car_id, booking.start_time, booking.end_time):
            raise HTTPException(
                status_code=400,
                detail="Выбранное время пересекается с другим бронированием"
            )
            
        success = await db.create_web_booking(user_data['id'], booking.car_id, booking.start_time, booking.end_time)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Ошибка при создании бронирования"
            )
            
        return {"status": "success", "message": "Бронирование успешно создано"}
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@router.get("/bookings/active")
async def get_active_bookings(user: Dict = Depends(verify_token)) -> List[Dict]:
    """Получение списка активных бронирований"""
    bookings = await db.get_user_bookings(user['id'])
    return [dict(b) for b in bookings if b['status'] == 'active']

@router.get("/bookings/canceled")
async def get_canceled_bookings(user: Dict = Depends(verify_token)) -> List[Dict]:
    """Получение списка отмененных бронирований"""
    bookings = await db.get_user_bookings(user['id'])
    return [dict(b) for b in bookings if b['status'] == 'canceled']

@router.get("/bookings/completed")
async def get_completed_bookings(user: Dict = Depends(verify_token)) -> List[Dict]:
    """Получение списка завершенных бронирований"""
    bookings = await db.get_user_bookings(user['id'])
    return [dict(b) for b in bookings if b['status'] == 'completed']

@router.get("/bookings/calendar")
async def get_calendar_bookings(user: Dict = Depends(verify_token)) -> List[Dict]:
    """Получение бронирований для календаря с фотографиями"""
    try:
        bookings = await db.get_all_bookings()
        
        for booking in bookings:
            photos = await db.get_booking_photos(booking['id'])
            
            booking['photos'] = {
                'before': [f"{photo['file_path']}"
                          for photo in photos if photo['stage'] == 'before'],
                'after': [f"{photo['file_path']}"
                         for photo in photos if photo['stage'] == 'after']
            }
            
            booking['start_time'] = datetime.fromisoformat(str(booking['start_time'])).isoformat()
            booking['end_time'] = datetime.fromisoformat(str(booking['end_time'])).isoformat()
            
        return bookings
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Ошибка при получении данных календаря"
        )

@router.get("/cars/available")
async def get_available_cars(user: Dict = Depends(verify_token)) -> List[Dict]:
    """Получение списка доступных автомобилей"""
    try:
        cars = await db.get_cars()
        return [dict(car) for car in cars if car['status'] != 'unavailable']
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Ошибка при получении списка автомобилей"
        )

@router.put("/bookings/{booking_id}/status")
async def update_booking_status(
    booking_id: int,
    status_update: UpdateBookingStatus,
    user: Dict = Depends(verify_token)
):
    """Обновление статуса бронирования (только для админов)"""
    try:
        if not user.get('admin'):
            raise HTTPException(
                status_code=403,
                detail="Недостаточно прав для выполнения операции"
            )
            
        if status_update.status not in ['canceled', 'completed']:
            raise HTTPException(
                status_code=400,
                detail="Недопустимый статус бронирования"
            )
            
        booking_info = await db.update_booking_status(booking_id, status_update.status)
        
        if not booking_info:
            raise HTTPException(
                status_code=404,
                detail="Бронирование не найдено"
            )
            
        status_text = "завершил" if status_update.status == "completed" else "отменил"
        notification_text = (
            f"ℹ️ Администратор {status_text} ваше бронирование:\n"
            f"🚗 Автомобиль: {booking_info['model']}\n"
            f"🔢 Гос. номер: {booking_info['number_plate']}"
        )
        
        
        return {
            "status": "success",
            "message": f"Статус бронирования успешно обновлен на {status_update.status}",
            "booking": booking_info
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@router.delete("/bookings/{booking_id}/cancel")
async def cancel_user_booking(booking_id: int, user: Dict = Depends(verify_token)):
    """Отмена бронирования пользователем"""
    try:

        booking_info = await db.get_booking_by_id(booking_id)
        
        if not booking_info:
            raise HTTPException(
                status_code=404,
                detail="Бронирование не найдено"
            )
            
        if booking_info['user_id'] != user['id']:
            raise HTTPException(
                status_code=403,
                detail="У вас нет прав на отмену этого бронирования"
            )

        if booking_info['status'] != 'active':
            raise HTTPException(
                status_code=400,
                detail="Можно отменить только активные бронирования"
            )
            

        success = await db.cancel_booking(booking_id)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Не удалось отменить бронирование"
            )
            
        return {
            "status": "success",
            "message": "Бронирование успешно отменено",
            "booking": booking_info
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        ) 