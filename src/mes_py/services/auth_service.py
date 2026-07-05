from __future__ import annotations

import base64
import hashlib
import hmac
import os
from dataclasses import dataclass
from datetime import timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mes_py.domain.enums import UserStatus
from mes_py.domain.errors import DomainError
from mes_py.domain.models import User, utc_now
from mes_py.services.utils import require_text


PBKDF2_ITERATIONS = 260_000


@dataclass(frozen=True)
class AuthenticatedUser:
    id: str
    name: str
    email: str


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        PBKDF2_ITERATIONS,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, digest = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        expected = base64.b64decode(digest)
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), base64.b64decode(salt), int(iterations)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


class AuthService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def ensure_bootstrap_admin(self, email: str, password: str) -> None:
        user_count = self.session.scalar(select(func.count()).select_from(User))
        if user_count:
            return
        now = utc_now()
        self.session.add(
            User(
                name="MES Admin",
                email=email.lower().strip(),
                password_hash=hash_password(password),
                status=UserStatus.ACTIVE.value,
                email_verified_at=now.astimezone(timezone.utc),
            )
        )

    def authenticate(self, email: str, password: str) -> AuthenticatedUser:
        normalized_email = require_text(email, "Email").lower()
        user = self.session.scalar(select(User).where(User.email == normalized_email))
        if not user or not verify_password(password, user.password_hash):
            raise DomainError("Email 或密碼不正確")
        if user.status != UserStatus.ACTIVE.value:
            raise DomainError("帳號尚未啟用")
        return AuthenticatedUser(id=user.id, name=user.name, email=user.email)

