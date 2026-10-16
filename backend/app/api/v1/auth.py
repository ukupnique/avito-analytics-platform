from fastapi import APIRouter, HTTPException, status

from app.core.tokens import create_access_token
from app.schemas.auth import LoginRequest, TokenResponse
from app.services.auth_service import authenticate_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest) -> TokenResponse:
    """Проверяет email и пароль и возвращает JWT при успешном входе.

    Если учётные данные неверны, завершает запрос с HTTP 401.
    """
    user = await authenticate_user(email=data.email, password=data.password)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный email или пароль"
        )

    token = create_access_token(user_id=user.id)

    return TokenResponse(access_token=token)
