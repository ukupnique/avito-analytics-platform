from typing import Literal

from sqlalchemy import URL, make_url

from app.core.config import settings


def get_database_url(driver: Literal["asyncpg", "psycopg"]) -> URL:
    """Формирует URL PostgreSQL для приложения или миграций.

    DATABASE_URL имеет приоритет над отдельными POSTGRES_* настройками.
    URL-объект сохраняет специальные символы пароля без ручного экранирования.
    """
    if settings.database_url:
        url = make_url(settings.database_url)
    else:
        url = URL.create(
            "postgresql",
            username=settings.postgres_user,
            password=settings.postgres_password,
            host=settings.postgres_host,
            port=settings.postgres_port,
            database=settings.postgres_db,
        )

    return url.set(drivername=f"postgresql+{driver}")
