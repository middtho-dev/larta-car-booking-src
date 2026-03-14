from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from handlers.db.database import Database
from api.routes.auth import verify_token
from typing import List, Dict

router = APIRouter()
db: Database = None


class UserDescription(BaseModel):
    description: str


class UserAdminUpdate(BaseModel):
    admin: bool


@router.get("/users")
async def get_users(_: Dict = Depends(verify_token)) -> List[Dict]:
    """Получение списка всех пользователей"""
    users = await db.get_users_list()
    return [dict(user) for user in users]


@router.get("/users/admin-panel")
async def get_users_for_admin_panel(user: Dict = Depends(verify_token)) -> List[Dict]:
    """Список пользователей для управления правами (только для админов)."""
    if not user.get("admin"):
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    return await db.get_users_for_admin_panel()


@router.put("/users/{user_id}/admin")
async def update_user_admin(user_id: int, payload: UserAdminUpdate, user: Dict = Depends(verify_token)) -> Dict:
    """Изменение админ-прав пользователя (только для админов)."""
    if not user.get("admin"):
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    if user.get("id") == user_id and not payload.admin:
        raise HTTPException(status_code=400, detail="Нельзя снять права администратора у самого себя")

    success = await db.set_user_admin(user_id, payload.admin)
    if not success:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    return {"status": "success", "message": "Роль пользователя обновлена"}


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
