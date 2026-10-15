import pytest

from app.core.passwords import hash_password, verify_password


def test_hash_password_returns_argon2id_hash() -> None:
    """Проверяет, что функция создаёт Argon2id-хеш, отличный от обычного пароля."""
    password = "Учебный пароль 123!"

    password_hash = hash_password(password)

    assert password_hash != password
    assert password_hash.startswith("$argon2id$")


@pytest.mark.parametrize(
    ("candidate_password", "expected_result"),
    [
        ("Учебный пароль 123!", True),
        ("Другой пароль 456!", False),
    ],
)
def test_verify_password(
    candidate_password: str,
    expected_result: bool,
) -> None:
    """Проверяет результаты сравнения хеша с верным и неверным паролями."""
    password_hash = hash_password("Учебный пароль 123!")

    assert verify_password(candidate_password, password_hash) is expected_result


def test_hash_password_uses_a_unique_salt() -> None:
    """Проверяет, что один пароль даёт разные хеши и подходит к каждому из них."""
    password = "Учебный пароль 123!"

    first_hash = hash_password(password)
    second_hash = hash_password(password)

    assert first_hash != second_hash
    assert verify_password(password, first_hash)
    assert verify_password(password, second_hash)
