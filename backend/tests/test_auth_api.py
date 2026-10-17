import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import AsyncSessionFactory
from app.core.tokens import get_user_id_from_token
from app.main import app
from app.repositories.user_repository import UserRepository
from app.services.auth_service import register_user


@pytest.fixture
def random_email() -> str:
    """Фикстура, генерирующая уникальный email для теста."""
    return f"user_{uuid.uuid4().hex[:8]}@test.com"


@pytest.mark.asyncio(loop_scope="session")
async def test_login_success(random_email: str) -> None:
    """Проверяет успешный вход и получение JWT с ID пользователя."""
    email = random_email
    password = uuid.uuid4().hex[:8]
    user_was_committed = False

    try:
        user = await register_user(random_email, password)
        user_was_committed = user is not None

        assert user is not None

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": password},
            )
            assert response.status_code == 200
            assert response.json()["token_type"] == "bearer"
            access_token = response.json()["access_token"]
            assert isinstance(access_token, str)
            assert access_token
            assert get_user_id_from_token(access_token) == user.id

    finally:
        if user_was_committed:
            async with AsyncSessionFactory() as session:
                repository = UserRepository(session)
                saved_user = await repository.get_user_by_email(random_email)
                if saved_user is not None:
                    await session.delete(saved_user)
                    await session.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_login_wrong_password(random_email: str) -> None:
    """Проверяет, что вход с неверным паролем возвращает HTTP 401."""
    email = random_email
    password = uuid.uuid4().hex[:8]
    user_was_committed = False

    try:
        user = await register_user(random_email, password)
        user_was_committed = user is not None

        assert user is not None

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "12345678"},
            )
            assert response.status_code == 401
            assert response.json()["detail"] == "Неверный email или пароль"
            assert "access_token" not in response.json()

    finally:
        if user_was_committed:
            async with AsyncSessionFactory() as session:
                repository = UserRepository(session)
                saved_user = await repository.get_user_by_email(random_email)
                if saved_user is not None:
                    await session.delete(saved_user)
                    await session.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_login_wrong_email(random_email: str) -> None:
    """Проверяет, что вход с незарегистрированным email возвращает HTTP 401."""

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": random_email, "password": "password123"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Неверный email или пароль"
        assert "access_token" not in response.json()

@pytest.mark.asyncio(loop_scope="session")
async def test_incorrect_email() -> None:
    """Проверяет, что вход с некорректным email возвращает HTTP 422."""

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "not_a_email", "password": "password123"},
        )
        assert response.status_code == 422