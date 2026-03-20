"""Tests for password hashing and JWT token utilities."""
import pytest
from services.core.security import get_password_hash, verify_password, create_access_token
from jose import jwt
from services.core.config import settings


class TestPasswordHashing:
    def test_hash_returns_bcrypt_string(self):
        h = get_password_hash("hello123")
        assert h.startswith("$2")
        assert len(h) >= 50

    def test_verify_correct_password(self):
        h = get_password_hash("secret")
        assert verify_password("secret", h) is True

    def test_verify_wrong_password(self):
        h = get_password_hash("secret")
        assert verify_password("wrong", h) is False

    def test_different_inputs_different_hashes(self):
        h1 = get_password_hash("password1")
        h2 = get_password_hash("password2")
        assert h1 != h2

    def test_same_input_different_salts(self):
        h1 = get_password_hash("same")
        h2 = get_password_hash("same")
        assert h1 != h2  # bcrypt uses random salts


class TestJWT:
    def test_create_token_decodable(self):
        token = create_access_token({"sub": "user-123"})
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["sub"] == "user-123"
        assert "exp" in payload

    def test_token_contains_custom_data(self):
        token = create_access_token({"sub": "abc", "role": "admin"})
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["role"] == "admin"

    def test_wrong_secret_fails(self):
        token = create_access_token({"sub": "x"})
        with pytest.raises(Exception):
            jwt.decode(token, "wrong-key", algorithms=[settings.ALGORITHM])
