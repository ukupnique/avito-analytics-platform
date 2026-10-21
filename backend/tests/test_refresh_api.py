import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.database import AsyncSessionFactory
from app.core.tokens import get_access_token_data, hash_refresh_token
from app.main import app
from app.models import AuthSession, RefreshToken
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenPairResponse
from app.schemas.user import UserRead
from app.services import auth_service


@pytest_asyncio.fixture(loop_scope="session")
async def client() -> AsyncIterator[AsyncClient]:
    """Предоставляет HTTP-клиент для запросов к приложению без запуска сервера."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as api_client:
        yield api_client


@pytest_asyncio.fixture(loop_scope="session")
async def logged_in_user(
    client: AsyncClient,
) -> AsyncIterator[tuple[UserRead, str, TokenPairResponse]]:
    """Регистрирует пользователя, выполняет вход и удаляет данные после теста."""
    email = f"refresh_{uuid.uuid4().hex}@test.com"
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
            user = await repository.get_user_by_email(email)
            if user is not None:
                await session.delete(user)
                await session.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_refresh_success(
    client: AsyncClient,
    logged_in_user: tuple[UserRead, str, TokenPairResponse],
) -> None:
    """Проверяет ротацию токенов, сохранение срока сессии и доступ к /me."""
    user, _, old_tokens = logged_in_user
    old_data = get_access_token_data(old_tokens.access_token)
    assert old_data is not None

    async with AsyncSessionFactory() as session:
        saved_session = await session.get(AuthSession, old_data.session_id)
        assert saved_session is not None
        original_expires_at = saved_session.expires_at

    before = datetime.now(timezone.utc)
    response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": old_tokens.refresh_token}
    )
    after = datetime.now(timezone.utc)

    assert response.status_code == 200
    data = response.json()
    assert set(data) == {"access_token", "refresh_token", "token_type"}
    assert data["token_type"] == "bearer"
    for field in ("access_token", "refresh_token"):
        assert isinstance(data[field], str)
        assert data[field]
    assert data["refresh_token"] != old_tokens.refresh_token

    new_data = get_access_token_data(data["access_token"])
    assert new_data is not None
    assert new_data.user_id == user.id
    assert new_data.session_id == old_data.session_id

    # Новое соединение подтверждает, что ротация зафиксирована в БД.
    async with AsyncSessionFactory() as session:
        sessions = (
            await session.scalars(
                select(AuthSession).where(AuthSession.user_id == user.id)
            )
        ).all()
        assert len(sessions) == 1
        assert sessions[0].id == old_data.session_id
        assert sessions[0].expires_at == original_expires_at
        assert sessions[0].revoked_at is None

        saved_tokens = (
            await session.scalars(
                select(RefreshToken).where(
                    RefreshToken.session_id == old_data.session_id
                )
            )
        ).all()
        by_hash = {token.token_hash: token for token in saved_tokens}
        old_hash = hash_refresh_token(old_tokens.refresh_token)
        new_hash = hash_refresh_token(data["refresh_token"])
        assert set(by_hash) == {old_hash, new_hash}
        used_at = by_hash[old_hash].used_at
        assert used_at is not None
        assert before <= used_at <= after
        assert by_hash[new_hash].used_at is None
        assert by_hash[new_hash].expires_at == original_expires_at

    me_response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert me_response.status_code == 200
    assert me_response.json() == {"id": user.id, "email": user.email}

    next_response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": data["refresh_token"]}
    )
    assert next_response.status_code == 200
    assert next_response.json()["refresh_token"] != data["refresh_token"]


@pytest.mark.asyncio(loop_scope="session")
async def test_refresh_reuse_revokes_only_its_session(
    client: AsyncClient,
    logged_in_user: tuple[UserRead, str, TokenPairResponse],
) -> None:
    """Проверяет отзыв сессии при повторном использовании и независимость входов."""
    user, password, old_tokens = logged_in_user
    other_login = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": password}
    )
    assert other_login.status_code == 200
    other_tokens = other_login.json()

    response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": old_tokens.refresh_token}
    )
    assert response.status_code == 200
    new_tokens = response.json()

    replay = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": old_tokens.refresh_token}
    )
    assert replay.status_code == 401
    assert replay.json() == {"detail": "Не удалось обновить токены"}

    token_data = get_access_token_data(new_tokens["access_token"])
    assert token_data is not None
    async with AsyncSessionFactory() as session:
        saved_session = await session.get(AuthSession, token_data.session_id)
        assert saved_session is not None
        assert saved_session.revoked_at is not None

    for access_token in (old_tokens.access_token, new_tokens["access_token"]):
        me_response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert me_response.status_code == 401
        assert me_response.headers["WWW-Authenticate"] == "Bearer"

    revoked_refresh = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": new_tokens["refresh_token"]}
    )
    assert revoked_refresh.status_code == 401

    other_me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {other_tokens['access_token']}"},
    )
    assert other_me.status_code == 200
    other_refresh = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": other_tokens["refresh_token"]}
    )
    assert other_refresh.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize("refresh_token", ["unknown-refresh-token", ""])
async def test_refresh_unknown_token(client: AsyncClient, refresh_token: str) -> None:
    """Проверяет HTTP 401 для неизвестного или пустого refresh-токена."""
    response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Не удалось обновить токены"}


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize("data", [{}, {"refresh_token": None}, {"refresh_token": 123}])
async def test_refresh_invalid_data(
    client: AsyncClient, data: dict[str, object]
) -> None:
    """Проверяет HTTP 422 при отсутствии refresh-токена или неверном типе поля."""
    response = await client.post("/api/v1/auth/refresh", json=data)
    assert response.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize(
    "state", ["expired_token", "expired_session", "revoked_session"]
)
async def test_refresh_inactive_token_or_session(
    client: AsyncClient,
    logged_in_user: tuple[UserRead, str, TokenPairResponse],
    state: str,
) -> None:
    """Проверяет отказ по истёкшему токену, истёкшей или отозванной сессии."""
    _, _, tokens = logged_in_user
    token_data = get_access_token_data(tokens.access_token)
    assert token_data is not None
    token_hash = hash_refresh_token(tokens.refresh_token)
    past = datetime.now(timezone.utc) - timedelta(minutes=1)

    async with AsyncSessionFactory() as session:
        saved_session = await session.get(AuthSession, token_data.session_id)
        assert saved_session is not None
        saved_token = (
            await session.scalars(
                select(RefreshToken).where(RefreshToken.token_hash == token_hash)
            )
        ).one()
        if state == "expired_token":
            saved_token.expires_at = past
        elif state == "expired_session":
            saved_session.expires_at = past
        else:
            saved_session.revoked_at = past
        await session.commit()

    response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens.refresh_token}
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Не удалось обновить токены"}

    async with AsyncSessionFactory() as session:
        saved_tokens = (
            await session.scalars(
                select(RefreshToken).where(
                    RefreshToken.session_id == token_data.session_id
                )
            )
        ).all()
        assert len(saved_tokens) == 1
        assert saved_tokens[0].used_at is None


@pytest.mark.asyncio(loop_scope="session")
async def test_refresh_rolls_back_when_access_token_creation_fails(
    client: AsyncClient,
    logged_in_user: tuple[UserRead, str, TokenPairResponse],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет откат ротации при ошибке выпуска JWT и возможность повторить запрос."""
    _, _, tokens = logged_in_user
    token_data = get_access_token_data(tokens.access_token)
    assert token_data is not None

    def fail_to_create_access_token(*args: object, **kwargs: object) -> str:
        """Имитирует ошибку выпуска JWT после изменения refresh-токенов в транзакции."""
        raise RuntimeError("Ошибка выпуска JWT")

    with monkeypatch.context() as patch:
        patch.setattr(auth_service, "create_access_token", fail_to_create_access_token)
        with pytest.raises(RuntimeError, match="Ошибка выпуска JWT"):
            await client.post(
                "/api/v1/auth/refresh", json={"refresh_token": tokens.refresh_token}
            )

    async with AsyncSessionFactory() as session:
        saved_tokens = (
            await session.scalars(
                select(RefreshToken).where(
                    RefreshToken.session_id == token_data.session_id
                )
            )
        ).all()
        assert len(saved_tokens) == 1
        assert saved_tokens[0].token_hash == hash_refresh_token(tokens.refresh_token)
        assert saved_tokens[0].used_at is None

    response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens.refresh_token}
    )
    assert response.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_refresh_concurrent_requests_detect_reuse(
    client: AsyncClient,
    logged_in_user: tuple[UserRead, str, TokenPairResponse],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет одну ротацию и отзыв сессии при двух запросах с одним токеном."""
    _, _, tokens = logged_in_user
    token_hash = hash_refresh_token(tokens.refresh_token)
    original_lookup = RefreshTokenRepository.get_refresh_token_by_hash
    both_loaded = asyncio.Event()
    loaded_count = 0

    async def load_token_before_lock(
        repository: RefreshTokenRepository, token_hash: str
    ) -> RefreshToken | None:
        """Задерживает первые два чтения до загрузки токена обеими транзакциями."""
        nonlocal loaded_count
        stored_token = await original_lookup(repository, token_hash)
        if token_hash == hash_refresh_token(tokens.refresh_token) and loaded_count < 2:
            assert stored_token is not None
            assert stored_token.used_at is None
            loaded_count += 1
            if loaded_count == 2:
                both_loaded.set()
            await asyncio.wait_for(both_loaded.wait(), timeout=10)
        return stored_token

    with monkeypatch.context() as patch:
        patch.setattr(
            RefreshTokenRepository, "get_refresh_token_by_hash", load_token_before_lock
        )
        responses = await asyncio.wait_for(
            asyncio.gather(
                client.post(
                    "/api/v1/auth/refresh", json={"refresh_token": tokens.refresh_token}
                ),
                client.post(
                    "/api/v1/auth/refresh", json={"refresh_token": tokens.refresh_token}
                ),
            ),
            timeout=15,
        )

    assert loaded_count == 2
    assert sorted(response.status_code for response in responses) == [200, 401]
    successful_tokens = next(
        response.json() for response in responses if response.status_code == 200
    )
    token_data = get_access_token_data(successful_tokens["access_token"])
    assert token_data is not None

    async with AsyncSessionFactory() as session:
        saved_session = await session.get(AuthSession, token_data.session_id)
        assert saved_session is not None
        assert saved_session.revoked_at is not None
        saved_tokens = (
            await session.scalars(
                select(RefreshToken).where(
                    RefreshToken.session_id == token_data.session_id
                )
            )
        ).all()
        by_hash = {token.token_hash: token for token in saved_tokens}
        new_hash = hash_refresh_token(successful_tokens["refresh_token"])
        assert set(by_hash) == {token_hash, new_hash}
        assert by_hash[token_hash].used_at is not None
        assert by_hash[new_hash].used_at is None

    me_response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {successful_tokens['access_token']}"},
    )
    assert me_response.status_code == 401
    next_refresh = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": successful_tokens["refresh_token"]},
    )
    assert next_refresh.status_code == 401
