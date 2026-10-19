import uuid
from datetime import datetime, timedelta, timezone
from secrets import token_hex

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.database import AsyncSessionFactory
from app.core.tokens import create_access_token, get_user_id_from_token
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


@pytest.mark.asyncio(loop_scope="session")
async def test_me_success(random_email: str) -> None:
    """Проверяет получение данных текущего пользователя по корректному JWT."""
    password = uuid.uuid4().hex
    user_was_committed = False

    try:
        user = await register_user(random_email, password)
        user_was_committed = user is not None

        assert user is not None

        token = create_access_token(user.id)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200

        assert response.json() == {
            "id": user.id,
            "email": user.email,
        }

    finally:
        if user_was_committed:
            async with AsyncSessionFactory() as session:
                repository = UserRepository(session)
                saved_user = await repository.get_user_by_email(random_email)
                if saved_user is not None:
                    await session.delete(saved_user)
                    await session.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_no_token() -> None:
    """Проверяет HTTP 401 и Bearer-заголовок при запросе /me без токена."""

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/v1/auth/me",
        )

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json() == {
        "detail": "Не удалось проверить учётные данные",
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_me_invalid_token() -> None:
    """Проверяет HTTP 401 и Bearer-заголовок при запросе /me с битым токеном."""

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer ololoolo"},
        )

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json() == {
        "detail": "Не удалось проверить учётные данные",
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_me_expired_token(random_email: str) -> None:
    """Проверяет HTTP 401 при запросе /me с просроченным JWT."""
    password = uuid.uuid4().hex
    user_was_committed = False

    try:
        user = await register_user(random_email, password)
        user_was_committed = user is not None

        assert user is not None

        payload = {
            "sub": str(user.id),
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        }
        token = jwt.encode(
            payload,
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"
        assert response.json() == {
            "detail": "Не удалось проверить учётные данные",
        }
    finally:
        if user_was_committed:
            async with AsyncSessionFactory() as session:
                repository = UserRepository(session)
                saved_user = await repository.get_user_by_email(random_email)
                if saved_user is not None:
                    await session.delete(saved_user)
                    await session.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_me_invalid_signature(random_email: str) -> None:
    """Проверяет HTTP 401 при запросе /me с JWT, подписанным другим ключом."""
    password = uuid.uuid4().hex
    user_was_committed = False

    try:
        user = await register_user(random_email, password)
        user_was_committed = user is not None

        assert user is not None

        payload = {
            "sub": str(user.id),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        }
        wrong_key = token_hex(32)
        token = jwt.encode(
            payload,
            wrong_key,
            algorithm=settings.jwt_algorithm,
        )

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"
        assert response.json() == {
            "detail": "Не удалось проверить учётные данные",
        }
    finally:
        if user_was_committed:
            async with AsyncSessionFactory() as session:
                repository = UserRepository(session)
                saved_user = await repository.get_user_by_email(random_email)
                if saved_user is not None:
                    await session.delete(saved_user)
                    await session.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_me_deleted_user(random_email: str) -> None:
    """Проверяет HTTP 401 при запросе /me с JWT у удаленного пользователя."""
    password = uuid.uuid4().hex
    user_was_committed = False

    try:
        user = await register_user(random_email, password)
        user_was_committed = user is not None

        assert user is not None

        payload = {
            "sub": str(user.id),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        }
        token = jwt.encode(
            payload,
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
        async with AsyncSessionFactory() as session:
            repository = UserRepository(session)
            saved_user = await repository.get_user_by_email(random_email)
            await session.delete(saved_user)
            await session.commit()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"
        assert response.json() == {
            "detail": "Не удалось проверить учётные данные",
        }
    finally:
        if user_was_committed:
            async with AsyncSessionFactory() as session:
                repository = UserRepository(session)
                saved_user = await repository.get_user_by_email(random_email)
                if saved_user is not None:
                    await session.delete(saved_user)
                    await session.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_register_success(random_email: str) -> None:
    """Проверяет успешную регистрацию через API и возврат HTTP 201."""

    email = random_email
    password = uuid.uuid4().hex[:8]
    user_was_committed = False

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": password},
            )
            user_was_committed = True
            assert response.status_code == 201
        async with AsyncSessionFactory() as session:
            repository = UserRepository(session)
            saved_user = await repository.get_user_by_email(email)

            assert saved_user is not None
            assert response.json() == {
                "id": saved_user.id,
                "email": email,
            }

    finally:
        if user_was_committed:
            async with AsyncSessionFactory() as session:
                repository = UserRepository(session)
                saved_user = await repository.get_user_by_email(random_email)
                if saved_user is not None:
                    await session.delete(saved_user)
                    await session.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_register_duplicate_email(random_email: str) -> None:
    """Проверяет повторную регистрацию по email и возврат HTTP 409."""

    email = random_email
    password = uuid.uuid4().hex[:8]
    user_was_committed = False

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": password},
            )
            user_was_committed = True
            assert response.status_code == 201
        async with AsyncSessionFactory() as session:
            repository = UserRepository(session)
            saved_user = await repository.get_user_by_email(email)

            assert saved_user is not None
            assert response.json() == {
                "id": saved_user.id,
                "email": email,
            }

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": password},
            )
            assert response.status_code == 409
            assert response.json() == {
                "detail": "Пользователь с таким email уже существует",
            }
    finally:
        if user_was_committed:
            async with AsyncSessionFactory() as session:
                repository = UserRepository(session)
                saved_user = await repository.get_user_by_email(random_email)
                if saved_user is not None:
                    await session.delete(saved_user)
                    await session.commit()


@pytest.mark.parametrize(
    "data",
    [
        {"email": "abc", "password": "password123"},
        {"password": "password123"},
        {"email": "user@example.com"},
    ],
)
@pytest.mark.asyncio(loop_scope="session")
async def test_register_invalid_data(data: dict[str, str]) -> None:
    """Проверяет HTTP 422 при некорректных данных регистрации."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/auth/register",
            json=data,
        )
        assert response.status_code == 422
