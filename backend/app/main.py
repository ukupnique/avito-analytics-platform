from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.auth import router as auth_router
from app.core.config import settings

WEB_DIRECTORY = Path(__file__).resolve().parent / "web"

app = FastAPI(
    title=settings.app_name,
    version=settings.project_version,
    debug=settings.debug,
)

app.include_router(auth_router, prefix="/api/v1")
app.mount("/assets", StaticFiles(directory=WEB_DIRECTORY), name="web-assets")


@app.get("/health")
async def health() -> dict:
    """Возвращает статус доступности API, окружение и версию приложения."""
    return {
        "status": "ok",
        "app_env": settings.app_env,
        "version": settings.project_version,
    }


@app.get("/", include_in_schema=False)
async def root() -> FileResponse:
    """Возвращает интерфейс входа, регистрации и личного кабинета."""
    return FileResponse(
        WEB_DIRECTORY / "index.html", headers={"Cache-Control": "no-store"}
    )
