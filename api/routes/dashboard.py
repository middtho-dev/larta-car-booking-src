from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.requests import Request
from typing import Dict, List
import os
import logging

from handlers.db.database import Database
from .auth import verify_token

router = APIRouter()
db = Database()

templates = Jinja2Templates(directory="api/templates")

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, user: Dict = Depends(verify_token)):
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request}
    ) 