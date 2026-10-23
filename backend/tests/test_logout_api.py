import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone

import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionFactory
from app.core.tokens import get_access_token_data, hash_refresh_token
from app.main import app
from app.models import AuthSession, RefreshToken
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenPairResponse
from app.schemas.user import UserRead


@pytest_asyncio.fixture(loop_scope="session")
async def client() -> AsyncIterator[AsyncClient]:
    """Предоставляет HTTP-клиент для тестирования API без запуска сервера."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as api_client:
        yield api_client


@pytest_asyncio.fixture(loop_scope="session")
async def logged_in_user(
    client: AsyncClient,
) -> AsyncIterator[tuple[UserRead, str, TokenPairResponse]]:
    """Регистрирует пользователя, выполняет вход и удаляет данные после теста."""
    email = f"logout_{uuid.uuid4().hex}@test.com"
    password = uuid.uuid4().hex

    try:
        register_response = await client.post(
            "/api/v1/auth/register", json={"email": email, "password": password}
        )
        assert register_response.status_code == 201
        user = UserRead.model_validate(register_response.json())

        login_response = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        assert login_response.status_code == 200
        tokens = TokenPairResponse.model_validate(login_response.json())
        yield user, password, tokens
    finally:
        async with AsyncSessionFactory() as session:
            repository = UserRepository(session)
            saved_user = await repository.get_user_by_email(email)
            if saved_user is not None:
                await session.delete(saved_user)
                await session.commit()


async def _assert_tokens_rejected(
    client: AsyncClient, tokens: TokenPairResponse
) -> None:
    """Проверяет отказ в доступе к /me и /refresh по токенам завершённой сессии."""
    me_response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens.access_token}"},
    )
    assert me_response.status_code == 401
    assert me_response.headers["WWW-Authenticate"] == "Bearer"
    assert me_response.json() == {"detail": "Не удалось проверить учётные данные"}

    refresh_response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens.refresh_token}
    )
    assert refresh_response.status_code == 401
    assert refresh_response.json() == {"detail": "Не удалось обновить токены"}


@pytest.mark.asyncio(loop_scope="session")
async def test_logout_success(
    client: AsyncClient,
    logged_in_user: tuple[UserRead, str, TokenPairResponse],
) -> None:
    """Проверяет HTTP 204, сохранённый отзыв сессии и отказ по её токенам."""
    user, _, tokens = logged_in_user
    token_data = get_access_token_data(tokens.access_token)
    assert token_data is not None

    before = datetime.now(timezone.utc)
    response = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": tokens.refresh_token}
    )
    after = datetime.now(timezone.utc)

    assert response.status_code == 204
    assert response.content == b""

    # Новая сессия БД подтверждает, что отзыв завершён через commit.
    async with AsyncSessionFactory() as session:
        saved_session = await session.get(AuthSession, token_data.session_id)
        assert saved_session is not None
        assert saved_session.user_id == user.id
        revoked_at = saved_session.revoked_at
        assert revoked_at is not None
        assert before <= revoked_at <= after

    await _assert_tokens_rejected(client, tokens)


@pytest.mark.asyncio(loop_scope="session")
async def test_logout_repeated_preserves_first_revocation_time(
    client: AsyncClient,
    logged_in_user: tuple[UserRead, str, TokenPairResponse],
) -> None:
    """Проверяет повторный HTTP 204 без изменения времени первого отзыва."""
    _, _, tokens = logged_in_user
    token_data = get_access_token_data(tokens.access_token)
    assert token_data is not None

    first_response = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": tokens.refresh_token}
    )
    assert first_response.status_code == 204
    assert first_response.content == b""

    async with AsyncSessionFactory() as session:
        saved_session = await session.get(AuthSession, token_data.session_id)
        assert saved_session is not None
        first_revoked_at = saved_session.revoked_at
        assert first_revoked_at is not None

    second_response = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": tokens.refresh_token}
    )
    assert second_response.status_code == 204
    assert second_response.content == b""

    async with AsyncSessionFactory() as session:
        saved_session = await session.get(AuthSession, token_data.session_id)
        assert saved_session is not None
        assert saved_session.revoked_at == first_revoked_at


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize("refresh_token", ["unknown-refresh-token", ""])
async def test_logout_unknown_token(client: AsyncClient, refresh_token: str) -> None:
    """Проверяет HTTP 204 без тела для неизвестного или пустого refresh-токена."""
    response = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": refresh_token}
    )
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize("data", [{}, {"refresh_token": None}, {"refresh_token": 123}])
async def test_logout_invalid_data(
    client: AsyncClient, data: dict[str, object]
) -> None:
    """Проверяет HTTP 422 при отсутствии refresh-токена или неверном типе поля."""
    response = await client.post("/api/v1/auth/logout", json=data)
    assert response.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_logout_does_not_revoke_other_session(
    client: AsyncClient,
    logged_in_user: tuple[UserRead, str, TokenPairResponse],
) -> None:
    """Проверяет доступ к /me и обновление токенов другого входа после выхода."""
    user, password, tokens = logged_in_user
    other_login = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": password}
    )
    assert other_login.status_code == 200
    other_tokens = TokenPairResponse.model_validate(other_login.json())
    token_data = get_access_token_data(tokens.access_token)
    other_data = get_access_token_data(other_tokens.access_token)
    assert token_data is not None
    assert other_data is not None
    assert token_data.session_id != other_data.session_id

    response = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": tokens.refresh_token}
    )
    assert response.status_code == 204
    assert response.content == b""
    await _assert_tokens_rejected(client, tokens)

    other_me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {other_tokens.access_token}"},
    )
    assert other_me.status_code == 200
    assert other_me.json() == {"id": user.id, "email": user.email}

    other_refresh = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": other_tokens.refresh_token}
    )
    assert other_refresh.status_code == 200
    refreshed_data = get_access_token_data(other_refresh.json()["access_token"])
    assert refreshed_data is not None
    assert refreshed_data.session_id == other_data.session_id

    async with AsyncSessionFactory() as session:
        other_session = await session.get(AuthSession, other_data.session_id)
        assert other_session is not None
        assert other_session.revoked_at is None


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize("token_source", ["current", "used"])
async def test_logout_after_refresh(
    client: AsyncClient,
    logged_in_user: tuple[UserRead, str, TokenPairResponse],
    token_source: str,
) -> None:
    """Проверяет выход после ротации по текущему или использованному refresh-токену."""
    _, _, old_tokens = logged_in_user
    refresh_response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": old_tokens.refresh_token}
    )
    assert refresh_response.status_code == 200
    new_tokens = TokenPairResponse.model_validate(refresh_response.json())
    me_response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {new_tokens.access_token}"},
    )
    assert me_response.status_code == 200

    logout_token = (
        new_tokens.refresh_token
        if token_source == "current"
        else old_tokens.refresh_token
    )
    response = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": logout_token}
    )
    assert response.status_code == 204
    assert response.content == b""
    await _assert_tokens_rejected(client, old_tokens)
    await _assert_tokens_rejected(client, new_tokens)


@pytest.mark.asyncio(loop_scope="session")
async def test_logout_with_expired_refresh_token(
    client: AsyncClient,
    logged_in_user: tuple[UserRead, str, TokenPairResponse],
) -> None:
    """Проверяет отзыв ещё действующей сессии по истёкшему refresh-токену."""
    _, _, tokens = logged_in_user
    token_hash = hash_refresh_token(tokens.refresh_token)
    async with AsyncSessionFactory() as session:
        saved_token = (
            await session.scalars(
                select(RefreshToken).where(RefreshToken.token_hash == token_hash)
            )
        ).one()
        saved_token.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        await session.commit()

    me_response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens.access_token}"},
    )
    assert me_response.status_code == 200

    response = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": tokens.refresh_token}
    )
    assert response.status_code == 204
    assert response.content == b""
    await _assert_tokens_rejected(client, tokens)


@pytest.mark.asyncio(loop_scope="session")
async def test_logout_with_expired_access_token(
    client: AsyncClient,
    logged_in_user: tuple[UserRead, str, TokenPairResponse],
) -> None:
    """Проверяет выход по refresh-токену при просроченном JWT в Authorization."""
    user, _, tokens = logged_in_user
    token_data = get_access_token_data(tokens.access_token)
    assert token_data is not None
    expired_token = jwt.encode(
        {
            "sub": str(user.id),
            "sid": str(token_data.session_id),
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    headers = {"Authorization": f"Bearer {expired_token}"}
    me_response = await client.get("/api/v1/auth/me", headers=headers)
    assert me_response.status_code == 401

    response = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": tokens.refresh_token},
        headers=headers,
    )
    assert response.status_code == 204
    assert response.content == b""
    await _assert_tokens_rejected(client, tokens)
