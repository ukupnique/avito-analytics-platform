import uuid

import pytest
from app.core.database import AsyncSessionFactory
from app.repositories.user_repository import UserRepository


@pytest.fixture
def random_email() -> str:
    """Фикстура, генерирующая уникальный email для теста."""
    return f"user_{uuid.uuid4().hex[:8]}@test.com"


@pytest.mark.asyncio
async def test_create_user_and_find_by_email(random_email: str) -> None:
    try:
        async with AsyncSessionFactory() as session:
            repository = UserRepository(session)

            assert await repository.get_user_by_email(random_email) is None

            await repository.create_user(random_email, "test-hash")
            await session.commit()

        # Новая сессия проверяет, что после commit пользователь виден в базе.
        async with AsyncSessionFactory() as session:
            repository = UserRepository(session)
            saved_user = await repository.get_user_by_email(random_email)

            assert saved_user is not None
            assert saved_user.email == random_email
            assert saved_user.password_hash == "test-hash"
    finally:
        # Удаляем тестовые данные, даже если какая-либо проверка завершилась ошибкой.
        async with AsyncSessionFactory() as session:
            repository = UserRepository(session)
            saved_user = await repository.get_user_by_email(random_email)
            if saved_user is not None:
                await session.delete(saved_user)
                await session.commit()
