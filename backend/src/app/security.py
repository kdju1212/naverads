import base64
import functools
import hashlib
import hmac
import json
import os
import secrets
import time

from cryptography.fernet import Fernet

TOKEN_TTL = 60 * 60 * 12


# 사용 시점에 읽는다: Workers에서는 Secret이 모듈 로드 후(첫 요청)에야 들어온다
def _secret() -> str:
    s = os.getenv("APP_SECRET", "")
    if not s:
        if os.getenv("APP_ENV", "dev") != "dev":
            raise RuntimeError("APP_SECRET must be set outside dev")
        s = "dev-only-secret"
    return s


@functools.cache
def _fernet(secret: str) -> Fernet:
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()))


# Workers WebCrypto의 PBKDF2 최대 반복 횟수가 100,000 이라 이 값으로 고정 (로컬 hashlib와 같은 결과)
PBKDF2_ITERATIONS = 100_000


async def _pbkdf2(pw: str, salt: str) -> str:
    try:
        from js import Object, Uint8Array, crypto  # Cloudflare Workers
        from pyodide.ffi import to_js
    except ImportError:
        return hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), PBKDF2_ITERATIONS).hex()
    # Workers(Pyodide)에는 hashlib.pbkdf2_hmac이 없고, wasm 계산은 무료 플랜 CPU 한도를 크게 소모해 네이티브 WebCrypto 사용
    key = await crypto.subtle.importKey("raw", to_js(pw.encode()), "PBKDF2", False, to_js(["deriveBits"]))
    params = to_js({"name": "PBKDF2", "hash": "SHA-256", "salt": to_js(salt.encode()), "iterations": PBKDF2_ITERATIONS},
                   dict_converter=Object.fromEntries)
    return bytes(Uint8Array.new(await crypto.subtle.deriveBits(params, key, 256)).to_py()).hex()


async def hash_password(pw: str) -> str:
    salt = secrets.token_hex(16)
    return f"{salt}${await _pbkdf2(pw, salt)}"


async def verify_password(pw: str, stored: str) -> bool:
    salt, digest = stored.split("$")
    return hmac.compare_digest(await _pbkdf2(pw, salt), digest)


def _sign(msg: str) -> str:
    return hmac.new(_secret().encode(), msg.encode(), hashlib.sha256).hexdigest()


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


def sign_payload(data: dict, ttl: int | None = None) -> str:
    """MCP 로그인(OAuth)의 클라이언트 ID·인가 코드·갱신 토큰. DB 없이 서명으로 검증한다(점 1개라 로그인 토큰과 섞이지 않음)."""
    if ttl:
        data = {**data, "exp": int(time.time()) + ttl}
    body = base64.urlsafe_b64encode(json.dumps(data, separators=(",", ":")).encode()).decode().rstrip("=")
    return f"{body}.{_sign('p.' + body)}"


def read_payload(token: str, kind: str) -> dict | None:
    body, _, sig = token.partition(".")
    if not sig or not hmac.compare_digest(sig, _sign("p." + body)):
        return None
    data = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    if data.get("t") != kind or data.get("exp", float("inf")) < time.time():
        return None
    return data


def encrypt(s: str) -> str:
    return _fernet(_secret()).encrypt(s.encode()).decode()


def decrypt(s: str) -> str:
    return _fernet(_secret()).decrypt(s.encode()).decode()
