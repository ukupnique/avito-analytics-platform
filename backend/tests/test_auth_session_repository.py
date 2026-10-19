import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.core.database import AsyncSessionFactory
from app.repositories.auth_session_repository import AuthSessionRepository
from app.repositories.user_repository import UserRepository
from app.services.auth_service import register_user


@pytest.fixture
def random_email() -> str:
    """Фикстура, генерирующая уникальный email для теста."""
    return f"user_{uuid.uuid4().hex[:8]}@test.com"


@pytest.mark.asyncio(loop_scope="session")
async def test_create_auth_session_and_find_by_id(random_email: str) -> None:
    """Проверяет создание сессии и поиск по ID из новой сессии БД после commit."""
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

        # Новая сессия БД проверяет, что запись действительно сохранилась.
        async with AsyncSessionFactory() as session:
            repository = AuthSessionRepository(session)
            saved_session = await repository.get_session_by_id(session_id)

            assert saved_session is not None
            assert saved_session.id == session_id
            assert saved_session.user_id == user.id
            assert saved_session.expires_at == expires_at
            assert saved_session.revoked_at is None
    finally:
        if user_was_committed:
            async with AsyncSessionFactory() as session:
                user_repository = UserRepository(session)
                saved_user = await user_repository.get_user_by_email(random_email)
                if saved_user is not None:
                    # Сессии авторизации удаляются каскадно вместе с пользователем.
                    await session.delete(saved_user)
                    await session.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_revoke_session(random_email: str) -> None:
    """Проверяет сохранение времени отзыва сессии в БД после commit."""
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
            repository = AuthSessionRepository(session)
            revoked_at = datetime.now(UTC)
            auth_session = await repository.revoke_session(
                session_id=session_id,
                revoked_at=revoked_at,
            )
            await session.commit()

        # Новая сессия БД проверяет, что запись действительно сохранилась.
        async with AsyncSessionFactory() as session:
            repository = AuthSessionRepository(session)
            saved_session = await repository.get_session_by_id(session_id)

            assert saved_session is not None
            assert saved_session.id == session_id
            assert saved_session.revoked_at == revoked_at
    finally:
        if user_was_committed:
            async with AsyncSessionFactory() as session:
                user_repository = UserRepository(session)
                saved_user = await user_repository.get_user_by_email(random_email)
                if saved_user is not None:
                    # Сессии авторизации удаляются каскадно вместе с пользователем.
                    await session.delete(saved_user)
                    await session.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_revoke_session_preserves_first_revoked_at(random_email: str) -> None:
    """Проверяет сохранение первого времени отзыва при повторном вызове."""
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
            repository = AuthSessionRepository(session)
            revoked_at_first = datetime.now(UTC)
            auth_session = await repository.revoke_session(
                session_id=session_id,
                revoked_at=revoked_at_first,
            )
            await session.commit()

        async with AsyncSessionFactory() as session:
            repository = AuthSessionRepository(session)
            revoked_at_second = revoked_at_first + timedelta(minutes=1)
            auth_session = await repository.revoke_session(
                session_id=session_id,
                revoked_at=revoked_at_second,
            )
            await session.commit()

        # Новая сессия БД проверяет, что запись действительно сохранилась.
        async with AsyncSessionFactory() as session:
            repository = AuthSessionRepository(session)
            saved_session = await repository.get_session_by_id(session_id)

            assert saved_session is not None
            assert saved_session.id == session_id
            assert saved_session.revoked_at == revoked_at_first
    finally:
        if user_was_committed:
            async with AsyncSessionFactory() as session:
                user_repository = UserRepository(session)
                saved_user = await user_repository.get_user_by_email(random_email)
                if saved_user is not None:
                    # Сессии авторизации удаляются каскадно вместе с пользователем.
                    await session.delete(saved_user)
                    await session.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_revoke_session_not_found() -> None:
    """Проверяет, что отзыв несуществующей сессии возвращает None."""
    session_id = uuid.uuid4()

    async with AsyncSessionFactory() as session:
        repository = AuthSessionRepository(session)
        revoked_at = datetime.now(UTC)
        auth_session = await repository.revoke_session(
            session_id=session_id,
            revoked_at=revoked_at,
        )
        assert auth_session is None
