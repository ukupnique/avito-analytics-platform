import uuid

import pytest

from app.core.database import AsyncSessionFactory
from app.core.passwords import verify_password
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserRead
from app.services.auth_service import authenticate_user, register_user


@pytest.fixture
def random_email() -> str:
    """Фикстура, генерирующая уникальный email для теста."""
    return f"user_{uuid.uuid4().hex[:8]}@test.com"


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
