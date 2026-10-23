from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.database_url import get_database_url

DATABASE_URL = get_database_url("asyncpg")

engine = create_async_engine(DATABASE_URL, echo=settings.debug, pool_pre_ping=True)
AsyncSessionFactory = async_sessionmaker(bind=engine, expire_on_commit=False)
