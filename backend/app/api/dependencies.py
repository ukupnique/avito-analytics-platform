from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.database import AsyncSessionFactory
from app.core.tokens import get_user_id_from_token
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserRead

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> UserRead:
    """Возвращает пользователя по JWT или завершает запрос с HTTP 401."""

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не удалось проверить учётные данные",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = get_user_id_from_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не удалось проверить учётные данные",
            headers={"WWW-Authenticate": "Bearer"},
        )

    async with AsyncSessionFactory() as session:
        repository = UserRepository(session)
        user = await repository.get_user_by_id(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Не удалось проверить учётные данные",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return UserRead.model_validate(user)
