# 🚗 Larta Car Booking

> Современная система бронирования автомобилей: **web-first приложение** + **Telegram-бот для уведомлений**.

---

## ✨ Что это за проект

Larta Car Booking состоит из двух частей:

- 🌐 **Web-приложение (FastAPI + Jinja2)**
  - календарь бронирований
  - управление статусами
  - админские действия
  - адаптация под мобильные
- 🤖 **Telegram-бот (aiogram)**
  - выдача токена/ссылки на веб
  - уведомления перед началом/окончанием аренды
  - кнопка перехода в веб-приложение в уведомлениях

---

## 🧭 Режим работы (web-first)

Основной UX — через веб (`/dashboard`). Telegram используется как канал уведомлений и входа:

- ✅ если пользователь переходит из бота по ссылке `/?token=...` — происходит **автоавторизация**;
- ✅ если пользователь зашел на сайт вручную — есть кнопка **«Авторизация через бота»**;
- ✅ уведомления в Telegram содержат кнопку **«Открыть веб-приложение»**;
- ✅ уведомления автоматически удаляются после поездки (с настраиваемым grace-периодом).

---

## 📦 Установка с GitHub (Production)

Ниже — «боевой» сценарий на Linux-сервере.

### 1) Подготовка сервера

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip
```

Убедись, что PostgreSQL уже установлен и доступен.

---

### 2) Клонирование проекта

```bash
cd /opt
sudo git clone <YOUR_GITHUB_REPO_URL> larta-car-booking-src
sudo chown -R $USER:$USER /opt/larta-car-booking-src
cd /opt/larta-car-booking-src
```

---

### 3) Настройка окружения

```bash
cp .env.example .env
```

Заполни `.env` (минимум):

- 🤖 `BOT_TOKEN`
- 🤖 `BOT_USERNAME`
- 🔐 `ACCESS_PASSWORD`
- 🛢️ `DB_USER`, `DB_PASS`, `DB_HOST`, `DB_PORT`, `DB_NAME`
- 🌐 `API_HOST`, `API_PORT`
- 🔗 `CAR_BOOKING_URL` (например `https://cars.example.com`)
- 🔗 `WEB_APP_URL` (например `https://cars.example.com/dashboard`)
- 🔔 `NOTIFICATION_CLEANUP_GRACE_MINUTES`, `CHECK_INTERVAL`, `NOTIFY_TIME`

---

### 4) Установка зависимостей

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

### 5) Проверка запуска вручную

```bash
# API
./scripts/run_local.sh api

# в отдельной сессии/вкладке
./scripts/run_local.sh bot
```

---

### 6) Запуск как systemd-сервисы (рекомендуется)

#### `larta-api.service`

Создай файл `/etc/systemd/system/larta-api.service`:

```ini
[Unit]
Description=Larta Car Booking API
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/larta-car-booking-src
EnvironmentFile=/opt/larta-car-booking-src/.env
ExecStart=/opt/larta-car-booking-src/.venv/bin/python -m api.start_api
Restart=always
RestartSec=3
User=www-data
Group=www-data

[Install]
WantedBy=multi-user.target
```

#### `larta-bot.service`

Создай файл `/etc/systemd/system/larta-bot.service`:

```ini
[Unit]
Description=Larta Car Booking Telegram Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/larta-car-booking-src
EnvironmentFile=/opt/larta-car-booking-src/.env
ExecStart=/opt/larta-car-booking-src/.venv/bin/python main.py
Restart=always
RestartSec=3
User=www-data
Group=www-data

[Install]
WantedBy=multi-user.target
```

Запуск:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now larta-api
sudo systemctl enable --now larta-bot

sudo systemctl status larta-api --no-pager
sudo systemctl status larta-bot --no-pager
```

---

### 7) Обновление с GitHub в Production

```bash
cd /opt/larta-car-booking-src
git fetch origin
git checkout work            # или твоя prod-ветка
git pull --ff-only origin work

source .venv/bin/activate
pip install -r requirements.txt

sudo systemctl restart larta-api
sudo systemctl restart larta-bot
```

Проверка логов:

```bash
journalctl -u larta-api -n 200 --no-pager
journalctl -u larta-bot -n 200 --no-pager
```

---

## 🧪 Тестовый режим (Staging / локальная отладка)

Рекомендуется отдельная БД и отдельный `.env`.

### Вариант A: локально на машине разработчика

```bash
git clone <YOUR_GITHUB_REPO_URL>
cd larta-car-booking-src
cp .env.example .env
# заполни тестовыми значениями

./scripts/run_local.sh api
./scripts/run_local.sh bot
```

### Вариант B: staging на сервере в отдельной папке

```bash
cd /opt
git clone <YOUR_GITHUB_REPO_URL> larta-car-booking-staging
cd larta-car-booking-staging
cp .env.example .env
# проставь staging-домен/бот/БД

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Рекомендуемые staging-настройки:

- `DB_NAME=car_booking_staging`
- `API_PORT=8001`
- отдельный Telegram-бот токен
- отдельный домен/поддомен (например `staging-cars.example.com`)

---

## ⚙️ Пример ключевых переменных `.env`

```env
BOT_TOKEN=...
BOT_USERNAME=your_bot_username
ACCESS_PASSWORD=...

DB_USER=postgres
DB_PASS=postgres
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=car_booking

API_HOST=0.0.0.0
API_PORT=8000

CAR_BOOKING_URL=https://cars.example.com
WEB_APP_URL=https://cars.example.com/dashboard

CHECK_INTERVAL=60
NOTIFY_TIME=1
NOTIFICATION_CLEANUP_GRACE_MINUTES=10
TIMEZONE=UTC
```

---


## 🧪 Проверка окружения перед первым запуском

Перед запуском API/бота убедись:

- ✅ PostgreSQL запущен;
- ✅ База `DB_NAME` существует;
- ✅ В `.env` корректные `DB_*`;
- ✅ Порт БД доступен.

Полезные команды:

```bash
sudo systemctl status postgresql --no-pager
sudo -u postgres psql -c "\l"
sudo -u postgres psql -c "CREATE DATABASE car_booking;"   # если еще нет
```

> Скрипт `./scripts/run_local.sh` теперь сам делает preflight-проверку подключения к БД и печатает понятные подсказки.

---

## ✅ Быстрые проверки перед релизом

```bash
node --check api/static/js/calendar.js
python -m compileall api handlers main.py
```

---

## 🛠️ Troubleshooting

- ❌ **401 в веб-календаре**
  - токен истек, получи новый через бота;
  - проверь корректность `CAR_BOOKING_URL` и `BOT_USERNAME`.

- ❌ **API не поднимается**
  - проверь `.env`;
  - проверь статус PostgreSQL: `sudo systemctl status postgresql`;
  - посмотри `journalctl -u larta-api`.

- ❌ **Бот не отправляет уведомления**
  - проверь `BOT_TOKEN`;
  - проверь, что бот запущен и доступен интернет;
  - проверь `WEB_APP_URL` (кнопки в уведомлениях).

- ❌ **Ошибка БД**
  - проверь доступ к PostgreSQL и учетные данные;
  - проверь, что нужная база существует.

---

## 💡 Полезные команды

```bash
# Статус сервисов
sudo systemctl status larta-api larta-bot --no-pager

# Перезапуск
sudo systemctl restart larta-api larta-bot

# Логи
journalctl -u larta-api -f
journalctl -u larta-bot -f
```
