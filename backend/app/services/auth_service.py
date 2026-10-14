from app.core.database import AsyncSessionFactory
from app.core.passwords import hash_password
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserRead


async def register_user(email: str, password: str) -> UserRead | None:
    async with AsyncSessionFactory() as session:
        repository = UserRepository(session)

        existing_user = await repository.get_user_by_email(email)
        if existing_user is not None:
            return None

        password_hash = hash_password(password)
        user = await repository.create_user(email, password_hash)
        await session.commit()

        return UserRead.model_validate(user)