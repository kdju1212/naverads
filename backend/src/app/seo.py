"""SEO·GEO 점검용 페이지 가져오기. 판정은 브라우저(frontend/lib/seo.ts)가 한다(HTML 분석을 파이썬이 하면 CPU 한도 초과)."""
import ipaddress
from urllib.parse import urlsplit

import httpx

# 스마트스토어·브랜드스토어는 외부 수집을 막아 점검 결과가 틀리게 나온다
BLOCKED_HOSTS = ("smartstore.naver.com", "brand.naver.com")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
MAX_HTML = 2_000_000


class SeoError(Exception):
    pass


def check_url(url: str) -> str:
    """점검할 수 없는 주소면 SeoError. shortcut: 도메인 이름이 내부 IP를 가리키는 경우는 막지 못한다(Workers는 내부망이 없어 운영에선 문제없음)"""
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    if parts.scheme not in ("http", "https") or not host:
        raise SeoError("http:// 또는 https://로 시작하는 주소를 넣어 주세요")
    if any(host == h or host.endswith("." + h) for h in BLOCKED_HOSTS):
        raise SeoError("스마트스토어·브랜드스토어 주소는 점검할 수 없습니다 (네이버가 외부 수집을 막아 결과가 정확하지 않음)")
    try:
        ip = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        ip = None
    if host == "localhost" or (ip and not ip.is_global):
        raise SeoError("내부 주소는 점검할 수 없습니다")
    return url.strip()


def _get(url: str):
    try:
        return httpx.get(url, headers={"User-Agent": UA}, timeout=15, follow_redirects=True)
    except httpx.HTTPError:
        return None


def fetch(url: str) -> dict:
    r = _get(check_url(url))
    if r is None:
        raise SeoError("페이지에 접속하지 못했습니다")
    final = str(r.url)
    check_url(final)  # 단축 주소 등이 스마트스토어로 넘어가는 경우도 막는다
    origin = "{0.scheme}://{0.netloc}".format(urlsplit(final))
    robots = _get(origin + "/robots.txt")
    robots_txt = robots.text[:100_000] if robots is not None and robots.status_code == 200 else None
    sitemaps = [ln.split(":", 1)[1].strip() for ln in (robots_txt or "").splitlines() if ln.lower().startswith("sitemap:")]
    if not sitemaps:
        sm = _get(origin + "/sitemap.xml")
        sitemaps = [origin + "/sitemap.xml"] if sm is not None and sm.status_code == 200 else []
    llms = _get(origin + "/llms.txt")
    return {"url": final, "status": r.status_code, "x_robots": r.headers.get("x-robots-tag", ""),
            "html": r.text[:MAX_HTML], "robots": robots_txt, "sitemaps": sitemaps,
            "llms": llms is not None and llms.status_code == 200}
