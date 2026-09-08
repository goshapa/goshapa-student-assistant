# Goshapa Student Assistant

Личный Telegram-бот на Python/aiogram 3, который следит за расписанием, Canvas
LMS assignments и дедлайнами одного пользователя (владельца бота).

Версия для Cloudflare Workers + D1 находится в [cloudflare/](cloudflare/README.md).
Она использует webhook и Cron Triggers; Python-версия ниже запускается на ПК или сервере.

## 1. Установка Python

Нужен Python 3.12+. Проверить версию:

```bash
python --version
```

Если версии нет — установите с [python.org](https://www.python.org/downloads/).

## 2. Создание виртуального окружения

```bash
cd goshapa_student_assistant
python -m venv venv
```

Активация:

- Windows (PowerShell): `venv\Scripts\Activate.ps1`
- Windows (cmd): `venv\Scripts\activate.bat`
- macOS/Linux: `source venv/bin/activate`

## 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

## 4. Создание Telegram-бота и получение BOT_TOKEN

1. Откройте Telegram и напишите [@BotFather](https://t.me/BotFather).
2. Отправьте `/newbot` и следуйте инструкциям.
3. Скопируйте выданный токен вида `123456789:AAExample-Token`.

## 5. Как узнать свой Telegram ID (OWNER_TELEGRAM_ID)

1. Напишите [@userinfobot](https://t.me/userinfobot) в Telegram.
2. Он пришлёт ваш числовой ID — это и есть `OWNER_TELEGRAM_ID`.

## 6. Получение Canvas Access Token

1. Зайдите в Canvas → **Account** → **Settings**.
2. В разделе **Approved Integrations** нажмите **+ New Access Token**.
3. Укажите назначение (например, "Goshapa Student Assistant") и создайте токен.
4. Скопируйте токен — он показывается только один раз.

## 7. CANVAS_BASE_URL

Это адрес вашего Canvas-инстанса без пути, например:

```
https://yourschool.instructure.com
```

## 8. Настройка .env

Скопируйте `.env.example` в `.env`:

```bash
cp .env.example .env
```

И заполните:

```
BOT_TOKEN=ваш_токен_бота
OWNER_TELEGRAM_ID=ваш_telegram_id

CANVAS_BASE_URL=https://yourschool.instructure.com
CANVAS_ACCESS_TOKEN=ваш_canvas_token

TIMEZONE=Asia/Tashkent

MORNING_BRIEFING_TIME=09:00
EVENING_BRIEFING_TIME=21:00

CANVAS_SYNC_INTERVAL_MINUTES=15
```

## 9. Запуск бота

```bash
pip install -r requirements.txt
python bot.py
```

При первом запуске бот создаст базу данных `database/student.db`, разово
засеет реальное расписание и создаст файл логов `logs/bot.log`.

Откройте бота в Telegram и отправьте `/start`.

## 10. Автозапуск

### Windows (Планировщик заданий)

1. Откройте **Task Scheduler** → **Create Task**.
2. Trigger: **At startup** (или при входе в систему).
3. Action: **Start a program**
   - Program: путь к `venv\Scripts\python.exe`
   - Arguments: `bot.py`
   - Start in: папка `goshapa_student_assistant`

### Linux (systemd)

Создайте `/etc/systemd/system/goshapa-bot.service`:

```ini
[Unit]
Description=Goshapa Student Assistant
After=network.target

[Service]
Type=simple
WorkingDirectory=/path/to/goshapa_student_assistant
ExecStart=/path/to/goshapa_student_assistant/venv/bin/python bot.py
Restart=on-failure
User=youruser

[Install]
WantedBy=multi-user.target
```

Затем:

```bash
sudo systemctl enable --now goshapa-bot
```

## Структура проекта

```
goshapa_student_assistant/
├── bot.py                 # точка входа
├── config.py               # переменные окружения
├── scheduler.py             # APScheduler jobs
├── middlewares.py           # проверка OWNER_TELEGRAM_ID
├── handlers/                # обработчики команд/кнопок
├── services/                # Canvas API, синхронизация, напоминания
├── database/                 # ORM-модели, engine, seed, student.db
├── keyboards/                # inline/reply клавиатуры
├── utils/                    # даты, форматирование текста, логирование
├── logs/bot.log               # логи (без токенов)
└── assets/courses/            # баннеры курсов
```

## Логи

Все важные события (запуск, синхронизация Canvas, ошибки, отправленные
напоминания) пишутся в `logs/bot.log`. Токены в логи никогда не попадают.
