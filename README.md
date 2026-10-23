# Avito Analytics Platform

# https://avito-analytics-demo.onrender.com/

Платформа для аналитики объявлений Avito, работы с сообщениями и автоматизации.
Реализованы авторизация, управление сессиями и простой личный кабинет.
Интеграция с Avito — следующий этап.

## Стек

- **Backend:** Python 3.12, FastAPI, Pydantic 2, pydantic-settings.
- **База данных:** PostgreSQL 16, SQLAlchemy 2, asyncpg, Alembic.
- **Авторизация:** PyJWT, pwdlib с Argon2id.
- **Интерфейс:** HTML, CSS и JavaScript; раздаётся через FastAPI без отдельной сборки.
- **Запуск:** Gunicorn, Uvicorn, Docker Compose.
- **Проверки:** pytest, pytest-asyncio, HTTPX, Ruff.

## Возможности

- Регистрация по email и паролю; хранение хеша пароля.
- Access JWT и refresh-токены; в БД сохраняются только хеши refresh-токенов.
- Независимые сессии для разных входов и проверка их состояния при обращении к API.
- Ротация refresh-токенов с защитой от повторного использования и одновременных запросов.
- Выход из текущей сессии с прекращением доступа по связанным токенам.
- Формы входа и регистрации, приветственная страница и восстановление входа при перезагрузке вкладки.

## API

| Метод | Путь | Назначение |
| --- | --- | --- |
| `GET` | `/health` | Состояние API |
| `POST` | `/api/v1/auth/register` | Регистрация |
| `POST` | `/api/v1/auth/login` | Вход и выдача пары токенов |
| `GET` | `/api/v1/auth/me` | Текущий пользователь |
| `POST` | `/api/v1/auth/refresh` | Обновление токенов |
| `POST` | `/api/v1/auth/logout` | Выход из сессии; HTTP 204 без тела |

## Локальный запуск

Нужны Python 3.12, Docker Compose и `make`. Команды выполняются из корня репозитория.
API запускается в `.venv`, PostgreSQL — в Docker.

```bash
python3.12 -m venv .venv
make install-dev
cp .env.example .env
```

В `.env` задай свои `POSTGRES_PASSWORD` и `JWT_SECRET_KEY`.
Для текущего Compose используются `POSTGRES_HOST=localhost` и `POSTGRES_PORT=5433`.

```bash
make up
DEBUG=false PYTHONPATH=backend .venv/bin/alembic upgrade head
make run
```

Личный кабинет: [http://127.0.0.1:8000/](http://127.0.0.1:8000/).
Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

## Размещение на Render

[Развернуть на Render](https://render.com/deploy?repo=https://github.com/ukupnique/avito-analytics-platform).
Перед этим отправь в GitHub конфигурацию `render.yaml` и остальные изменения.
Она создаёт бесплатное приложение и PostgreSQL, генерирует JWT-ключ и связывает сервисы.
Миграции применяются при запуске. Секреты хранятся в настройках Render.

На бесплатном тарифе приложение засыпает после 15 минут простоя, база истекает через 30 дней.
Подробнее — [ограничения Render](https://render.com/docs/free).

## Проверки

Тесты используют БД из `.env`; нужны запущенный PostgreSQL и применённые миграции.
Отдельный процесс API для тестов не требуется.

```bash
make test
make lint
```

Последний полный прогон: **82 теста прошли**. Форматирование — `make format`, все команды — `make help`.

## Дальнейшее развитие

Интеграция с официальным API Avito, синхронизация объявлений и аналитики,
сообщения и webhooks, фоновые задачи, автоматизация и расширенный frontend на Next.js.
