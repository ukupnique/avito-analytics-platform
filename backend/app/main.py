from fastapi import FastAPI

from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.project_version,
    debug=settings.debug,
)


@app.get("/health")
async def health() -> dict:
    """Возвращает статус доступности API, окружение и версию приложения."""
    return {
        "status": "ok",
        "app_env": settings.app_env,
        "version": settings.project_version,
    }


@app.get("/")
async def root() -> dict:
    """Возвращает приветственное сообщение и текущее окружение приложения."""
    return {
        "message": "Avito Analytics Platform is running",
        "app_env": settings.app_env,
    }
