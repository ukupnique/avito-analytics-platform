import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone

import jwt
import pytest
import pytest_asyncio
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionFactory
from app.core.passwords import verify_password
from app.core.tokens import hash_refresh_token
from app.models import AuthSession, RefreshToken
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenPairResponse
from app.schemas.user import UserRead
from app.services.auth_service import authenticate_user, login_user, register_user


@pytest.fixture
def random_email() -> str:
    """Фикстура, генерирующая уникальный email для теста."""
    return f"user_{uuid.uuid4().hex[:8]}@test.com"


@pytest_asyncio.fixture(loop_scope="session")
async def registered_user(
    random_email: str,
) -> AsyncIterator[tuple[UserRead, str]]:
    """Создаёт пользователя и удаляет его вместе с записями входа после теста."""
    password = uuid.uuid4().hex

    try:
        user = await register_user(random_email, password)
        assert user is not None
        yield user, password
    finally:
        async with AsyncSessionFactory() as session:
            repository = UserRepository(session)
            saved_user = await repository.get_user_by_email(random_email)
            if saved_user is not None:
                await session.delete(saved_user)
                await session.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_register_user(random_email: str) -> None:
    """Проверяет сохранение хеша пароля и отказ при повторной регистрации email."""
    password = uuid.uuid4().hex[:8]
    user_was_committed = False

    try:
        user = await register_user(random_email, password)
        user_was_committed = user is not None

        assert user is not None
        assert isinstance(user, UserRead)
        assert user.email == random_email

        async with AsyncSessionFactory() as session:
            repository = UserRepository(session)
            saved_user = await repository.get_user_by_email(random_email)

            assert saved_user is not None
            assert saved_user.password_hash != password
            assert verify_password(password, saved_user.password_hash)
            assert await register_user(random_email, password) is None

    finally:
        if user_was_committed:
            async with AsyncSessionFactory() as session:
                repository = UserRepository(session)
                saved_user = await repository.get_user_by_email(random_email)
                if saved_user is not None:
                    await session.delete(saved_user)
                    await session.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_authenticate_user_success(random_email: str) -> None:
    """Проверяет возврат UserRead с верными ID и email при успешном входе."""
    password = uuid.uuid4().hex[:8]
    user_was_committed = False

    try:
        user = await register_user(random_email, password)
        user_was_committed = user is not None

        assert user is not None

        load_user = await authenticate_user(random_email, password)

        assert isinstance(load_user, UserRead)
        assert load_user.id == user.id
        assert load_user.email == user.email

    finally:
        if user_was_committed:
            async with AsyncSessionFactory() as session:
                repository = UserRepository(session)
                saved_user = await repository.get_user_by_email(random_email)
                if saved_user is not None:
                    await session.delete(saved_user)
                    await session.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_authenticate_user_wrong_password(random_email: str) -> None:
    """Проверяет, что вход с неверным паролем возвращает None."""
    password = uuid.uuid4().hex[:8]
    wrong_password = "ololo_im_wrong_text"
    user_was_committed = False

    try:
        user = await register_user(random_email, password)
        user_was_committed = user is not None

        assert user is not None

        wrong_user = await authenticate_user(random_email, wrong_password)

        assert wrong_user is None

    finally:
        if user_was_committed:
            async with AsyncSessionFactory() as session:
                repository = UserRepository(session)
                saved_user = await repository.get_user_by_email(random_email)
                if saved_user is not None:
                    await session.delete(saved_user)
                    await session.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_authenticate_user_unknown_email(random_email: str) -> None:
    """Проверяет, что вход с незарегистрированным email возвращает None."""
    wrong_email = random_email

    wrong_user = await authenticate_user(wrong_email, "password")

    assert wrong_user is None


