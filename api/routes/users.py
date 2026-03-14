from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from handlers.db.database import Database
from api.routes.auth import verify_token
from typing import List, Dict

router = APIRouter()
db: Database = None

class UserDescription(BaseModel):
    description: str

@router.get("/users")
async def get_users(_: Dict = Depends(verify_token)) -> List[Dict]:
    """Получение списка всех пользователей"""
    users = await db.get_users_list()
    return [dict(user) for user in users]

@router.put("/users/phone/{phone_number}/description")
async def update_user_description_by_phone(
    phone_number: str, description: UserDescription, _: Dict = Depends(verify_token)
) -> Dict:
    """Обновление описания пользователя по номеру телефона"""
    try:
        users = await db.search_users(phone_number)
        if not users:
            raise HTTPException(status_code=404, detail="User not found")
            
        user = users[0]
        success = await db.update_user_description(user['id'], description.description)
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to update user description")
            
        return {"message": "User description updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/users/telegram/{telegram_id}/description")
async def update_user_description_by_telegram(
    telegram_id: int, description: UserDescription, _: Dict = Depends(verify_token)
) -> Dict:
    """Обновление описания пользователя по Telegram ID"""
    try:
        user = await db.get_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        success = await db.update_user_description(user['id'], description.description)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to update user description")
            
        return {"message": "User description updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) 