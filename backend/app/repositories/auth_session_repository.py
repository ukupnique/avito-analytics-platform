from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuthSession


class AuthSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        """Принимает сессию БД, которой управляет вызывающий код."""
        self.session = session

    async def create_session(self, user_id: int, expires_at: datetime) -> AuthSession:
        """Создаёт сессию авторизации; commit выполняет вызывающий код."""
        auth_session = AuthSession(user_id=user_id, expires_at=expires_at)
        self.session.add(auth_session)
        await self.session.flush()
        return auth_session

    async def get_session_by_id(self, session_id: UUID) -> AuthSession | None:
        """Возвращает сессию авторизации по ID или None, если она не найдена."""
        result = await self.session.execute(
            select(AuthSession).where(AuthSession.id == session_id)
        )
        return result.scalar_one_or_none()
