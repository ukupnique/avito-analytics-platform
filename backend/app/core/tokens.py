from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings


def create_access_token(user_id: int) -> str:
    """Создаёт и возвращает подписанный JWT для указанного пользователя.

    Записывает ID пользователя строкой в sub и срок действия в UTC в exp.
    Ключ, алгоритм подписи и время жизни токена берёт из settings.
    """
    current_time = datetime.now(timezone.utc)
    expires_at = current_time + timedelta(minutes=settings.access_token_expire_minutes)

    payload = {
        "sub": str(user_id),
        "exp": expires_at,
    }
    encoded_jwt = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    return encoded_jwt


def get_user_id_from_token(token: str) -> int | None:
    """Проверяет JWT и возвращает положительный ID пользователя или None."""

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "exp"]},
        )

        user_id = int(payload["sub"])

        if user_id <= 0:
            return None

    except jwt.InvalidTokenError:
        return None
    except ValueError:
        return None

    return user_id
