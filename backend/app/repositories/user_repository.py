from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        """Принимает сессию БД, которой управляет вызывающий код."""
        self.session = session

    async def get_user_by_email(self, email: str) -> User | None:
        """Возвращает модель пользователя по email или None, если он не найден."""
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def create_user(self, email: str, password_hash: str) -> User:
        """Добавляет нового пользователя с готовым хешем пароля в сессию.

        Возвращает модель User; commit выполняет вызывающий код.
        """
        user = User(email=email, password_hash=password_hash)
        self.session.add(user)
        return user

    async def get_user_by_id(self, user_id: int) -> User | None:
        """Возвращает пользователя по ID или None, если он не найден."""
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
