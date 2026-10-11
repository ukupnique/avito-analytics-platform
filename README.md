# Avito Analytics Platform

Учебный проект для работы с аккаунтами Avito, аналитикой объявлений, чатами и автоматизацией.

## Стек

- Python
- FastAPI
- PostgreSQL
- SQLAlchemy
- Alembic
- Docker Compose
- Redis (позже)
- Next.js (позже)

## Структура проекта

- `backend/` — backend-приложение
- `docker-compose.yml` — локальная инфраструктура
- `.env.example` — пример переменных окружения

## Локальный запуск

1. Скопируйте переменные окружения:
   ```bash
   cp .env.example .env
   ```

2. Запустите PostgreSQL:
   ```bash
   docker compose up -d db
   ```

3. Проверьте, что база доступна:
   ```bash
   docker compose ps
   ```

## Дальше по roadmap

Сначала мы настроим FastAPI skeleton, затем подключим PostgreSQL, auth и Avito integration.
