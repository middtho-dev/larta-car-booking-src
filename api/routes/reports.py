from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, List
from datetime import datetime
from fastapi.responses import StreamingResponse
import pandas as pd
import io
import logging
from urllib.parse import quote

from handlers.db.database import Database
from .auth import verify_token

router = APIRouter()
db = Database()

@router.get("/reports/monthly/{year}/{month}")
async def get_monthly_report(
    year: int, 
    month: int, 
    user: Dict = Depends(verify_token)
) -> List[Dict]:
    """
    Получение отчета о бронированиях за указанный месяц и год
    
    Доступ только для админов.
    Параметры:
    - year: год в формате YYYY
    - month: месяц в формате MM (1-12)
    """
    if not user.get('admin'):
        raise HTTPException(
            status_code=403,
            detail="Недостаточно прав для получения отчета"
        )
    
    if year < 2000 or year > 2100:
        raise HTTPException(
            status_code=400,
            detail="Некорректный год (должен быть от 2000 до 2100)"
        )
    
    if month < 1 or month > 12:
        raise HTTPException(
            status_code=400,
            detail="Некорректный месяц (должен быть от 1 до 12)"
        )
    
    try:
        report = await db.get_month_report(year, month)
        
        for booking in report:
            booking['start_time'] = datetime.fromisoformat(str(booking['start_time'])).isoformat()
            booking['end_time'] = datetime.fromisoformat(str(booking['end_time'])).isoformat()
        
        return report
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при получении отчета: {str(e)}"
        )

@router.get("/reports/monthly/{year}/{month}/excel")
async def get_monthly_report_excel(
    year: int, 
    month: int, 
    user: Dict = Depends(verify_token)
):
    """
    Получение отчета о бронированиях за указанный месяц и год в формате Excel
    
    Доступ только для админов.
    Параметры:
    - year: год в формате YYYY
    - month: месяц в формате MM (1-12)
    """
    try:
        if not user.get('admin'):
            raise HTTPException(
                status_code=403,
                detail="Недостаточно прав для получения отчета"
            )
        
        if year < 2000 or year > 2100:
            raise HTTPException(
                status_code=400,
                detail="Некорректный год (должен быть от 2000 до 2100)"
            )
        
        if month < 1 or month > 12:
            raise HTTPException(
                status_code=400,
                detail="Некорректный месяц (должен быть от 1 до 12)"
            )
        
        logging.info(f"Получаем отчет за {month}/{year}")
        report = await db.get_month_report(year, month)
        logging.info(f"Получены данные: {report}")
        
        month_names = [
            "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
            "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
        ]
        month_name = month_names[month - 1]
        
        if not report:
            logging.info("Нет данных для отчета, создаем пустой DataFrame")
            df = pd.DataFrame(columns=[
                "Клиент", "Телефон", "Автомобиль", "Номер", 
                "Начало", "Окончание", "Статус"
            ])
        else:
            logging.info("Создаем DataFrame из данных")
            df = pd.DataFrame(report)
            df = df.rename(columns={
                'user_name': 'Клиент',
                'user_phone': 'Телефон',
                'car_model': 'Автомобиль',
                'car_plate': 'Номер',
                'start_time': 'Начало',
                'end_time': 'Окончание',
                'booking_status': 'Статус'
            })
            
            logging.info("Форматируем даты")
            for date_column in ['Начало', 'Окончание']:
                df[date_column] = pd.to_datetime(df[date_column]).dt.strftime('%d.%m.%Y, %H:%M:%S')
            
            status_mapping = {
                'active': 'Активно',
                'completed': 'Завершено',
                'canceled': 'Отменено'
            }
            df['Статус'] = df['Статус'].map(lambda x: status_mapping.get(x, x))
        
        logging.info("Создаем Excel файл")
        output = io.BytesIO()
        sheet_name = f"{month_name} {year}"
        
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            
            workbook = writer.book
            worksheet = writer.sheets[sheet_name]
            
            header_format = workbook.add_format({
                'bold': True,
                'text_wrap': True,
                'valign': 'top',
                'fg_color': '#D7E4BC',
                'border': 1
            })
            
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
                
            for i, column in enumerate(df.columns):
                column_width = max(df[column].astype(str).map(len).max(), len(column))
                worksheet.set_column(i, i, column_width * 1.1)
        
        output.seek(0)
        logging.info("Отдаем файл")
        
        filename = f"Report_booking_{month_name}_{year}.xlsx"
        encoded_filename = quote(filename)
        
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{encoded_filename}"; filename*=UTF-8\'\'{encoded_filename}'
            }
        )
        
    except Exception as e:
        logging.error(f"Ошибка при формировании Excel-отчета: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при формировании Excel-отчета: {str(e)}"
        ) 