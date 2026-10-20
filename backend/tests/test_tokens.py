import time
from datetime import datetime, timedelta, timezone
from secrets import token_hex
from uuid import uuid4

import jwt
import pytest

from app.core.config import settings
from app.core.tokens import (
    create_access_token,
    generate_refresh_token,
    get_user_id_from_token,
    hash_refresh_token,
)


def test_create_access_token_contains_user_id_session_id_and_expiration() -> None:
    """Проверяет ID пользователя, ID сессии и настроенный срок действия JWT."""
    session_id = uuid4()
    before = int(time.time())
    token = create_access_token(user_id=112, session_id=session_id)
    after = int(time.time())

    assert isinstance(token, str)
    assert token

    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )

    assert payload["sub"] == "112"
    assert payload["sid"] == str(session_id)

    ttl_seconds = settings.access_token_expire_minutes * 60

    assert before + ttl_seconds <= payload["exp"] <= after + ttl_seconds


def test_get_user_id_from_token_expired() -> None:
    """Проверяет, что токен с истёкшим сроком действия возвращает None."""
    payload = {
        "sub": "112",
        "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
    }
    encoded_jwt = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    assert get_user_id_from_token(encoded_jwt) is None


def test_get_user_id_from_token_success() -> None:
    """Проверяет возврат целочисленного ID пользователя из действительного JWT."""
    token = create_access_token(user_id=112, session_id=uuid4())

    user_id = get_user_id_from_token(token=token)

    assert user_id == 112


def test_get_user_id_from_token_invalid_signature() -> None:
    """Проверяет отказ для непросроченного токена, подписанного другим ключом."""
    payload = {
        "sub": "112",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    wrong_key = token_hex(32)

    encoded_jwt = jwt.encode(
        payload,
        wrong_key,
        algorithm=settings.jwt_algorithm,
    )

    assert get_user_id_from_token(encoded_jwt) is None


def test_get_user_id_from_token_malformed() -> None:
    """Проверяет возврат None для строки, не являющейся JWT."""
    assert get_user_id_from_token("not_a_token") is None


@pytest.mark.parametrize("missing_claim", ["sub", "exp"])
def test_get_user_id_from_token_missing_required_claim(
    missing_claim: str,
) -> None:
    """Проверяет отказ для подписанного токена без обязательного поля sub или exp."""
    payload = {
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        "sub": "112",
    }

    payload.pop(missing_claim)

    encoded_jwt = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    assert get_user_id_from_token(encoded_jwt) is None


@pytest.mark.parametrize("sub", ["abc", "0", "-1"])
def test_get_user_id_from_token_invalid_sub(sub: str) -> None:
    """Проверяет отказ для нечислового или неположительного ID."""
    payload = {
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        "sub": sub,
    }

    encoded_jwt = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    assert get_user_id_from_token(encoded_jwt) is None


def test_get_user_id_from_token_disallowed_algorithm() -> None:
    """Проверяет отказ для токена с неразрешённым алгоритмом подписи."""
    payload = {
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        "sub": "112",
    }

    encoded_jwt = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm="HS384",
    )

    assert get_user_id_from_token(encoded_jwt) is None


def test_generate_refresh_token_returns_unique_strings() -> None:
    """Проверяет, что генератор возвращает разные непустые строки."""
    first_token = generate_refresh_token()
    second_token = generate_refresh_token()

    assert isinstance(first_token, str)
    assert isinstance(second_token, str)
    assert first_token
    assert second_token
    assert first_token != second_token


def test_hash_refresh_token_is_repeatable() -> None:
    """Проверяет одинаковый хеш при повторном хешировании одного токена."""
    token = "example-refresh-token"

    first_hash = hash_refresh_token(token)
    second_hash = hash_refresh_token(token)

    assert first_hash == second_hash


def test_hash_refresh_token_known_value() -> None:
    """Проверяет SHA-256 переданной строки по заранее известному значению."""
    expected_hash = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"

    assert hash_refresh_token("abc") == expected_hash
