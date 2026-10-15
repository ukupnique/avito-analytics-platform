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
