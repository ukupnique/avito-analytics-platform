from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user
from app.core.tokens import create_access_token
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserCreate, UserRead
from app.services.auth_service import authenticate_user, register_user

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


@router.get("/me", response_model=UserRead)
async def read_current_user(
    current_user: UserRead = Depends(get_current_user),
) -> UserRead:
    """Возвращает данные текущего пользователя после проверки JWT."""
    return current_user


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
async def register(data: UserCreate) -> UserRead:
    """Регистрирует пользователя или возвращает HTTP 409, если email занят."""
    user = await register_user(email=data.email, password=data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь с таким email уже существует",
        )
    return user
