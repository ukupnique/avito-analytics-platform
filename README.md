# Avito Analytics Platform

Учебно-практический проект платформы для работы с аккаунтами Avito, аналитикой
объявлений, сообщениями и автоматизацией. Разработка идёт небольшими этапами:
сначала backend и авторизация, затем интеграция с Avito и пользовательский интерфейс.

## Текущее состояние

Реализовано:

- FastAPI-приложение с настройками через `pydantic-settings` и `.env`.
- PostgreSQL в Docker Compose, асинхронный доступ через SQLAlchemy и миграции Alembic.
- Регистрация по email и паролю с проверкой занятости email.
- Хеширование паролей Argon2id через `pwdlib` и проверка пароля при входе.
- Выдача access JWT с полями `sub` и `exp`, проверка подписи, алгоритма и срока действия.
- Защищённый endpoint `/api/v1/auth/me`, который возвращает текущего пользователя.
- Таблицы `users`, `auth_sessions` и `refresh_tokens`.
- Репозитории для создания и поиска пользователей, сессий входа и записей refresh-токенов.
- Отзыв сессии на уровне репозитория с сохранением времени первого отзыва.
- Тесты функций, сервисов, репозиториев и HTTP API; Ruff и команды разработки в Makefile.

Сейчас идёт переход к схеме **access token + refresh token**. Для неё уже подготовлено
хранилище: отдельные сессии входа, хеши refresh-токенов и поля `revoked_at` / `used_at`.
Текущий `/login` выдаёт только access JWT; создание сессии входа при логине,
проверка её состояния в API, обновление токенов и `/logout` — следующие задачи.

## Стек

- Python **3.12** — версия ограничена в `backend/pyproject.toml`.
- FastAPI, Pydantic и pydantic-settings.
- PostgreSQL 16, SQLAlchemy, asyncpg для приложения и psycopg для миграций.
- Alembic для управления схемой БД.
- PyJWT для access-токенов, pwdlib с Argon2 для паролей.
- Gunicorn с ASGI-воркером Uvicorn для локального запуска API.
- pytest, pytest-asyncio и HTTPX для тестов; Ruff для линтинга и форматирования.
- Docker Compose для локальной БД.

## Структура проекта

```text
backend/
  app/
    main.py          — FastAPI-приложение и подключение маршрутов
    api/             — HTTP-маршруты и зависимость get_current_user
    core/            — настройки, подключение к БД, пароли и JWT
    models/          — SQLAlchemy-модели пользователей, сессий и refresh-токенов
    schemas/         — Pydantic-схемы запросов и ответов
    repositories/    — операции с записями БД
    services/        — регистрация и проверка учётных данных
  tests/             — тесты функций, сервисов, репозиториев и API
  pyproject.toml     — зависимости и настройки Ruff
alembic/
  versions/          — история миграций
  env.py             — подключение моделей и БД к Alembic
alembic.ini          — конфигурация Alembic
docker-compose.yml   — PostgreSQL и постоянный том с данными
Makefile             — команды разработки
.env.example         — шаблон настроек
```

`AuthSession` — запись об отдельном входе пользователя в таблице `auth_sessions`.
`AsyncSession` — объект SQLAlchemy для обращения к БД. Репозитории получают его
от вызывающего кода; фиксация транзакции через `commit()` остаётся вызывающему коду.

## Локальный запуск

Нужны Python 3.12, Docker с Docker Compose и `make`. Все команды выполняются
из корня репозитория `avito-analytics-platform`.

Backend запускается из локального `.venv`; Docker Compose сейчас поднимает PostgreSQL.

1. Создай виртуальное окружение и установи зависимости разработки:

    ```bash
    python3.12 -m venv .venv
    make install-dev
    ```

2. При первом запуске создай файл настроек:

    ```bash
    cp .env.example .env
    ```

    Укажи в `.env` свои значения `POSTGRES_PASSWORD` и `JWT_SECRET_KEY`.
    Для генерации секретного ключа можно использовать стандартный модуль
    [secrets](https://docs.python.org/3.12/library/secrets.html#generating-tokens):

    ```bash
    .venv/bin/python -c 'import secrets; print(secrets.token_hex(32))'
    ```

    Полученную строку запиши в `JWT_SECRET_KEY`.

3. Запусти БД и дождись её готовности:

    ```bash
    make up
    ```

    В текущем Compose PostgreSQL доступен приложению по `localhost:5433`.
    Состояние контейнера можно посмотреть через `docker compose ps`.

4. Примени миграции:

    ```bash
    DEBUG=false PYTHONPATH=backend .venv/bin/alembic upgrade head
    ```

5. Запусти API:

    ```bash
    make run
    ```

Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).
Проверка доступности API: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health).
Остановка API — `Ctrl+C` в терминале с `make run`.

Если порт API занят:

```bash
make run API_PORT=8001
```

После первоначальной настройки для обычного запуска достаточно `make up` и `make run`.
Новые миграции применяются через `alembic upgrade head` после их появления в проекте.

## Настройки

Настройки приложения описаны в `backend/app/core/config.py`, пример значений — в
`.env.example`. Файл `.env` читается из корня репозитория.

