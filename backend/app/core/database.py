from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings

DATABASE_URL = (
    f"postgresql+asyncpg://{settings.postgres_user}:{settings.postgres_password}"
    f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
)

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionFactory = async_sessionmaker(bind=engine, expire_on_commit=False)