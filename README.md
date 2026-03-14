# Larta Car Booking

Система бронирования автомобилей:
- Telegram-бот для пользователей и админов.
- Web-календарь (FastAPI + Jinja2) для просмотра/управления бронированиями.

## Что улучшено в этом обновлении
- Исправлена логика выборки пользовательских броней (используется `telegram_id`, а не внутренний `id` в неверном формате).
- Добавлена серверная валидация времени бронирования (конец позже начала, запрет создания в прошлом).
- Убрана утечка внутренних исключений в API-ответы (`detail=str(e)` заменено на безопасные сообщения).
- Усилены права на изменение статуса автомобиля (`/api/cars/{number_plate}/status` теперь только для админов).
- В веб-календаре добавлены:
  - toast-уведомления вместо блокирующих `alert`
  - проверка токена до инициализации
  - более безопасная отрисовка данных (экранирование + защита от отсутствующих фото)
  - поиск, фильтр по статусу, кнопка "Сегодня", легенда статусов

---


## Web-first режим (мобильное приложение в браузере)

Текущая версия переведена в **web-first** формат:
- основной сценарий работы — веб-приложение (`/dashboard`), адаптированное под мобильные;
- Telegram остаётся для уведомлений:
  - авторизация по переходу из Telegram выполняется автоматически по токену в ссылке;
  - при обычном входе на сайт доступна кнопка **"Авторизация через бота"**;
  - перед началом поездки,
  - перед завершением поездки,
  - в каждом уведомлении есть кнопка **"Открыть веб-приложение"**;
  - уведомления автоматически удаляются после поездки с grace-периодом.

Для этого используются переменные окружения:
```bash
WEB_APP_URL=https://your-domain.com/dashboard
NOTIFICATION_CLEANUP_GRACE_MINUTES=10
BOT_USERNAME=your_bot_username
CAR_BOOKING_URL=https://your-domain.com
```

---

## Быстрый старт (локально)

### 1) Подготовка окружения
```bash
cp .env.example .env
```
Заполни `.env` своими значениями.

### 2) Запуск API
```bash
./scripts/run_local.sh api
```
API по умолчанию доступен на `http://127.0.0.1:8000`.

### 3) Запуск Telegram-бота
В отдельном терминале:
```bash
./scripts/run_local.sh bot
```

---

## Как обновлять на сервере с GitHub

Предположим, проект находится в `/opt/larta-car-booking-src`.

### Вариант A (простой pull на сервере)
```bash
cd /opt/larta-car-booking-src
git fetch origin
git checkout work        # или твоя production-ветка
git pull --ff-only origin work

# Обновляем зависимости
source .venv/bin/activate
pip install -r requirements.txt

# Перезапуск сервиса API (пример для systemd)
sudo systemctl restart larta-api
sudo systemctl status larta-api --no-pager
```

Если бот тоже как service:
```bash
sudo systemctl restart larta-bot
sudo systemctl status larta-bot --no-pager
```

### Вариант B (через конкретный commit)
```bash
cd /opt/larta-car-booking-src
git fetch origin
git checkout <commit_sha>
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart larta-api
```

---

## Локальная проверка перед деплоем

```bash
# Синтаксис JS
node --check api/static/js/calendar.js

# Проверка Python-модулей
python -m compileall api

# (опционально) запуск API
./scripts/run_local.sh api
```

---

## Типовые проблемы

1. **401 в веб-календаре**
   - Токен истек: получи новый токен через бота.
2. **API не стартует**
   - Проверь `.env` (DB_* и API_* переменные).
3. **Ошибка подключения к БД**
   - Проверь доступ к Postgres и значения `DB_HOST/DB_PORT/DB_USER/DB_PASS/DB_NAME`.
