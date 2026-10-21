from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.database import AsyncSessionFactory
from app.core.tokens import get_access_token_data
from app.repositories.auth_session_repository import AuthSessionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserRead

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> UserRead:
    """Возвращает пользователя по JWT с действующей сессией авторизации.

    Проверяет существование, владельца, срок действия и отзыв сессии из sid.
    При ошибке проверки JWT, сессии или пользователя возвращает HTTP 401.
    """

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не удалось проверить учётные данные",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_token = get_access_token_data(credentials.credentials)
    if user_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не удалось проверить учётные данные",
            headers={"WWW-Authenticate": "Bearer"},
        )

    async with AsyncSessionFactory() as session:
        user_repository = UserRepository(session)
        session_repository = AuthSessionRepository(session)
        auth_session = await session_repository.get_session_by_id(user_token.session_id)
        if (
            auth_session is None
            or auth_session.user_id != user_token.user_id
            or auth_session.revoked_at is not None
            or auth_session.expires_at <= datetime.now(timezone.utc)
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Не удалось проверить учётные данные",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user = await user_repository.get_user_by_id(user_token.user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Не удалось проверить учётные данные",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return UserRead.model_validate(user)
