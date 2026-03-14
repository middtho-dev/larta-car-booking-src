from datetime import datetime

def parse_datetime(date_str: str) -> datetime:
    """Parse date string in format DD.MM.YYYY HH:MM"""
    try:
        return datetime.strptime(date_str, "%d.%m.%Y %H:%M")
    except ValueError:
        raise ValueError("Неверный формат даты/времени. Используйте DD.MM.YYYY HH:MM") 