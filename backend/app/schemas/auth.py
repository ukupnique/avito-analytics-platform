from typing import Literal

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
