import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.database import AsyncSessionFactory
from app.core.tokens import create_access_token, get_access_token_data
from app.main import app
from app.models import AuthSession
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserRead
from app.services.auth_service import login_user, register_user


@pytest_asyncio.fixture(loop_scope="session")
async def authenticated_user() -> AsyncIterator[tuple[UserRead, str]]:
    """Создаёт пользователя с действующим JWT и сессией, затем очищает данные."""
    email = f"user_{uuid.uuid4().hex}@test.com"
    password = uuid.uuid4().hex

    try:
        user = await register_user(email, password)
        assert user is not None
        tokens = await login_user(email, password)
        assert tokens is not None
        yield user, tokens.access_token
    finally:
        async with AsyncSessionFactory() as session:
            repository = UserRepository(session)
            saved_user = await repository.get_user_by_email(email)
            if saved_user is not None:
                await session.delete(saved_user)
                await session.commit()


async def _assert_me_unauthorized(token: str) -> None:
    """Проверяет общий ответ HTTP 401 с Bearer-заголовком для запроса /me."""
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
    assert response.json() == {"detail": "Не удалось проверить учётные данные"}


@pytest.mark.asyncio(loop_scope="session")
async def test_me_missing_session(
    authenticated_user: tuple[UserRead, str],
) -> None:
    """Проверяет отказ с действующим JWT, если его сессия удалена из БД."""
    _, token = authenticated_user
    token_data = get_access_token_data(token)
    assert token_data is not None

    async with AsyncSessionFactory() as session:
        auth_session = await session.get(AuthSession, token_data.session_id)
        assert auth_session is not None
        await session.delete(auth_session)
        await session.commit()

    await _assert_me_unauthorized(token)


@pytest.mark.asyncio(loop_scope="session")
async def test_me_revoked_session(
    authenticated_user: tuple[UserRead, str],
) -> None:
    """Проверяет немедленный отказ по ещё действующему JWT после отзыва сессии."""
    _, token = authenticated_user
    token_data = get_access_token_data(token)
    assert token_data is not None

    async with AsyncSessionFactory() as session:
        auth_session = await session.get(AuthSession, token_data.session_id)
        assert auth_session is not None
        auth_session.revoked_at = datetime.now(timezone.utc)
        await session.commit()

    await _assert_me_unauthorized(token)


@pytest.mark.asyncio(loop_scope="session")
async def test_me_expired_session(
    authenticated_user: tuple[UserRead, str],
) -> None:
    """Проверяет отказ при истёкшей сессии, пока срок самого JWT ещё не истёк."""
    _, token = authenticated_user
    token_data = get_access_token_data(token)
    assert token_data is not None

    async with AsyncSessionFactory() as session:
        auth_session = await session.get(AuthSession, token_data.session_id)
        assert auth_session is not None
        auth_session.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        await session.commit()

    await _assert_me_unauthorized(token)


@pytest.mark.asyncio(loop_scope="session")
async def test_me_session_belongs_to_another_user(
    authenticated_user: tuple[UserRead, str],
) -> None:
    """Проверяет отказ, когда sub и sid относятся к разным существующим людям."""
    user, _ = authenticated_user
    other_email = f"other_{uuid.uuid4().hex}@test.com"
    password = uuid.uuid4().hex

    try:
        other_user = await register_user(other_email, password)
        assert other_user is not None
        other_tokens = await login_user(other_email, password)
        assert other_tokens is not None
        other_token_data = get_access_token_data(other_tokens.access_token)
        assert other_token_data is not None

        # Оба пользователя существуют, подпись JWT верна, чужая сессия действует.
        token = create_access_token(
            user_id=user.id,
            session_id=other_token_data.session_id,
        )

        await _assert_me_unauthorized(token)
    finally:
        async with AsyncSessionFactory() as session:
            repository = UserRepository(session)
            saved_user = await repository.get_user_by_email(other_email)
            if saved_user is not None:
                await session.delete(saved_user)
                await session.commit()
