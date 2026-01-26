from __future__ import annotations

import base64
import hashlib
import hmac
import os


def _b64e(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _b64d(txt: str) -> bytes:
    return base64.b64decode(txt.encode("ascii"))


def hash_password(password: str, *, salt: bytes | None = None) -> tuple[str, str]:
    if salt is None:
        salt = os.urandom(16)
    pwd = password.encode("utf-8")
    derived = hashlib.pbkdf2_hmac("sha256", pwd, salt, 200_000)
    return _b64e(salt), _b64e(derived)


def verify_password(password: str, *, salt_b64: str, password_hash_b64: str) -> bool:
    salt = _b64d(salt_b64)
    pwd = password.encode("utf-8")
    derived = hashlib.pbkdf2_hmac("sha256", pwd, salt, 200_000)
    expected = _b64d(password_hash_b64)
    return hmac.compare_digest(derived, expected)

