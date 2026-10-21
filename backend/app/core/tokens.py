import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt

from app.core.config import settings
from app.schemas.auth import AccessTokenData


def create_access_token(user_id: int, session_id: UUID) -> str:
    """Создаёт и возвращает подписанный JWT для указанного пользователя.

    Записывает ID пользователя строкой в sub, ID сессии строкой в sid
    и срок действия в UTC в exp.
    Ключ, алгоритм подписи и время жизни токена берёт из settings.
    """
    current_time = datetime.now(timezone.utc)
    expires_at = current_time + timedelta(minutes=settings.access_token_expire_minutes)

    payload = {
        "sub": str(user_id),
        "exp": expires_at,
        "sid": str(session_id),
    }
    encoded_jwt = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    return encoded_jwt


def get_access_token_data(token: str) -> AccessTokenData | None:
    """Проверяет access JWT и возвращает данные пользователя и сессии.

    Возвращает None при неверной подписи, истёкшем сроке или некорректных данных.
    """

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "exp", "sid"]},
        )

        user_id = int(payload["sub"])

        if user_id <= 0:
            return None

        session_id = payload["sid"]

        session_data = {
            "user_id": user_id,
            "session_id": session_id,
        }

        token_data = AccessTokenData.model_validate(session_data)

    except jwt.InvalidTokenError:
        return None
    except ValueError:
        return None

    return token_data


def generate_refresh_token() -> str:
    """Создаёт секретный URL-безопасный refresh-токен из 32 случайных байтов."""
    refresh_token = secrets.token_urlsafe(32)
    return refresh_token


def hash_refresh_token(token: str) -> str:
    """Возвращает SHA-256-хеш переданного refresh-токена в виде hex-строки."""
    hashed_token = hashlib.sha256(token.encode("utf-8"))
    return hashed_token.hexdigest()
