from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    """Данные запроса входа: email и пароль пользователя."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Ответ успешного входа с JWT access token и типом токена bearer."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"


class TokenPairResponse(TokenResponse):
    """Ответ с access-токеном, refresh-токеном и типом токена."""

    refresh_token: str


class AccessTokenData(BaseModel):
    """Данные пользователя и сессии из проверенного access-токена."""

    user_id: int
    session_id: UUID


class RefreshRequest(BaseModel):
    """Запрос на обновление пары токенов по refresh-токену."""

    refresh_token: str
