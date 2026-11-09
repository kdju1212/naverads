"""Claude 도구: 비즈머니, 노출 제한 IP, 비즈채널 등록·재검수, 타기팅(켜기/끄기만), 대용량 보고서.
웹 화면 없이 Claude(MCP)에서만 쓴다(2026-11-09 결정). 요청 형식 근거는 docs/naver-searchad-api, 실계정 미확인.
타기팅·IP·비즈채널은 하루예산 합계와 입찰가를 바꾸지 않아 안전장치 검사 없이 수정 권한과 작업 기록만 확인한다.
입찰 가중치(타기팅별 입찰가 50~500%)는 광고비가 크게 늘 수 있어 승인 정책을 정할 때까지 만들지 않는다."""
import ipaddress
from datetime import date, timedelta

from fastapi import HTTPException

from . import bulk
from .access import resolve_account_ids
from .models import AuditLog, Membership, today_kst
from .naver import NaverApiError

TARGET_TYPES = {"SD": "요일·시간", "RL": "지역", "DV": "기기(PC·모바일)", "AG": "연령", "GN": "성별"}
REPORT_TYPES = ["AD", "AD_DETAIL", "AD_CONVERSION", "AD_CONVERSION_DETAIL", "ADEXTENSION", "ADEXTENSION_CONVERSION", "EXPKEYWORD",
                "SHOPPINGKEYWORD_DETAIL", "SHOPPINGKEYWORD_CONVERSION_DETAIL", "SHOPPINGBRANDPRODUCT", "SHOPPINGBRANDPRODUCT_CONVERSION",
                "CRITERION", "CRITERION_CONVERSION"]
PREVIEW_LINES = 50  # shortcut: 칸 이름을 모르는 원본이라 앞부분만 넘긴다, 실계정 파일로 칸을 확인하면 이름 붙여 요약

_ACC = {"workspace_id": {"type": "integer"}, "ad_account_id": {"type": "integer"}}
_GRP = {**_ACC, "adgroup_id": {"type": "string", "description": "광고그룹 네이버 ID"}}

