from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from handlers.db.database import Database
from typing import Dict
from loguru import logger

router = APIRouter()
security = HTTPBearer()
db: Database = None
templates = None

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict:
    """Проверка токена и получение данных пользователя"""
    try:
        async with db.pool.acquire() as conn:
            user = await conn.fetchrow("""
                SELECT u.id, u.telegram_id, u.full_name, u.phone_number, u.description, u.admin 
                FROM users u
                JOIN tokens t ON u.id = t.user_id
                WHERE t.token = $1 
                AND t.status = 'active'
                AND t.expires_at > NOW()
            """, credentials.credentials)
            
            if not user:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid or expired token",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return dict(user)
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.get("/")
async def root(request: Request):
    """Отображение страницы авторизации"""
    try:
        return templates.TemplateResponse("auth.html", {"request": request})
    except Exception as e:
        logger.error(f"Error rendering auth template: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/verify-token")
async def verify_token_endpoint(token: str = Form(...)):
    """Проверка токена"""
    if not token or not token.strip():
        raise HTTPException(status_code=400, detail="Токен не может быть пустым")
    
    is_valid = await db.verify_token(token.strip())
    if not is_valid:
        raise HTTPException(status_code=401, detail="Неверный или просроченный токен")
    
    return {"status": "success"}

@router.get("/dashboard")
async def dashboard(request: Request):
    """Отображение главной страницы после авторизации"""
    try:
        return templates.TemplateResponse("dashboard.html", {"request": request})
    except Exception as e:
        logger.error(f"Error rendering dashboard template: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/auth/me")
async def get_current_user(user: Dict = Depends(verify_token)) -> Dict:
    """Получение информации о текущем пользователе"""
    return user 

@router.post("/logout")
async def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Выход пользователя из системы"""
    try:
        success = await db.deactivate_token(credentials.credentials)
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Ошибка при выходе из системы"
            )
            
        return {"status": "success", "message": "Выход выполнен успешно"}
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        ) 