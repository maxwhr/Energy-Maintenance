from datetime import timedelta

import pytest

from app.core.security import (
    TokenExpiredError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.services.auth_service import AuthService, AuthServiceError


def test_hash_password_round_trip() -> None:
    password = "StrongLocal!234"
    assert verify_password(password, hash_password(password))


def test_hash_password_uses_unique_salts() -> None:
    password = "StrongLocal!234"
    assert hash_password(password) != hash_password(password)


def test_verify_password_rejects_wrong_value() -> None:
    assert not verify_password("wrong-value", hash_password("StrongLocal!234"))


def test_verify_password_rejects_malformed_hash() -> None:
    assert not verify_password("anything", "not-a-valid-password-hash")


def test_access_token_round_trip() -> None:
    token, expires_in = create_access_token("user-subject")
    payload = decode_access_token(token)
    assert payload["sub"] == "user-subject"
    assert expires_in > 0


def test_expired_access_token_is_rejected() -> None:
    token, _ = create_access_token("expired-subject", timedelta(seconds=-1))
    with pytest.raises(TokenExpiredError):
        decode_access_token(token)


def test_auth_service_accepts_active_user(db_session, make_user) -> None:
    user = make_user(username="active_auth_user", role="engineer")
    authenticated, token, expires_in = AuthService(db_session).authenticate(
        user.username,
        "LocalOnly!234",
    )
    assert authenticated.id == user.id
    assert authenticated.last_login_at is not None
    assert decode_access_token(token)["sub"] == str(user.id)
    assert expires_in > 0


def test_auth_service_rejects_disabled_user(db_session, make_user) -> None:
    user = make_user(
        username="disabled_auth_user",
        role="viewer",
        status="disabled",
        is_active=False,
    )
    with pytest.raises(AuthServiceError, match="disabled"):
        AuthService(db_session).authenticate(user.username, "LocalOnly!234")