@pytest.mark.asyncio(loop_scope="session")
async def test_login_user_persists_session_and_refresh_token(
    registered_user: tuple[UserRead, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет связь JWT с сохранённой сессией, хеш refresh и настроенный TTL."""
    user, password = registered_user
    monkeypatch.setattr(settings, "refresh_token_expire_days", 3)

    before = datetime.now(timezone.utc)
    tokens = await login_user(user.email, password)
    after = datetime.now(timezone.utc)

    assert isinstance(tokens, TokenPairResponse)
    assert tokens.token_type == "bearer"
    assert tokens.refresh_token

    payload = jwt.decode(
        tokens.access_token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    assert payload["sub"] == str(user.id)
    session_id = uuid.UUID(payload["sid"])
    expected_hash = hash_refresh_token(tokens.refresh_token)

    # Новая сессия БД видит только изменения, завершённые через commit.
    async with AsyncSessionFactory() as session:
        saved_session = await session.get(AuthSession, session_id)
        assert saved_session is not None
        assert saved_session.user_id == user.id
        assert saved_session.revoked_at is None

        ttl = timedelta(days=3)
        assert before + ttl <= saved_session.expires_at <= after + ttl

        result = await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == expected_hash)
        )
        saved_token = result.scalar_one()
        assert saved_token.session_id == saved_session.id
        assert saved_token.token_hash != tokens.refresh_token
        assert saved_token.expires_at == saved_session.expires_at
        assert saved_token.used_at is None


@pytest.mark.asyncio(loop_scope="session")
async def test_login_user_wrong_password_does_not_create_session(
    registered_user: tuple[UserRead, str],
) -> None:
    """Проверяет, что неверный пароль не создаёт сессию авторизации."""
    user, password = registered_user

    assert await login_user(user.email, password + "-wrong") is None

    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(AuthSession).where(AuthSession.user_id == user.id)
        )
        assert result.scalar_one_or_none() is None


@pytest.mark.asyncio(loop_scope="session")
async def test_login_user_creates_separate_sessions(
    registered_user: tuple[UserRead, str],
) -> None:
    """Проверяет независимые сессии и разные refresh-токены при двух входах."""
    user, password = registered_user

    first_tokens = await login_user(user.email, password)
    second_tokens = await login_user(user.email, password)

    assert first_tokens is not None
    assert second_tokens is not None
    assert first_tokens.refresh_token != second_tokens.refresh_token

    session_ids = {
        uuid.UUID(
            jwt.decode(
                tokens.access_token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
            )["sid"]
        )
        for tokens in (first_tokens, second_tokens)
    }
    assert len(session_ids) == 2

    async with AsyncSessionFactory() as session:
        sessions_result = await session.execute(
            select(AuthSession).where(AuthSession.user_id == user.id)
        )
        saved_sessions = sessions_result.scalars().all()
        assert {saved_session.id for saved_session in saved_sessions} == session_ids
        assert all(saved_session.revoked_at is None for saved_session in saved_sessions)

        tokens_result = await session.execute(
            select(RefreshToken).where(RefreshToken.session_id.in_(session_ids))
        )
        saved_tokens = tokens_result.scalars().all()
        assert len(saved_tokens) == 2
        assert {saved_token.session_id for saved_token in saved_tokens} == session_ids
        assert {saved_token.token_hash for saved_token in saved_tokens} == {
            hash_refresh_token(first_tokens.refresh_token),
            hash_refresh_token(second_tokens.refresh_token),
        }


@pytest.mark.asyncio(loop_scope="session")
async def test_login_user_rolls_back_when_access_token_creation_fails(
    registered_user: tuple[UserRead, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет откат сессии и refresh-записи при ошибке выпуска JWT."""
    user, password = registered_user
    refresh_token = uuid.uuid4().hex

    def fail_to_create_access_token(user_id: int, session_id: uuid.UUID) -> str:
        """Имитирует ошибку после создания обеих записей, до commit."""
        raise RuntimeError("Ошибка выпуска JWT")

    monkeypatch.setattr(
        "app.services.auth_service.generate_refresh_token", lambda: refresh_token
    )
    monkeypatch.setattr(
        "app.services.auth_service.create_access_token", fail_to_create_access_token
    )

    with pytest.raises(RuntimeError, match="Ошибка выпуска JWT"):
        await login_user(user.email, password)

    async with AsyncSessionFactory() as session:
        sessions_result = await session.execute(
            select(AuthSession).where(AuthSession.user_id == user.id)
        )
        assert sessions_result.scalar_one_or_none() is None

        tokens_result = await session.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_refresh_token(refresh_token)
            )
        )
        assert tokens_result.scalar_one_or_none() is None