TOOLS = [
    {"name": "get_bizmoney", "description": "비즈머니(광고비 충전금) 잔액·잠금 상태와 일별 사용 현황(VAT 포함). 기간을 비우면 최근 7일. 충전·환불은 API로 할 수 없다.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "ad_account_id"], "properties": {
         **_ACC, "since": {"type": "string", "description": "YYYY-MM-DD"}, "until": {"type": "string", "description": "YYYY-MM-DD"}}},
     "annotations": {"readOnlyHint": True}},
    {"name": "list_ip_exclusions", "description": "광고를 보여 주지 않게 막은 IP 목록(부정 클릭 방지). 계정 전체에 적용된다.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "ad_account_id"], "properties": _ACC}, "annotations": {"readOnlyHint": True}},
    {"name": "add_ip_exclusion", "description": "IP 하나에 광고가 안 보이게 막는다(바로 실행, 계정 전체). 막을 IP와 메모를 채팅에 표로 보여 준 뒤 호출. "
     "가게·회사 IP를 막으면 사장님도 내 광고를 못 본다고 함께 알린다.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "ad_account_id", "ip"], "properties": {
         **_ACC, "ip": {"type": "string"}, "memo": {"type": "string", "description": "25자 이내"}}},
     "annotations": {"destructiveHint": True}},
    {"name": "delete_ip_exclusion", "description": "막아 둔 IP를 풀어 그 IP에 다시 광고가 보이게 한다(바로 실행). 풀 IP를 채팅에 표로 보여 준 뒤 호출. ID는 list_ip_exclusions의 ipFilterId.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "ad_account_id", "ip_filter_id"], "properties": {
         **_ACC, "ip_filter_id": {"type": "integer"}, "ip": {"type": "string", "description": "작업 기록용"}}},
     "annotations": {"destructiveHint": True}},
    {"name": "create_site_channel", "description": "파워링크에 쓸 웹사이트 비즈채널을 등록한다(바로 실행, 네이버 검수 후 사용 가능). 이름과 URL을 채팅에 표로 보여 준 뒤 호출. "
     "쇼핑몰·플레이스 채널은 네이버 광고관리에서 등록한다. 검수 상태는 list_channels로 본다.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "ad_account_id", "name", "url"], "properties": {
         **_ACC, "name": {"type": "string"}, "url": {"type": "string", "description": "http(s)://로 시작"}}},
     "annotations": {"destructiveHint": True}},
    {"name": "reinspect_channel", "description": "검수에서 보류·반려된 비즈채널을 다시 검수해 달라고 요청한다(바로 실행). 사이트를 고친 뒤에 쓴다.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "ad_account_id", "channel_id"], "properties": {
         **_ACC, "channel_id": {"type": "string", "description": "list_channels의 naver_id"}}},
     "annotations": {"destructiveHint": True}},
    {"name": "get_targeting", "description": "광고그룹의 타기팅 설정. type: SD 요일·시간, RL 지역, DV 기기, AG 연령, GN 성별. codes=true면 그 유형에 쓸 수 있는 코드표도 함께.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "ad_account_id", "adgroup_id", "type"], "properties": {
         **_GRP, "type": {"enum": list(TARGET_TYPES)}, "codes": {"type": "boolean"}}},
     "annotations": {"readOnlyHint": True}},
    {"name": "set_targeting", "description": "광고그룹 타기팅을 유형별로 바꾼다(바로 실행). codes에 넣은 코드만 켜지고 빠진 코드는 모두 꺼진다. "
     "먼저 get_targeting으로 지금 값과 코드표를 보고, 지금 → 바뀔 코드(이름 포함)를 채팅에 표로 보여 준 뒤 호출. 입찰 가중치는 바꾸지 않는다.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "ad_account_id", "adgroup_id", "type", "codes"], "properties": {
         **_GRP, "type": {"enum": list(TARGET_TYPES)}, "codes": {"type": "array", "items": {"type": "string"}, "minItems": 1}}},
     "annotations": {"destructiveHint": True}},
    {"name": "request_stat_report", "description": "하루치 대용량 성과 보고서(TSV) 생성을 네이버에 요청한다. 만들어지는 데 시간이 걸리니 돌려받은 report_job_id로 get_stat_report를 부른다. "
     "AD 광고 성과, AD_DETAIL 상세, AD_CONVERSION 전환, EXPKEYWORD 확장검색 검색어, SHOPPINGKEYWORD_DETAIL 쇼핑 검색어, CRITERION 타기팅별 등. 보관 14일.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "ad_account_id", "report_type", "date"], "properties": {
         **_ACC, "report_type": {"enum": REPORT_TYPES}, "date": {"type": "string", "description": "YYYY-MM-DD(어제 이전)"}}},
     "annotations": {"readOnlyHint": True}},
    {"name": "get_stat_report", "description": f"대용량 보고서 상태. BUILT면 파일 앞 {PREVIEW_LINES}줄(원본 TSV, 칸 이름 없음)과 전체 줄 수, NONE이면 그날 데이터 없음. "
     "REGIST·RUNNING·WAITING·AGGREGATING이면 잠시 뒤 다시 부른다.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "ad_account_id", "report_job_id"], "properties": {
         **_ACC, "report_job_id": {"type": "integer"}}},
     "annotations": {"readOnlyHint": True}},
]


def _client(db, m: Membership, acc: int, edit: bool):
    resolve_account_ids(db, m, [acc], edit=edit)
    return bulk._client(db, m.workspace_id, acc)


def _naver(fn, what: str):
    try:
        return fn()
    except NaverApiError as e:  # 응답을 못 받은 쓰기는 됐을 수 있다 → 다시 보내지 말고 네이버에서 확인하게
        raise HTTPException(400, bulk.UNKNOWN if str(e).startswith("네트워크 오류") else f"네이버 {what} 실패: {e}")


def _log(db, m, acc, action, entity_type, naver_id, field=None, before=None, after=None):
    db.add(AuditLog(workspace_id=m.workspace_id, user_id=m.user_id, ad_account_id=acc, action=action, entity_type=entity_type,
                    naver_id=str(naver_id)[:50], field=field, before=before and before[:50], after=after and after[:50]))
    db.commit()


