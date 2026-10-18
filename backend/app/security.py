import base64
import hashlib
import hmac
import os
import secrets
import time

from cryptography.fernet import Fernet

APP_SECRET = os.getenv("APP_SECRET", "")
if not APP_SECRET:
    if os.getenv("APP_ENV", "dev") != "dev":
        raise RuntimeError("APP_SECRET must be set outside dev")
    APP_SECRET = "dev-only-secret"

TOKEN_TTL = 60 * 60 * 12
_fernet = Fernet(base64.urlsafe_b64encode(hashlib.sha256(APP_SECRET.encode()).digest()))


def hash_password(pw: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 200_000).hex()
    return f"{salt}${digest}"


def verify_password(pw: str, stored: str) -> bool:
    salt, digest = stored.split("$")
    return hmac.compare_digest(hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 200_000).hex(), digest)


def _sign(msg: str) -> str:
    return hmac.new(APP_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()


def make_token(user_id: int) -> str:
    msg = f"{user_id}.{int(time.time()) + TOKEN_TTL}"
    return f"{msg}.{_sign(msg)}"


def read_token(token: str) -> int | None:
    try:
        uid, exp, sig = token.split(".")
    except ValueError:
        return None
    if not hmac.compare_digest(sig, _sign(f"{uid}.{exp}")) or int(exp) < time.time():
        return None
    return int(uid)


def encrypt(s: str) -> str:
    return _fernet.encrypt(s.encode()).decode()


def decrypt(s: str) -> str:
    return _fernet.decrypt(s.encode()).decode()
