from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from handlers.db.database import Database
from api.routes.auth import verify_token
from typing import List, Dict, Optional

router = APIRouter()
db: Database = None

class CarCreate(BaseModel):
    number_plate: str
    model: str

class CarStatus(BaseModel):
    status: str

class CarModelUpdate(BaseModel):
    model: str

class CarNumberUpdate(BaseModel):
    number_plate: str

@router.get("/cars")
async def get_cars(_: Dict = Depends(verify_token)) -> List[Dict]:
    """Получение списка всех автомобилей"""
    cars = await db.get_cars()
    return [dict(car) for car in cars]

@router.post("/cars/add")
async def add_car(car: CarCreate, user: Dict = Depends(verify_token)):
    """Добавление нового автомобиля (только для админов)"""
    try:
        if not user.get('admin'):
            raise HTTPException(
                status_code=403,
                detail="Недостаточно прав для выполнения операции"
            )
            
        success = await db.add_car(car.model, car.number_plate)
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Автомобиль с таким номером уже существует"
            )
            
        return {"status": "success", "message": "Автомобиль успешно добавлен"}
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@router.delete("/cars/{number_plate}/delete")
async def delete_car(number_plate: str, user: Dict = Depends(verify_token)) -> Dict:
    """Отключение автомобиля (устанавливает is_enable=False)"""
    try:
        if not user.get('admin'):
            raise HTTPException(
                status_code=403,
                detail="Недостаточно прав для выполнения операции"
            )
            
        success = await db.disable_car(number_plate)
        if not success:
            raise HTTPException(
                status_code=400, 
                detail="Не удалось отключить автомобиль. Убедитесь, что он существует."
            )
        return {"message": "Автомобиль успешно отключен"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/cars/{number_plate}/enable")
async def enable_car(number_plate: str, user: Dict = Depends(verify_token)) -> Dict:
    """Включение отключенного автомобиля (устанавливает is_enable=True)"""
    try:
        if not user.get('admin'):
            raise HTTPException(
                status_code=403,
                detail="Недостаточно прав для выполнения операции"
            )
            
        success = await db.enable_car(number_plate)
        if not success:
            raise HTTPException(
                status_code=400, 
                detail="Не удалось включить автомобиль. Убедитесь, что он существует."
            )
        return {"message": "Автомобиль успешно включен"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/cars/all")
async def get_all_cars(user: Dict = Depends(verify_token)) -> List[Dict]:
    """Получение списка всех автомобилей, включая отключенные (только для админов)"""
    if not user.get('admin'):
        raise HTTPException(
            status_code=403,
            detail="Недостаточно прав для выполнения операции"
        )
    
    cars = await db.get_all_cars()
    return [dict(car) for car in cars]

@router.put("/cars/{number_plate}/status")
async def update_car_status(
    number_plate: str, status: CarStatus, user: Dict = Depends(verify_token)
) -> Dict:
    """Обновление статуса автомобиля (только для админов)"""
    try:
        if not user.get('admin'):
            raise HTTPException(
                status_code=403,
                detail="Недостаточно прав для выполнения операции"
            )

        car = await db.get_car_by_number(number_plate)
        if not car:
            raise HTTPException(status_code=404, detail="Car not found")
            
        success = await db.update_car_status(car['id'], status.status)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to update car status")
            
        return {"message": "Car status updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/cars/{car_id}/model")
async def update_car_model(
    car_id: int, 
    car_data: CarModelUpdate, 
    user: Dict = Depends(verify_token)
) -> Dict:
    """Обновление модели автомобиля (только для админов)"""
    try:
        if not user.get('admin'):
            raise HTTPException(
                status_code=403,
                detail="Недостаточно прав для выполнения операции"
            )
        
        car = await db.get_car_by_id(car_id)
        if not car:
            raise HTTPException(
                status_code=404,
                detail="Автомобиль не найден"
            )
        
        success = await db.update_car_model(car_id, car_data.model)
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Не удалось обновить модель автомобиля"
            )
        
        return {"message": "Модель автомобиля успешно обновлена"}
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/cars/{car_id}/number")
async def update_car_number(
    car_id: int, 
    car_data: CarNumberUpdate, 
    user: Dict = Depends(verify_token)
) -> Dict:
    """Обновление номера автомобиля (только для админов)"""
    try:
        if not user.get('admin'):
            raise HTTPException(
                status_code=403,
                detail="Недостаточно прав для выполнения операции"
            )
        
        car = await db.get_car_by_id(car_id)
        if not car:
            raise HTTPException(
                status_code=404,
                detail="Автомобиль не найден"
            )
        
        success = await db.update_car_number(car_id, car_data.number_plate)
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Не удалось обновить номер автомобиля. Возможно, такой номер уже существует."
            )
        
        return {"message": "Номер автомобиля успешно обновлен"}
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 