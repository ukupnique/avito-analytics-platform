from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RefreshToken


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        """Принимает сессию БД, которой управляет вызывающий код."""
        self.session = session

    async def create_refresh_token(
        self, session_id: UUID, token_hash: str, expires_at: datetime
    ) -> RefreshToken:
        """Сохраняет хеш refresh-токена; commit выполняет вызывающий код."""
        token = RefreshToken(
            session_id=session_id, token_hash=token_hash, expires_at=expires_at
        )
        self.session.add(token)
        await self.session.flush()
        return token

    async def get_refresh_token_by_hash(self, token_hash: str) -> RefreshToken | None:
        """Возвращает запись refresh-токена по хешу или None."""
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()
