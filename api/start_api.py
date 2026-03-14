from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from handlers.db.database import Database
from api.routes import auth, cars, users, bookings, dashboard, reports
import uvicorn
from loguru import logger
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent.parent

db = Database()

app = FastAPI(
    title="Car Booking API",
    description="API для системы бронирования автомобилей",
    version="1.0.0",
    docs_url=None
)

static_dir = os.path.join(BASE_DIR, "api/static")
photos_dir = os.path.join(BASE_DIR, "photos")
os.makedirs(photos_dir, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")
app.mount("/photos", StaticFiles(directory=photos_dir), name="photos")

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "api/templates"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

auth.db = db
cars.db = db
users.db = db
bookings.db = db
dashboard.db = db
reports.db = db

auth.templates = templates

app.include_router(auth.router, tags=["Авторизация"])
app.include_router(cars.router, prefix="/api", tags=["Автомобили"])
app.include_router(users.router, prefix="/api", tags=["Пользователи"])
app.include_router(bookings.router, prefix="/api", tags=["Бронирования"])
app.include_router(dashboard.router, prefix="/api", tags=["Дашборд"])
app.include_router(reports.router, prefix="/api", tags=["Отчеты"])

@app.on_event("startup")
async def startup():
    """Инициализация подключения к базе данных при запуске"""
    await db.create_pool()
    logger.info("Database connection pool created")

@app.on_event("shutdown")
async def shutdown():
    """Закрытие подключения к базе данных при остановке"""
    if db.pool:
        await db.pool.close()
        logger.info("Database connection pool closed")

if __name__ == "__main__":
    uvicorn.run(
        "api.start_api:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", 8000)),
        reload=True
    ) 