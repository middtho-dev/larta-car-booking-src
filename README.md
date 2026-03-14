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

> ⚠️ Требование Telegram: для `WebApp` кнопок нужен **HTTPS-домен** (кроме `localhost/127.0.0.1` в режиме разработки).

- 🤖 бот используется только как шлюз в mini app и уведомления (без сценариев бронирования в чате);

- ✅ если пользователь переходит из бота по ссылке `/?token=...` — происходит **автоавторизация**;
- ✅ если пользователь зашел на сайт вручную — есть кнопка **«Авторизация через бота»**;
- ✅ уведомления в Telegram содержат кнопку **«Открыть веб-приложение»**;
- ✅ уведомления автоматически удаляются после поездки (с настраиваемым grace-периодом).

---


## 👑 Как назначить первого администратора

Есть 2 способа:

1. **Через `.env` (автобутстрап при старте бота)**
   - укажи `FIRST_ADMIN_TELEGRAM_ID=<ID>`
   - перезапусти бота
   - важно: пользователь должен хотя бы 1 раз нажать `/start` в боте

2. **Через скрипт вручную**
```bash
python scripts/set_admin.py <telegram_id> on
# снять права:
python scripts/set_admin.py <telegram_id> off
```

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

💡 Быстрые флаги скрипта:

```bash
./scripts/run_local.sh api --skip-install    # если зависимости уже стоят
./scripts/run_local.sh bot --skip-install
./scripts/run_local.sh api --skip-db-check   # только если точно знаете, что делаете
./scripts/run_local.sh api --no-init-db      # не пытаться создавать БД автоматически
./scripts/run_local.sh api --no-auto-db-container  # не поднимать Postgres в Docker автоматически
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
git checkout main
git pull --ff-only origin main

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


## 🔐 HTTPS через Caddy (автосертификаты и автопродление)

Если ты освободил `:443`, самый простой production-вариант — Caddy как reverse proxy.

### Почему Caddy ✅
- автоматически получает сертификат Let's Encrypt;
- автоматически продлевает сертификат;
- не перевыпускает сертификат на каждый запуск (использует сохраненное состояние);
- простая конфигурация и reload без простоя.

### 1) Подготовка

Убедись, что:
- DNS `A`-запись домена (`journal.kv9.ru`) указывает на IP сервера;
- порты 80 и 443 открыты в firewall/security-group;
- приложение запущено локально на `127.0.0.1:8000`.
- если `:80/:443` заняты, останови конфликтующий сервис (`nginx`, `apache2`, другой proxy).

### 2) Автонастройка Caddy (скрипт)

```bash
cd /opt/larta-car-booking-src
sudo ./scripts/setup_caddy.sh journal.kv9.ru 127.0.0.1:8000 admin@kv9.ru
```

Что делает скрипт:
- устанавливает Caddy (если еще не установлен);
- настраивает импорт `/etc/caddy/sites/*.caddy`;
- пишет конфиг сайта `/etc/caddy/sites/larta-car-booking.caddy`;
- валидирует конфиг;
- включает и перезагружает сервис.

### 3) Настройка `.env`

```env
CAR_BOOKING_URL=https://journal.kv9.ru
WEB_APP_URL=https://journal.kv9.ru/dashboard
```

### 4) Проверка

```bash
systemctl status caddy --no-pager
journalctl -u caddy -n 200 --no-pager
curl -I https://journal.kv9.ru
```

Если при установке Caddy видишь ошибку вида `NO_PUBKEY ...`/`repository ... is not signed`, просто обнови скрипт до актуальной версии и запусти его повторно — он перезапишет source с `signed-by` и установит keyring корректно.

### 5) Важно про сертификаты

Caddy хранит сертификаты и состояние ACME здесь:
- `/var/lib/caddy/.local/share/caddy`
- `/var/lib/caddy/.local/state/caddy`

Пока эти директории не удалены, сертификаты **не будут запрашиваться заново при каждом запуске**. Caddy сам обновит их, когда нужно.

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
LOCAL_DB_CONTAINER_NAME=larta-postgres-local
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

# запуск без повторной установки пакетов
./scripts/run_local.sh api --skip-install
```

> Скрипт `./scripts/run_local.sh` теперь сам делает preflight-проверку подключения к БД.
> Если БД недоступна и Docker установлен — скрипт пытается поднять локальный PostgreSQL в контейнере.
> Если контейнер уже был создан с другими логином/паролем, скрипт пересоздает контейнер с текущими значениями из `.env`.
> Если сервер PostgreSQL доступен, но базы нет — скрипт пытается создать `DB_NAME` автоматически.

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

- ❌ **`password authentication failed for user "root"`**
  - это обычно значит, что не подхватились `DB_USER/DB_PASS` из `.env`;
  - убедись, что `.env` лежит в корне проекта и заполнен;
  - в новой версии `run_local.sh` сам загружает `.env` перед preflight-проверкой.

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
