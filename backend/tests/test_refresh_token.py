import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.core.database import AsyncSessionFactory
from app.repositories.auth_session_repository import AuthSessionRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.services.auth_service import register_user


@pytest.fixture
def random_email() -> str:
    """Фикстура, генерирующая уникальный email для теста."""
    return f"user_{uuid.uuid4().hex[:8]}@test.com"


@pytest.mark.asyncio(loop_scope="session")
async def test_create_refresh_token_and_find_by_hash(random_email: str) -> None:
    """Проверяет создание refresh-токена и поиск по хешу после commit."""
    password = uuid.uuid4().hex[:8]
    user_was_committed = False

    try:
        user = await register_user(random_email, password)
        user_was_committed = user is not None

        assert user is not None

        expires_at = datetime.now(UTC) + timedelta(days=7)

        async with AsyncSessionFactory() as session:
            repository = AuthSessionRepository(session)
            auth_session = await repository.create_session(
                user_id=user.id,
                expires_at=expires_at,
            )
            session_id = auth_session.id
            await session.commit()

        async with AsyncSessionFactory() as session:
            repository = RefreshTokenRepository(session)
            token_hash = uuid.uuid4().hex + uuid.uuid4().hex

            created_token = await repository.create_refresh_token(
                session_id=session_id,
                token_hash=token_hash,
                expires_at=expires_at,
            )

            assert created_token is not None
            assert created_token.session_id == session_id
            assert created_token.expires_at == expires_at
            assert created_token.token_hash == token_hash

            await session.commit()

        # Новая сессия БД проверяет, что refresh-токен действительно сохранился.
        async with AsyncSessionFactory() as session:
            repository = RefreshTokenRepository(session)

            saved_token = await repository.get_refresh_token_by_hash(
                token_hash=token_hash
            )

            assert saved_token is not None
            assert saved_token.session_id == session_id
            assert saved_token.expires_at == expires_at
            assert saved_token.token_hash == token_hash
            assert saved_token.used_at is None
    finally:
        if user_was_committed:
            async with AsyncSessionFactory() as session:
                user_repository = UserRepository(session)
                saved_user = await user_repository.get_user_by_email(random_email)
                if saved_user is not None:
                    # Удаление пользователя каскадно удаляет его сессии и токены.
                    await session.delete(saved_user)
                    await session.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_mark_refresh_token_as_used(random_email: str) -> None:
    """Проверяет сохранение времени использования refresh-токена после commit."""
    password = uuid.uuid4().hex[:8]
    user_was_committed = False

    try:
        user = await register_user(random_email, password)
        user_was_committed = user is not None

        assert user is not None

        expires_at = datetime.now(UTC) + timedelta(days=7)

        async with AsyncSessionFactory() as session:
            repository = AuthSessionRepository(session)
            auth_session = await repository.create_session(
                user_id=user.id,
                expires_at=expires_at,
            )
            session_id = auth_session.id
            await session.commit()

        async with AsyncSessionFactory() as session:
            repository = RefreshTokenRepository(session)
            token_hash = uuid.uuid4().hex + uuid.uuid4().hex

            created_token = await repository.create_refresh_token(
                session_id=session_id,
                token_hash=token_hash,
                expires_at=expires_at,
            )
            used_date = datetime.now(UTC)

            await repository.mark_refresh_token_as_used(
                token_hash=token_hash, used_at=used_date
            )
            assert created_token is not None
            assert created_token.session_id == session_id
            assert created_token.expires_at == expires_at
            assert created_token.token_hash == token_hash

            await session.commit()

        # Новая сессия БД проверяет, что refresh-токен действительно сохранился.
        async with AsyncSessionFactory() as session:
            repository = RefreshTokenRepository(session)

            saved_token = await repository.get_refresh_token_by_hash(
                token_hash=token_hash
            )

            assert saved_token is not None
            assert saved_token.session_id == session_id
            assert saved_token.expires_at == expires_at
            assert saved_token.token_hash == token_hash
            assert saved_token.used_at == used_date
    finally:
        if user_was_committed:
            async with AsyncSessionFactory() as session:
                user_repository = UserRepository(session)
                saved_user = await user_repository.get_user_by_email(random_email)
                if saved_user is not None:
                    # Удаление пользователя каскадно удаляет его сессии и токены.
                    await session.delete(saved_user)
                    await session.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_mark_refresh_token_as_used_preserves_first_used_at(
    random_email: str,
) -> None:
    """Проверяет сохранение первого времени использования при повторном вызове."""
    password = uuid.uuid4().hex[:8]
    user_was_committed = False

    try:
        user = await register_user(random_email, password)
        user_was_committed = user is not None

        assert user is not None

        expires_at = datetime.now(UTC) + timedelta(days=7)

        async with AsyncSessionFactory() as session:
            repository = AuthSessionRepository(session)
            auth_session = await repository.create_session(
                user_id=user.id,
                expires_at=expires_at,
            )
            session_id = auth_session.id
            await session.commit()

        async with AsyncSessionFactory() as session:
            repository = RefreshTokenRepository(session)
            token_hash = uuid.uuid4().hex + uuid.uuid4().hex

            created_token = await repository.create_refresh_token(
                session_id=session_id,
                token_hash=token_hash,
                expires_at=expires_at,
            )
            used_date_first = datetime.now(UTC)
            used_date_second = used_date_first + timedelta(minutes=1)

            await repository.mark_refresh_token_as_used(
                token_hash=token_hash, used_at=used_date_first
            )
            assert created_token is not None
            assert created_token.session_id == session_id
            assert created_token.expires_at == expires_at
            assert created_token.token_hash == token_hash

            await session.commit()

        async with AsyncSessionFactory() as session:
            repository = RefreshTokenRepository(session)

            await repository.mark_refresh_token_as_used(
                token_hash=token_hash, used_at=used_date_second
            )

            await session.commit()

        # Повторная отметка должна сохранить время первого использования.
        async with AsyncSessionFactory() as session:
            repository = RefreshTokenRepository(session)

            saved_token = await repository.get_refresh_token_by_hash(
                token_hash=token_hash
            )

            assert saved_token is not None
            assert saved_token.session_id == session_id
            assert saved_token.expires_at == expires_at
            assert saved_token.token_hash == token_hash
            assert saved_token.used_at == used_date_first
    finally:
        if user_was_committed:
            async with AsyncSessionFactory() as session:
                user_repository = UserRepository(session)
                saved_user = await user_repository.get_user_by_email(random_email)
                if saved_user is not None:
                    # Удаление пользователя каскадно удаляет его сессии и токены.
                    await session.delete(saved_user)
                    await session.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_mark_refresh_token_as_used_not_found() -> None:
    """Проверяет, что отметка использования отсутствующего токена возвращает None."""
    token_hash = uuid.uuid4().hex + uuid.uuid4().hex
    used_at = datetime.now(UTC)

    async with AsyncSessionFactory() as session:
        repository = RefreshTokenRepository(session)
        result = await repository.mark_refresh_token_as_used(
            token_hash=token_hash,
            used_at=used_at,
        )

        assert result is None
