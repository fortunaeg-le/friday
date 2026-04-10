# Пятница — Telegram Bot

Персональный ежедневник в Telegram с Mini App интерфейсом.

## Функциональность

- **Расписание** — добавление задач с временем, напоминания
- **Проекты и подзадачи** — управление проектами через бота и Mini App
- **Статистика** — процент выполнения, серии, лучшие дни, тепловая карта
- **Тихие дни** — настройка дней без уведомлений (по дням недели или конкретным датам)
- **Вечерняя рефлексия** — ежедневный дневник в 21:00 UTC
- **Экспорт** — выгрузка всей истории в JSON
- **Настройки уведомлений** — управление типами, звуком, временем напоминаний
- **Mini App** — React-интерфейс с 4 вкладками: расписание, статистика, проекты, настройки

## Требования

- Docker и Docker Compose
- Публичный домен с HTTPS (для Telegram webhook)
- Telegram Bot Token ([@BotFather](https://t.me/BotFather))

## Быстрый старт

### 1. Клонировать репозиторий

```bash
git clone <repo_url>
cd friday/friday-bot
```

### 2. Настроить переменные окружения

```bash
cp .env.example .env
```

Отредактировать `.env`:

| Переменная | Описание | Пример |
|---|---|---|
| `BOT_TOKEN` | Токен бота от @BotFather | `123456:ABC-DEF...` |
| `WEBHOOK_URL` | URL вебхука (публичный HTTPS) | `https://example.com/webhook` |
| `WEBHOOK_SECRET` | Секрет для проверки подлинности вебхука | любая случайная строка |
| `DATABASE_URL` | URL подключения к PostgreSQL | `postgresql+asyncpg://user:password@postgres:5432/friday_db` |
| `DEBUG` | Режим отладки (отключает auth middleware) | `false` |
| `DEFAULT_TASK_DURATION` | Длительность задачи по умолчанию (мин) | `30` |
| `MINI_APP_URL` | URL Mini App (для кнопок) | `https://example.com/app` |

### 3. Настроить nginx

Скопировать и настроить конфиг:

```bash
cp nginx.conf.example nginx.conf  # если есть, иначе отредактировать nginx.conf
```

Конфиг должен проксировать `/webhook` и `/api/*` на `app:8000`, а статику Mini App отдавать напрямую.

### 4. Запустить через Docker Compose

```bash
docker compose up -d --build
```

Контейнеры:
- `postgres` — PostgreSQL 15
- `app` — FastAPI + бот (порт 8000)
- `nginx` — nginx + Mini App (порт 80)

### 5. Применить миграции

```bash
docker compose exec app alembic upgrade head
```

### 6. Зарегистрировать команды бота

В [@BotFather](https://t.me/BotFather) → `/setcommands`:

```
start - Открыть Пятницу
add - Добавить задачу
project - Создать проект
projects - Список проектов
stats - Статистика за неделю
quietday - Настроить тихие дни
export - Экспортировать данные
settings - Настройки уведомлений
```

## Структура проекта

```
friday-bot/
├── api/                    # FastAPI приложение
│   ├── main.py             # Точка входа, lifespan, middleware
│   ├── middleware/
│   │   └── auth.py         # HMAC-SHA256 верификация Telegram initData
│   └── routers/            # REST endpoints (/api/tasks, /api/stats, ...)
├── bot/                    # Telegram bot (python-telegram-bot v20)
│   ├── app.py              # Регистрация хендлеров
│   ├── handlers/           # Команды и FSM-хендлеры
│   ├── notifications/      # Отправка уведомлений (утро, напоминания, ...)
│   └── scheduler.py        # APScheduler джобы
├── core/
│   ├── config.py           # Настройки (pydantic-settings)
│   ├── stats.py            # Расчёт статистики
│   └── ai.py               # AI-заглушки (этап 2)
├── db/
│   ├── models.py           # SQLAlchemy ORM модели
│   ├── crud.py             # CRUD операции
│   └── database.py         # Сессия и engine
├── mini_app/               # React + Vite + Tailwind CSS
│   └── src/
│       ├── pages/          # SchedulePage, StatsPage, ProjectsPage, SettingsPage
│       └── api/client.js   # API клиент с Telegram initData заголовком
├── tests/                  # pytest тесты
├── logs/                   # Логи приложения (ротация 10MB × 5)
├── Dockerfile
├── docker-compose.yml
└── alembic/                # Миграции БД
```

## API Endpoints

| Метод | Путь | Описание |
|---|---|---|
| `GET` | `/health` | Проверка работоспособности |
| `GET` | `/api/tasks` | Задачи пользователя |
| `POST` | `/api/tasks` | Создать задачу |
| `PATCH` | `/api/tasks/{id}` | Обновить задачу |
| `DELETE` | `/api/tasks/{id}` | Удалить задачу |
| `GET` | `/api/calendar` | Задачи за период |
| `GET` | `/api/projects` | Проекты пользователя |
| `POST` | `/api/projects` | Создать проект |
| `GET` | `/api/projects/{id}/subtasks` | Подзадачи проекта |
| `POST` | `/api/projects/{id}/subtasks` | Добавить подзадачу |
| `PATCH` | `/api/projects/{id}/subtasks/{sid}` | Обновить статус подзадачи |
| `GET` | `/api/stats` | Статистика (`?period=week\|month\|all`) |
| `GET` | `/api/settings` | Настройки уведомлений |
| `PATCH` | `/api/settings/{type}` | Обновить настройку |
| `POST` | `/webhook` | Telegram webhook (не требует auth) |

Все `/api/*` запросы из Mini App должны включать заголовок:
```
X-Telegram-Init-Data: <initData из window.Telegram.WebApp.initData>
```

## Аутентификация Mini App

Middleware `TelegramAuthMiddleware` проверяет HMAC-SHA256 подпись `initData`:

- Если заголовок `X-Telegram-Init-Data` отсутствует — запрос пропускается (для внутреннего использования)
- Если заголовок присутствует и подпись неверна — `401 Unauthorized`
- В режиме `DEBUG=true` проверка отключена

## Логирование

Логи пишутся одновременно в:
- **stdout** (для Docker / systemd)
- **`logs/friday.log`** (ротация: 10 МБ × 5 файлов)

## Планировщик (APScheduler)

| Джоба | Расписание | Описание |
|---|---|---|
| `check_reminders` | каждую минуту | Отправка напоминаний о задачах |
| `check_completions` | каждую минуту | Проверка выполнения задач |
| `morning_summary` | 08:00 UTC | Утренняя сводка |
| `generate_reminders` | 00:05 UTC | Генерация напоминаний на завтра |
| `window_suggestions` | каждые 30 мин | Предложения задач в свободные окна |
| `evening_reflections` | 21:00 UTC | Запрос вечерней рефлексии |
| `quiet_day_summaries` | 21:30 UTC | Сводка тихого дня |
| `weekly_stats` | вс 20:00 UTC | Еженедельный отчёт |
| `monthly_stats` | 1-е число 20:00 UTC | Ежемесячный отчёт |

## Тесты

```bash
cd friday-bot
pip install -r requirements-dev.txt
pytest tests/ -v
```

## Обновление

```bash
git pull
docker compose up -d --build
docker compose exec app alembic upgrade head
```
