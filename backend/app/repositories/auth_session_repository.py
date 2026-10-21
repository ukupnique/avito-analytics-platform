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

    async def get_session_by_id(
        self, session_id: UUID, for_update: bool = False
    ) -> AuthSession | None:
        """Возвращает сессию авторизации по ID или None, если она не найдена.

        При for_update=True блокирует строку до завершения транзакции.
        Фиксацией или откатом транзакции управляет вызывающий код.
        """
        statement = select(AuthSession).where(AuthSession.id == session_id)
        if for_update:
            statement = statement.with_for_update()

        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def revoke_session(
        self, session_id: UUID, revoked_at: datetime
    ) -> AuthSession | None:
        """Отзывает сессию, сохраняя время первого отзыва.

        Возвращает None, если сессия не найдена; commit выполняет вызывающий код.
        """
        auth_session = await self.get_session_by_id(session_id=session_id)
        if auth_session is None:
            return None
        if auth_session.revoked_at is None:
            auth_session.revoked_at = revoked_at
        await self.session.flush()
        return auth_session
