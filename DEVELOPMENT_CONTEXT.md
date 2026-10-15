# Avito Analytics Platform — контекст разработки

## 1. Общая цель
Проект создаётся как учебный/промежуточный Python FastAPI сервис с modular monolith структурой, в котором мы последовательно прошли:
- подготовку репозитория и окружения;
- FastAPI приложение;
- PostgreSQL + SQLAlchemy + Alembic;
- модели/репозитории;
- безопасное хранение паролей;
- регистрацию пользователей;
- тесты и отладку окружения.

## 2. Текущий статус
На текущий момент проект стабилен:
- Python 3.12
- FastAPI работает
- PostgreSQL запускается в Docker через compose
- Alembic настроен и миграции работают
- SQLAlchemy async session настроен корректно
- репозиторий пользователей работает
- хеширование паролей реализовано через Argon2id
- регистрация пользователей реализована и покрыта тестами
- набор pytest проходит (последний прогон: 6 passed)

## 3. Что уже сделано
### Stage 0 — подготовка
- создана структура репозитория
- добавлены .gitignore, .env.example, docker-compose.yml
- создан README/проектный каркас
- создан проектный контекст и дорожная карта
- создан Makefile для очистки мусора

### Stage 1 — FastAPI
- настроен минимальный app/main.py
- добавлены базовые endpoints: / и /health
- приложение запускается в корректной среде

### Stage 2 — PostgreSQL + SQLAlchemy + Alembic
- создана база Postgres в Docker на порту 5433
- настроен async engine и session factory
- базовая модель User создана
- настроены Alembic миграции
- исправлены ошибки с URL БД, target_metadata, и mismatch моделей
- завершена работа с repository layer

### Stage 3 — безопасность и auth
- добавлен password helper
- выбран bcrypt/Argon2id (в финале использован pwdlib[argon2])
- реализована функция хеширования и проверки пароля
- реализован auth_service.register_user
- добавлены проверки на дубликат email
- тесты для паролей, репозитория и auth проходят

## 4. Основные файлы проекта
- backend/app/main.py — entrypoint FastAPI
- backend/app/core/config.py — настройки окружения
- backend/app/core/database.py — async DB engine/session factory
- backend/app/models/base.py — DeclarativeBase
- backend/app/models/user.py — модель User
- backend/app/repositories/user_repository.py — доступ к данным пользователя
- backend/app/core/passwords.py — помощник хеширования/проверки пароля
- backend/app/schemas/user.py — Pydantic схемы
- backend/app/services/auth_service.py — регистрация пользователя
- backend/tests/test_passwords.py — тесты хеширования
- backend/tests/test_user_repository.py — проверка репозитория
- backend/tests/test_auth_service.py — проверка регистрационной логики

## 5. Ключевые решения и уроки
- .env и .env.example — разные вещи, оба нужны
- для локальной разработки лучше использовать отдельный порт Postgres, чтобы не конфликтовать с уже используемым 5432
- Alembic требует не только корректный URL, но и target_metadata
- для async SQLAlchemy нужно корректно использовать session factory
- asyncpg и pytest-asyncio могут ломаться при разных event loop, поэтому нужно использовать session-scoped loop
- публичные Pydantic схемы нельзя возвращать с полем password_hash
- пароль хранится только в виде хеша
- тесты должны очищать созданные данные после себя

## 6. Проблемы, которые уже были решены
- неправильный интерпретатор Python в VS Code
- Import "app.core.config" could not be resolved
- .env отсутствовал или был пустой
- port 5432 already in use
- Alembic default config был неверным
- mismatch между моделью и repository
- duplicate email handling
- event loop issues in async tests
- leftover rows in DB after tests
- warnings about datetime.utcnow deprecation

## 7. Сейчас следующая логическая задача
Нужно переходить к логину и JWT-based auth:
1. login flow
   - поиск пользователя по email
   - проверка пароля через verify_password
   - возврат результата или ошибки
2. JWT token issuance
   - SECRET_KEY
   - ALGORITHM
   - ACCESS_TOKEN_EXPIRE_MINUTES
3. protected endpoints
   - dependency injection по токену
   - текущий пользователь из токена
4. тесты для login и protected access

## 8. Рекомендации для продолжения
- не ломать modular monolith разделение: core / models / repositories / services / schemas
- держать логику хранения пароля отдельно от repository
- писать тесты до новых фич, если они отсутствуют
- проверять запуск через `PYTHONPATH=backend .venv/bin/pytest -q`
- запуск БД через Docker compose перед локальной проверкой сервисов

## 9. Формат дальнейшей работы
- мы идём последовательно по шагам, не прыгая между слоями
- сначала проверяем архитектуру и тесты
- затем добавляем минимальную реализацию
- затем прогоняем реальные проверки
- затем фиксируем результат и его ограничения

## 10. История работы в проекте
- проект был инициализирован и выведен в git
- были исправлены проблемы с окружением и Python interpreter
- настроен Docker/Postgres и локальная БД
- решены проблемы с Alembic и миграциями
- внедрена безопасная регистрация пользователя
- добавлены тесты и проверка реального поведения
- проект стабилен и готов к следующему этапу — login + JWT

## 11. Ссылки на ключевые файлы
- [backend/app/services/auth_service.py](backend/app/services/auth_service.py)
- [backend/app/core/passwords.py](backend/app/core/passwords.py)
- [backend/app/repositories/user_repository.py](backend/app/repositories/user_repository.py)
- [backend/app/models/user.py](backend/app/models/user.py)
- [backend/tests/test_auth_service.py](backend/tests/test_auth_service.py)
- [backend/tests/test_user_repository.py](backend/tests/test_user_repository.py)

## 12. Проверка, которая прошла успешно
Команда проверки:
`cd /home/user88/Downloads/avito_project_context/avito-analytics-platform && PYTHONPATH=backend .venv/bin/pytest -q`

Результат:
`6 passed in 2.14s`

Это подтверждает, что на момент сохранения контекста проект находится в рабочем состоянии и готов к следующему этапу разработки.
