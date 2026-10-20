from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.database import AsyncSessionFactory
from app.core.passwords import hash_password, verify_password
from app.core.tokens import (
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
)
from app.repositories.auth_session_repository import AuthSessionRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenPairResponse
from app.schemas.user import UserRead


async def register_user(email: str, password: str) -> UserRead | None:
    """Регистрирует пользователя по email и обычному паролю.

    Сохраняет в БД хеш пароля и возвращает публичные данные пользователя.
    Если email уже занят, возвращает None.
    """
    async with AsyncSessionFactory() as session:
        repository = UserRepository(session)

        existing_user = await repository.get_user_by_email(email)
        if existing_user is not None:
            return None

        password_hash = hash_password(password)
        user = await repository.create_user(email, password_hash)
        await session.commit()

        return UserRead.model_validate(user)


async def authenticate_user(email: str, password: str) -> UserRead | None:
    """Проверяет email и обычный пароль существующего пользователя.

    Сравнивает пароль с сохранённым хешем через verify_password.
    Возвращает публичные данные пользователя при успешной проверке,
    иначе None, если пользователь не найден или пароль неверный.
    """
    async with AsyncSessionFactory() as session:
        repository = UserRepository(session)
        user = await repository.get_user_by_email(email)
        if user is None:
            return None

        password_hash = user.password_hash
        if verify_password(password, password_hash=password_hash):
            return UserRead.model_validate(user)

        return None


async def login_user(email: str, password: str) -> TokenPairResponse | None:
    """Проверяет учётные данные перед созданием сессии авторизации.

    Возвращает None, если email или пароль неверны.
    """
    user = await authenticate_user(email, password)
    if user is None:
        return None

    current_time = datetime.now(timezone.utc)
    expires_at = current_time + timedelta(days=settings.refresh_token_expire_days)

    async with AsyncSessionFactory() as session:
        repository = AuthSessionRepository(session)
        auth_session = await repository.create_session(user.id, expires_at)
        refresh_token = generate_refresh_token()
        token_hash = hash_refresh_token(refresh_token)
        token_repository = RefreshTokenRepository(session)

        await token_repository.create_refresh_token(
            auth_session.id, token_hash, expires_at
        )

        access_token = create_access_token(user.id, auth_session.id)

        response = TokenPairResponse(access_token=access_token, refresh_token=refresh_token)

        await session.commit()
        
    return response        