"""SEO·GEO 점검용 페이지 가져오기. 판정은 브라우저(frontend/lib/seo.ts)가 한다(HTML 분석을 파이썬이 하면 CPU 한도 초과)."""
import ipaddress
import socket
import sys
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import httpx

# 스마트스토어·브랜드스토어는 외부 수집을 막아 점검 결과가 틀리게 나온다
BLOCKED_HOSTS = ("smartstore.naver.com", "brand.naver.com")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
MAX_HTML = 2_000_000
MAX_REDIRECTS = 5
MAX_BODY = 3_000_000  # 받는 중에 이 크기를 넘으면 끊는다(전부 받은 뒤 자르지 않음)
TIMEOUT = httpx.Timeout(10, connect=5)
# Workers(Pyodide)는 사설망·메타데이터 주소에 닿지 못하고 DNS를 직접 조회할 수도 없다. 그 밖(로컬·VM)에서는 접속할 IP를 검사한다
ON_WORKERS = sys.platform == "emscripten"
INTERNAL_SUFFIXES = (".localhost", ".local", ".internal", ".lan", ".home.arpa")


class SeoError(Exception):
    pass


def check_url(url: str) -> str:
    """점검할 수 없는 주소면 SeoError.
    shortcut: 도메인 이름이 내부 IP를 가리키는 경우(DNS 리바인딩 포함)는 막지 못한다 — 운영(Workers)은 사설망·메타데이터 주소에
    닿지 못해 문제없고, 로컬 실행에서만 해당. 서버를 VM·컨테이너로 옮기면 실제 접속 IP를 검사해야 한다"""
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower().rstrip(".")
    if parts.scheme not in ("http", "https") or not host:
        raise SeoError("http:// 또는 https://로 시작하는 주소를 넣어 주세요")
    try:
        port = parts.port
    except ValueError:
        raise SeoError("주소 형식이 올바르지 않습니다") from None
    if parts.username or parts.password or "@" in parts.netloc:
        raise SeoError("주소에 아이디·비밀번호를 넣을 수 없습니다")
    if port not in (None, 80, 443):
        raise SeoError("기본 포트(80·443) 주소만 점검할 수 있습니다")
    if any(host == h or host.endswith("." + h) for h in BLOCKED_HOSTS):
        raise SeoError("스마트스토어·브랜드스토어 주소는 점검할 수 없습니다 (네이버가 외부 수집을 막아 결과가 정확하지 않음)")
    try:
        ip = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        ip = None
    # 2130706433·127.1·0x7f.1처럼 숫자로만 된 주소는 내부 IP로 해석될 수 있어 도메인 이름만 받는다
    numeric = ip is None and not any(ch.isalpha() for ch in host.rsplit(".", 1)[-1])
    if host == "localhost" or host.endswith(INTERNAL_SUFFIXES) or numeric or (ip and not _public(ip)):
        raise SeoError("내부 주소는 점검할 수 없습니다")
    if ip is None and not ON_WORKERS:
        _check_dns(host)
    return url.strip()


def _public(ip) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:  # ::ffff:10.0.0.1 같은 IPv4 변형
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


def _check_dns(host: str):
    """도메인이 가리키는 IP가 하나라도 내부면 거부한다.
    shortcut: 검사 후 실제 접속 사이에 DNS가 바뀌는 리바인딩은 못 막는다(로컬 실행만 해당), 서버를 VM으로 옮기면 IP 고정 접속으로"""
    try:
        ips = {ipaddress.ip_address(a[4][0].split("%")[0]) for a in socket.getaddrinfo(host, None)}
    except (socket.gaierror, UnicodeError, ValueError):
        raise SeoError("주소를 찾을 수 없습니다") from None
    if not ips or not all(_public(i) for i in ips):
        raise SeoError("내부 주소는 점검할 수 없습니다")


@dataclass
class Page:
    status_code: int
    url: str
    headers: dict = field(default_factory=dict)
    text: str = ""


def _fetch_once(url: str) -> Page:
    """한 번 요청(리다이렉트 안 따라감). 본문은 받는 중에 MAX_BODY를 넘으면 끊는다."""
    with httpx.stream("GET", url, headers={"User-Agent": UA}, timeout=TIMEOUT) as r:
        if int(r.headers.get("content-length") or 0) > MAX_BODY:
            raise SeoError("페이지가 너무 큽니다")
        body = bytearray()
        if not r.is_redirect:
            for chunk in r.iter_bytes():
                body += chunk
                if len(body) > MAX_BODY:
                    raise SeoError("페이지가 너무 큽니다")
        return Page(r.status_code, str(r.url), {k.lower(): v for k, v in r.headers.items()},
                    body.decode(r.encoding or "utf-8", errors="replace"))


def _get(url: str):
    """리다이렉트를 한 단계씩 따라가며 매번 주소를 검사한다(검사 안 한 내부 주소로 넘어가지 않게)."""
    try:
        for _ in range(MAX_REDIRECTS + 1):
            r = _fetch_once(url)
            if not (300 <= r.status_code < 400 and "location" in r.headers):
                return r
            url = check_url(str(httpx.URL(r.url).join(r.headers["location"])))
        raise SeoError(f"리다이렉트가 {MAX_REDIRECTS}번을 넘습니다")
    except httpx.HTTPError:
        return None


def _extra(url: str):
    """robots.txt 등 부가 파일: 막히거나 너무 크면 없는 것으로 본다(본 페이지 점검은 계속)."""
    try:
        return _get(url)
    except SeoError:
        return None


def fetch(url: str) -> dict:
    r = _get(check_url(url))
    if r is None:
        raise SeoError("페이지에 접속하지 못했습니다")
    final = str(r.url)
    # Workers의 httpx(JS fetch)는 리다이렉트를 스스로 따라갈 수 있어 최종 주소도 다시 검사한다
    check_url(final)
    origin = "{0.scheme}://{0.netloc}".format(urlsplit(final))
    robots = _extra(origin + "/robots.txt")
    robots_txt = robots.text[:100_000] if robots is not None and robots.status_code == 200 else None
    sitemaps = [ln.split(":", 1)[1].strip() for ln in (robots_txt or "").splitlines() if ln.lower().startswith("sitemap:")]
    if not sitemaps:
        sm = _extra(origin + "/sitemap.xml")
        sitemaps = [origin + "/sitemap.xml"] if sm is not None and sm.status_code == 200 else []
    llms = _extra(origin + "/llms.txt")
    return {"url": final, "status": r.status_code, "x_robots": r.headers.get("x-robots-tag", ""),
            "html": r.text[:MAX_HTML], "robots": robots_txt, "sitemaps": sitemaps,
            "llms": llms is not None and llms.status_code == 200}