| Переменная | Назначение |
| --- | --- |
| `APP_ENV` | Название окружения; для локальной работы — `local` |
| `POSTGRES_HOST` | Адрес БД; для приложения на хосте — `localhost` |
| `POSTGRES_PORT` | Порт БД на хосте; в текущем Compose — `5433` |
| `POSTGRES_DB` | Имя базы данных |
| `POSTGRES_USER` | Пользователь PostgreSQL |
| `POSTGRES_PASSWORD` | Пароль PostgreSQL |
| `JWT_SECRET_KEY` | Обязательный секретный ключ подписи JWT |
| `JWT_ALGORITHM` | Алгоритм подписи; по умолчанию `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Время жизни access JWT; по умолчанию 30 минут |

`make run` и `make test` задают `DEBUG=false` и `PYTHONPATH=backend`.
Те же значения используются в приведённых командах Alembic, чтобы импортировать
пакет `app` и запускаться с корректным значением `DEBUG` независимо от настроек shell.

## Доступное API

| Метод | Путь | Назначение |
| --- | --- | --- |
| `GET` | `/` | Сообщение о запуске приложения |
| `GET` | `/health` | Статус API, окружение и версия |
| `POST` | `/api/v1/auth/register` | Регистрация; HTTP 201 с `id` и `email` |
| `POST` | `/api/v1/auth/login` | Проверка email и пароля; access JWT и `token_type: bearer` |
| `GET` | `/api/v1/auth/me` | Данные текущего пользователя по Bearer-токену |

Для ручной проверки в Swagger UI:

1. Выполни `POST /api/v1/auth/register` с тестовыми данными:

    ```json
    {
      "email": "developer@example.com",
      "password": "example-password"
    }
    ```

2. Выполни `POST /api/v1/auth/login` с теми же данными.
3. Скопируй `access_token` из ответа и укажи его через кнопку **Authorize**.
4. Выполни `GET /api/v1/auth/me`.

Для запросов вне Swagger передавай заголовок `Authorization: Bearer <access_token>`.

Повторная регистрация email возвращает HTTP 409, неверные учётные данные при входе —
HTTP 401, некорректные входные данные — HTTP 422. `/me` возвращает HTTP 401 при
отсутствующем, повреждённом или просроченном токене, неверной подписи и удалённом пользователе.

## Тесты

Для интеграционных тестов нужна запущенная БД с применёнными миграциями.
Они подключаются к БД из `.env`, создают уникальные тестовые данные и очищают их
в `finally`. API-тесты используют HTTPX с ASGI-приложением, поэтому отдельный
процесс `make run` для тестов не требуется.

Запуск всех тестов из другого терминала:

```bash
make up
make test
```

Проверяются:

- Хеширование паролей, проверка пароля и уникальность соли.
- Регистрация, повторный email и неверные учётные данные.
- Создание и проверка JWT, срок действия, обязательные поля, подпись и алгоритм.
- HTTP API регистрации, входа и `/me`, включая ошибки валидации и авторизации.
- Сохранение пользователей, сессий и хешей refresh-токенов с чтением через новую сессию БД.
- Отзыв сессии, сохранение первого времени при повторном отзыве и отсутствующая запись.

Отдельный файл или тест можно выбрать через аргументы pytest:

```bash
make test PYTEST_ARGS="backend/tests/test_auth_session_repository.py"
make test PYTEST_ARGS="backend/tests/test_auth_session_repository.py -k revoke"
```

## Команды разработки

Команды используют Python из `.venv`, отдельно активировать окружение не нужно.

| Команда | Назначение |
| --- | --- |
| `make install-dev` | Установить приложение и зависимости разработки в `.venv` |
| `make format` | Исправить порядок импортов и форматирование backend и миграций |
| `make lint` | Проверить Python-код линтером Ruff |
| `make up` | Запустить сервисы Compose и дождаться их готовности |
| `make stop` | Остановить контейнеры, сохранив их для следующего запуска |
| `make down` | Удалить контейнеры и сеть; том с данными PostgreSQL сохраняется |
| `make run` | Запустить API через Gunicorn и Uvicorn с перезагрузкой при изменении кода |
| `make test` | Запустить pytest |
| `make clean` | Удалить генерируемые кэши и артефакты Python |
| `make help` | Показать доступные команды |

Для форматирования одного файла:

```bash
make format PYTHON_PATHS=backend/tests/test_auth_session_repository.py
```

## Миграции

Текущая версия схемы и проверка соответствия моделям:

```bash
DEBUG=false PYTHONPATH=backend .venv/bin/alembic current
DEBUG=false PYTHONPATH=backend .venv/bin/alembic check
```

После изменения моделей создай миграцию:

```bash
DEBUG=false PYTHONPATH=backend .venv/bin/alembic revision --autogenerate -m "describe schema change"
```

Проверь изменения в `upgrade()` и `downgrade()`, затем примени миграцию:

```bash
DEBUG=false PYTHONPATH=backend .venv/bin/alembic upgrade head
```

Подробнее о генерации и проверке миграций — в
[документации Alembic](https://alembic.sqlalchemy.org/en/latest/autogenerate.html).

## Следующие шаги

Ближайшая задача — заполнение `RefreshToken.used_at` при использовании токена и тесты этого метода.

Затем завершаем авторизацию:

1. Генерация секретного refresh-токена и его хеша, настройки времени жизни.
2. Создание сессии и refresh-токена при `/login` в одной транзакции; добавление `sid` в access JWT.
3. Проверка владельца, срока действия и отзыва сессии в `get_current_user()`.
4. `/refresh` с заменой использованного токена новым, обработкой повторного использования
   и одновременных запросов. Повторное использование старого токена отзывает связанную сессию.
5. `/logout`, который отзывает сессию и прекращает доступ по связанным токенам.
6. Тесты полного цикла входа, обновления токенов и выхода.

Дальнейшие этапы проекта: интеграция с официальным API Avito, синхронизация объявлений,
накопление аналитики, сообщения и webhooks, Redis с фоновыми задачами, автоматизация
и frontend на Next.js. AI-функции и база знаний рассматриваются как последующие этапы.
