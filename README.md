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

## Команды разработки

Запускайте команды из директории `avito-analytics-platform`.
Используется Python из `.venv`, поэтому активировать окружение отдельно не нужно.
Если окружение ещё не создано, выполните `python3.12 -m venv .venv`.

Один раз установите зависимости разработки, включая Ruff:

```bash
make install-dev
```

| Команда | Назначение |
| --- | --- |
| `make format` | Автоматически исправить форматирование и порядок импортов в backend и миграциях |
| `make lint` | Проверить Python-код линтером Ruff |
| `make up` | Запустить все сервисы Docker Compose и дождаться их готовности |
| `make stop` | Остановить контейнеры, сохранив их для следующего запуска |
| `make down` | Остановить и удалить контейнеры и сеть; данные PostgreSQL сохраняются |
| `make test` | Запустить все тесты pytest; перед этим запустите БД через `make up` |
| `make clean` | Удалить генерируемые кэши и артефакты Python |
| `make help` | Показать доступные команды |

Тесты запускаются с `DEBUG=false`, чтобы настройки debug в окружении shell
не влияли на их запуск.

Для запуска отдельных тестов передайте аргументы pytest:

```bash
make test PYTEST_ARGS="backend/tests/test_auth_service.py -k authenticate"
```

Для форматирования одного файла можно указать его путь:

```bash
make format PYTHON_PATHS=backend/app/services/auth_service.py
```

## Дальше по roadmap

Сначала мы настроим FastAPI skeleton, затем подключим PostgreSQL, auth и Avito integration.
