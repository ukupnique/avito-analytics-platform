from app.core.database import AsyncSessionFactory
from app.core.passwords import hash_password, verify_password
from app.repositories.user_repository import UserRepository
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