def call_tool(db, m: Membership, name: str, a: dict):
    acc = int(a["ad_account_id"])
    if name == "get_bizmoney":
        until = date.fromisoformat(a["until"]) if a.get("until") else today_kst()
        since = date.fromisoformat(a["since"]) if a.get("since") else until - timedelta(days=6)
        if since > until or (until - since).days > 92:
            raise HTTPException(400, "기간은 93일 이내로")
        c = _client(db, m, acc, False)
        return {"balance": _naver(c.bizmoney, "비즈머니 조회"), "daily": _naver(lambda: c.bizmoney_daily(since, until), "비즈머니 현황 조회")}
    if name == "list_ip_exclusions":
        return _naver(_client(db, m, acc, False).list_ip_exclusions, "노출 제한 IP 조회")
    if name == "add_ip_exclusion":
        try:
            ip = str(ipaddress.ip_address(a["ip"].strip()))
        except ValueError:
            raise HTTPException(400, f"IP 주소 형식이 아닙니다: {a['ip']}")
        memo = (a.get("memo") or "").strip()
        if len(memo) > 25:
            raise HTTPException(400, "메모는 25자 이내")
        c = _client(db, m, acc, True)
        out = _naver(lambda: c.add_ip_exclusion(ip, memo), "노출 제한 IP 등록")
        _log(db, m, acc, "CREATE", "ip_exclusion", (out or {}).get("ipFilterId", ip), "ip", after=ip)
        return out
    if name == "delete_ip_exclusion":
        c = _client(db, m, acc, True)
        _naver(lambda: c.delete_ip_exclusion(int(a["ip_filter_id"])), "노출 제한 IP 삭제")
        _log(db, m, acc, "DELETE", "ip_exclusion", a["ip_filter_id"], "ip", before=a.get("ip"))
        return {"ok": True}
    if name == "create_site_channel":
        url, nm = a["url"].strip(), a["name"].strip()
        if not nm or not url.startswith(("http://", "https://")):
            raise HTTPException(400, "이름과 http(s):// 로 시작하는 URL을 입력하세요")
        c = _client(db, m, acc, True)
        out = _naver(lambda: c.create_site_channel(nm, url), "비즈채널 등록")
        _log(db, m, acc, "CREATE", "channel", (out or {}).get("nccBusinessChannelId", nm), "site", after=url)
        return out
    if name == "reinspect_channel":
        c = _client(db, m, acc, True)
        out = _naver(lambda: c.reinspect_channel(a["channel_id"]), "비즈채널 재검수 요청")
        _log(db, m, acc, "UPDATE", "channel", a["channel_id"], "inspect", after="재검수 요청")
        return out
    if name == "get_targeting":
        tp = a["type"]
        if tp not in TARGET_TYPES:
            raise HTTPException(400, f"type은 {', '.join(TARGET_TYPES)} 중 하나")
        c = _client(db, m, acc, False)
        out = {"type": TARGET_TYPES[tp], "current": _naver(lambda: c.targeting(a["adgroup_id"], tp), "타기팅 조회")}
        if a.get("codes"):
            out["codes"] = _naver(lambda: c.targeting_codes(tp), "타기팅 코드표 조회")
        return out
    if name == "set_targeting":
        tp, codes = a["type"], list(dict.fromkeys(str(x).strip() for x in a["codes"] if str(x).strip()))
        if tp not in TARGET_TYPES:
            raise HTTPException(400, f"type은 {', '.join(TARGET_TYPES)} 중 하나")
        if not codes:  # 빈 목록이면 네이버가 그 유형을 모두 끈다 → 실수로 보고 막는다
            raise HTTPException(400, "켤 코드를 하나 이상 넣으세요")
        c = _client(db, m, acc, True)
        before = ",".join(x.get("dictionaryCode", "") for x in _naver(lambda: c.targeting(a["adgroup_id"], tp), "타기팅 조회"))
        out = _naver(lambda: c.set_targeting(a["adgroup_id"], tp, codes), "타기팅 변경")
        _log(db, m, acc, "UPDATE", "targeting", a["adgroup_id"], tp, before=before, after=",".join(codes))
        return out
    if name == "request_stat_report":
        if a["report_type"] not in REPORT_TYPES:
            raise HTTPException(400, "지원하지 않는 보고서 유형")
        day = date.fromisoformat(a["date"])
        if day >= today_kst():
            raise HTTPException(400, "어제 이전 날짜만 받을 수 있어요")
        c = _client(db, m, acc, False)
        return _naver(lambda: c.create_stat_report(a["report_type"], day), "보고서 요청")
    if name == "get_stat_report":
        c = _client(db, m, acc, False)
        job = _naver(lambda: c.get_stat_report(int(a["report_job_id"])), "보고서 조회")
        if job.get("status") != "BUILT" or not job.get("downloadUrl"):
            return job
        lines = _naver(lambda: c.stat_file(job), "보고서 다운로드").splitlines()
        return {**job, "total_lines": len(lines), "preview": lines[:PREVIEW_LINES]}
    raise HTTPException(400, f"알 수 없는 도구: {name}")
