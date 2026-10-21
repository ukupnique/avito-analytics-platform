from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user
from app.schemas.auth import LoginRequest, RefreshRequest, TokenPairResponse
from app.schemas.user import UserCreate, UserRead
from app.services.auth_service import login_user, refresh_tokens, register_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenPairResponse)
async def login(data: LoginRequest) -> TokenPairResponse:
    """Возвращает access- и refresh-токены после проверки email и пароля.

    Если учётные данные неверны, завершает запрос с HTTP 401.
    """
    tokens = await login_user(email=data.email, password=data.password)

    if tokens is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный email или пароль"
        )

    return tokens


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


@router.post(
    "/refresh",
    response_model=TokenPairResponse,
    status_code=status.HTTP_200_OK,
)
async def refresh(data: RefreshRequest) -> TokenPairResponse:
    """Обновляет пару токенов или завершает запрос с HTTP 401."""
    tokens = await refresh_tokens(refresh_token=data.refresh_token)

    if tokens is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не удалось обновить токены",
        )

    return tokens
