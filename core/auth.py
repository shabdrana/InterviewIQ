"""Registration / login with salted PBKDF2-HMAC-SHA256 password hashes (stdlib only)."""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets

from . import config, db

_ITER = 240_000
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITER)
    return f"pbkdf2_sha256${_ITER}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt, digest = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iters))
        return hmac.compare_digest(dk.hex(), digest)
    except Exception:
        return False


def register(full_name: str, email: str, password: str, confirm: str, role: str = "candidate",
             access_code: str = "") -> tuple[dict | None, str]:
    full_name, email = full_name.strip(), email.strip().lower()
    if len(full_name) < 2:
        return None, "Enter your full name."
    if not _EMAIL.match(email):
        return None, "Enter a valid email address."
    if len(password) < 8:
        return None, "Use a password with at least 8 characters."
    if password != confirm:
        return None, "The two passwords don't match."
    if role == "mentor" and not hmac.compare_digest(access_code, config.mentor_code()):
        return None, "That evaluator access code is incorrect."
    if db.get_user_by_email(email):
        return None, "An account with this email already exists. Sign in instead."
    uid = db.create_user(email, full_name, hash_password(password), role)
    return db.get_user(uid), ""


def login(email: str, password: str) -> tuple[dict | None, str]:
    user = db.get_user_by_email(email)
    if not user or not verify_password(password, user["password_hash"]):
        return None, "Email or password is incorrect."
    return user, ""


def demo_user() -> dict:
    """Local demo account so reviewers can look around without registering."""
    email = "demo@interviewiq.local"
    user = db.get_user_by_email(email)
    if not user:
        uid = db.create_user(email, "Demo Candidate", hash_password(secrets.token_urlsafe(24)), "candidate")
        user = db.get_user(uid)
    return user
