import base64
import functools
import hashlib
import hmac
import json
import os
import secrets
import time

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

TOKEN_TTL = 60 * 60 * 12  # 웹 로그인(재발급 장치가 없어 업무 하루치)


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


def make_token(user_id: int, version: int = 0, mcp: int | None = None, ttl: int = TOKEN_TTL) -> str:
    """mcp: Claude 연결 토큰이면 사용자의 mcp_version(Claude 연결만 끊기용)."""
    msg = ".".join(map(str, [user_id, version, *([mcp] if mcp is not None else []), int(time.time()) + ttl]))
    return f"{msg}.{_sign(msg)}"


def read_token(token: str) -> tuple[int, int, int | None] | None:
    """(사용자 ID, 토큰 버전, Claude 연결 버전 또는 None). 버전 없는 예전 토큰(점 2개)은 버전 0 — 배포 때 모두 로그아웃되지 않게."""
    parts = token.split(".")
    if len(parts) not in (3, 4, 5) or not all(p.isdigit() for p in parts[:-1]):
        return None
    *body, sig = parts
    if not hmac.compare_digest(sig, _sign(".".join(body))) or int(body[-1]) < time.time():
        return None
    return int(body[0]), int(body[1]) if len(body) >= 3 else 0, int(body[2]) if len(body) == 4 else None


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


# 네이버 비밀키 암호화 열쇠는 CRED_KEY(로그인 서명용 APP_SECRET과 따로). 둘 중 하나만 새서는 비밀키를 풀 수 없다.
# 열쇠 교체: 지금 CRED_KEY를 CRED_KEY_OLD로 옮겨 넣고 새 값을 CRED_KEY로 → 목록 조회·크론이 새 열쇠로 옮김 → 모두 CRED_KEY인지
# 확인한 뒤에만 CRED_KEY_OLD를 지운다(예전 열쇠 없이 바꾸면 저장된 비밀키를 못 푼다 — 10/29 장애)
KEY_NAMES = ("CRED_KEY", "CRED_KEY_OLD", "APP_SECRET")


def _secrets() -> list[tuple[str, str]]:
    return [(n, os.getenv(n, "") if n != "APP_SECRET" else _secret()) for n in KEY_NAMES if n == "APP_SECRET" or os.getenv(n)]


def _keys() -> MultiFernet:
    return MultiFernet([_fernet(v) for _, v in _secrets()])


def encrypt(s: str) -> str:
    return _keys().encrypt(s.encode()).decode()


def decrypt(s: str) -> str:
    return _keys().decrypt(s.encode()).decode()


def key_of(s: str) -> str:
    """암호문을 푸는 열쇠 이름: CRED_KEY | CRED_KEY_OLD | APP_SECRET | UNREADABLE(어느 열쇠로도 안 풀림 — 열쇠를 잃음)."""
    for name, secret in _secrets():
        try:
            _fernet(secret).decrypt(s.encode())
            return name
        except InvalidToken:
            pass
    return "UNREADABLE"


def rotated(s: str) -> str | None:
    """CRED_KEY로 다시 암호화한 값. 이미 CRED_KEY로 돼 있거나, CRED_KEY가 없거나, 풀 수 없으면 None(그대로 둠)."""
    if not os.getenv("CRED_KEY") or key_of(s) not in ("CRED_KEY_OLD", "APP_SECRET"):
        return None
    return _keys().rotate(s.encode()).decode()
