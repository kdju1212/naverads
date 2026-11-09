"""Claude 도구: 비즈머니, 노출 제한 IP, 비즈채널 등록·재검수, 타기팅(켜기/끄기만), 대용량 보고서,
입찰가 예측, 검수 이력, 키워드·소재 재검수, 소재 복사(OFF로), 확장검색·ADVoost Max(끄기만) 설정.
웹 화면 없이 Claude(MCP)에서만 쓴다(2026-11-09 결정). 요청 형식 근거는 docs/naver-searchad-api, 실계정 미확인.
타기팅·IP·비즈채널은 하루예산 합계와 입찰가를 바꾸지 않아 안전장치 검사 없이 수정 권한과 작업 기록만 확인한다.
입찰 가중치(타기팅별 입찰가 50~500%)는 광고비가 크게 늘 수 있어 승인 정책을 정할 때까지 만들지 않는다."""
import ipaddress
from datetime import date, datetime, timedelta

from fastapi import HTTPException

from . import bulk, safety
from .access import resolve_account_ids
from .models import KST, AuditLog, Membership, today_kst
from .naver import NaverApiError

TARGET_TYPES = {"SD": "요일·시간", "RL": "지역", "DV": "기기(PC·모바일)", "AG": "연령", "GN": "성별"}
REPORT_TYPES = ["AD", "AD_DETAIL", "AD_CONVERSION", "AD_CONVERSION_DETAIL", "ADEXTENSION", "ADEXTENSION_CONVERSION", "EXPKEYWORD",
                "SHOPPINGKEYWORD_DETAIL", "SHOPPINGKEYWORD_CONVERSION_DETAIL", "SHOPPINGBRANDPRODUCT", "SHOPPINGBRANDPRODUCT_CONVERSION",
                "CRITERION", "CRITERION_CONVERSION"]
PREVIEW_LINES = 50  # shortcut: 칸 이름을 모르는 원본이라 앞부분만 넘긴다, 실계정 파일로 칸을 확인하면 이름 붙여 요약

_ACC = {"workspace_id": {"type": "integer"}, "ad_account_id": {"type": "integer"}}
_GRP = {**_ACC, "adgroup_id": {"type": "string", "description": "광고그룹 네이버 ID"}}

TOOLS = [
    {"name": "get_bizmoney", "description": "비즈머니(광고비 충전금) 잔액·잠금 상태와 내역(원, VAT 포함, 날짜는 한국 기준). 기간을 비우면 최근 7일. "
     "history: period 일별 잔액·사용(기본), charge 충전 내역, exhaust 광고비 차감 내역(campaignTp 1 파워링크, 2 쇼핑검색). 충전·환불은 API로 할 수 없다.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "ad_account_id"], "properties": {
         **_ACC, "since": {"type": "string", "description": "YYYY-MM-DD"}, "until": {"type": "string", "description": "YYYY-MM-DD"},
         "history": {"enum": ["period", "charge", "exhaust"]}}},
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
    {"name": "get_stat_report", "description": "대용량 보고서 상태. BUILT면 EXPKEYWORD(확장검색 검색어)는 검색어별 노출·클릭·비용 합계(비용 큰 순 100개, 원은 VAT 제외), "
     f"그 밖의 유형은 파일 앞 {PREVIEW_LINES}줄(원본 TSV, 칸 이름 없음)과 전체 줄 수. NONE이면 그날 데이터 없음. "
     "검색어 결과로 제외검색어를 추천할 땐 클릭·비용은 있는데 상품과 맞지 않는 검색어를 고르고, add_exp_negative_keywords로 등록한다. "
     "REGIST·RUNNING·WAITING·AGGREGATING이면 잠시 뒤 다시 부른다.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "ad_account_id", "report_job_id"], "properties": {
         **_ACC, "report_job_id": {"type": "integer"}}},
     "annotations": {"readOnlyHint": True}},
    {"name": "estimate_bid", "description": "입찰가 예측(네이버 통계 기반, 조회만). kind: position 원하는 순위의 평균 입찰가(positions 필요), "
     "median 중간 입찰가, minimum 최소 노출 입찰가, performance 입찰가별 예상 노출·클릭·비용(bids 필요, 파워링크만). "
     "product WEB_SITE면 keys는 키워드 문구(by_id면 키워드 ID), SHOPPING이면 상품 ID(by_id면 소재 ID)이고 position·minimum만 된다. "
     "device PC|MOBILE. 한 번에 200개까지. 예측은 과거 통계라 실제 순위·비용과 다를 수 있다고 함께 알린다.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "ad_account_id", "kind", "keys", "device"], "properties": {
         **_ACC, "kind": {"enum": ["position", "median", "minimum", "performance"]}, "product": {"enum": ["WEB_SITE", "SHOPPING"]},
         "keys": {"type": "array", "items": {"type": "string"}, "minItems": 1}, "by_id": {"type": "boolean"},
         "device": {"enum": ["PC", "MOBILE"]}, "positions": {"type": "array", "items": {"type": "integer"}, "description": "position: 1~15"},
         "bids": {"type": "array", "items": {"type": "integer"}, "description": "performance: 입찰가(원)"},
         "period": {"enum": ["DAY", "MONTH"], "description": "median·minimum: 어제(DAY) 또는 최근 28일(MONTH, 기본)"}}},
     "annotations": {"readOnlyHint": True}},
    {"name": "get_inspect_history", "description": "비즈채널·소재·확장소재·키워드의 검수 결과와 보류·반려 사유(최근 3개월). ids 최대 100개.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "ad_account_id", "ids"], "properties": {
         **_ACC, "ids": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 100}}},
     "annotations": {"readOnlyHint": True}},
    {"name": "request_inspect", "description": "보류·반려된 키워드나 소재를 다시 검수해 달라고 요청한다(바로 실행). 반려 사유(get_inspect_history)를 고친 뒤에 쓴다. "
     "대상을 채팅에 표로 보여 준 뒤 호출.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "ad_account_id", "kind", "naver_id"], "properties": {
         **_ACC, "kind": {"enum": ["keyword", "ad"]}, "naver_id": {"type": "string"}}},
     "annotations": {"destructiveHint": True}},
    {"name": "copy_ads", "description": "소재를 다른 광고그룹으로 복사한다(바로 실행). 복사본은 OFF로 만들어지고 검수를 다시 받는다. "
     "복사할 소재·대상 광고그룹을 채팅에 표로 보여 준 뒤 호출.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "ad_account_id", "ad_ids", "target_adgroup_id"], "properties": {
         **_ACC, "ad_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 20}, "target_adgroup_id": {"type": "string"}}},
     "annotations": {"destructiveHint": True}},
    {"name": "set_adgroup_options", "description": "파워링크 광고그룹의 확장검색(use_exp_search: 등록 안 한 비슷한 검색어에도 노출), 확장검색 예산 비율, ADVoost Max(ai_ads_opt_in) 설정(바로 실행). "
     "확장검색을 켜면 노출·비용이 늘 수 있다. ADVoost Max는 끄기만 된다(켜기는 웹 승인 대상이라 아직 없음). 지금 → 바뀔 값을 채팅에 표로 보여 준 뒤 호출.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "ad_account_id", "adgroup_id"], "properties": {
         **_GRP, "use_exp_search": {"type": "boolean"}, "ai_ads_opt_in": {"type": "boolean"},
         "exp_search_budget_ratio": {"type": "integer", "description": "광고그룹 예산 중 확장검색에 쓸 비율 1~100(%, 기본 100)"}}},
     "annotations": {"destructiveHint": True}},
    {"name": "get_media_target", "description": "광고그룹이 광고를 내보내는 매체: 검색 매체(search)·콘텐츠 매체(contents, 블로그·카페 등) 각각 naver(네이버)·partner(파트너 사이트). "
     "type 1이면 모든 매체.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "ad_account_id", "adgroup_id"], "properties": _GRP},
     "annotations": {"readOnlyHint": True}},
    {"name": "set_media_target", "description": "광고그룹의 노출 매체를 바꾼다(바로 실행). search·contents에 켤 매체(naver, partner)를 넣고, 넣지 않은 쪽은 꺼진다. "
     "둘 다 naver·partner면 모든 매체. 예: 검색에만 내기 = search [naver, partner], contents []. 지금 → 바뀔 매체를 채팅에 표로 보여 준 뒤 호출.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "ad_account_id", "adgroup_id", "search", "contents"], "properties": {
         **_GRP, "search": {"type": "array", "items": {"enum": ["naver", "partner"]}},
         "contents": {"type": "array", "items": {"enum": ["naver", "partner"]}}}},
     "annotations": {"destructiveHint": True}},
    {"name": "list_exp_negative_keywords", "description": "확장검색 제외검색어 목록(확장검색으로 이 검색어엔 광고를 안 냄). 일반 제외검색어는 list_negative_keywords.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "ad_account_id", "adgroup_id"], "properties": _GRP},
     "annotations": {"readOnlyHint": True}},
    {"name": "add_exp_negative_keywords", "description": "확장검색 제외검색어를 등록한다(바로 실행, 한 번에 20개까지). 검색어 보고서(EXPKEYWORD)에서 돈만 쓰고 맞지 않는 검색어를 막을 때 쓴다. "
     "등록할 검색어와 그 검색어의 비용·클릭을 채팅에 표로 보여 준 뒤 호출.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "ad_account_id", "adgroup_id", "keywords"], "properties": {
         **_GRP, "keywords": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 20}}},
     "annotations": {"destructiveHint": True}},
    {"name": "delete_exp_negative_keyword", "description": "확장검색 제외검색어를 지운다(바로 실행, 그 검색어에 다시 노출될 수 있음). ID는 list_exp_negative_keywords의 naver_id.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "ad_account_id", "adgroup_id", "naver_id"], "properties": {
         **_GRP, "naver_id": {"type": "string"}, "keyword": {"type": "string", "description": "작업 기록용"}}},
     "annotations": {"destructiveHint": True}},
    {"name": "set_keyword_url", "description": "키워드별 연결 URL을 바꾼다(바로 실행). 이 키워드로 클릭한 사람을 소재 URL 대신 이 주소로 보낸다. "
     "키워드·지금 URL → 바뀔 URL을 채팅에 표로 보여 준 뒤 호출.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "ad_account_id", "keyword_id", "pc_url"], "properties": {
         **_ACC, "keyword_id": {"type": "string"}, "pc_url": {"type": "string"}, "mobile_url": {"type": "string", "description": "비우면 PC URL"}}},
     "annotations": {"destructiveHint": True}},
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


def _won(v):
    return round(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v


def _money_row(r: dict) -> dict:
    """settleDt는 밀리초 유닉스 시각, 금액은 VAT 포함 소수 → 한국 날짜와 원 단위. 0원 칸은 뺀다."""
    out = {k: _won(v) for k, v in r.items() if k not in ("customerId", "settleDt") and v not in (0, None)}
    if isinstance(r.get("settleDt"), (int, float)):
        out["date"] = datetime.fromtimestamp(r["settleDt"] / 1000, KST).date().isoformat()
    return out


def call_tool(db, m: Membership, name: str, a: dict):
    acc = int(a["ad_account_id"])
    if name == "get_bizmoney":
        until = date.fromisoformat(a["until"]) if a.get("until") else today_kst()
        since = date.fromisoformat(a["since"]) if a.get("since") else until - timedelta(days=6)
        if since > until or (until - since).days > 92:
            raise HTTPException(400, "기간은 93일 이내로")
        kind = a.get("history") or "period"
        if kind not in ("period", "charge", "exhaust"):
            raise HTTPException(400, "history는 period, charge, exhaust 중 하나")
        c = _client(db, m, acc, False)
        bal = _naver(c.bizmoney, "비즈머니 조회")
        rows = _naver(lambda: c.bizmoney_history(kind, since, until), "비즈머니 내역 조회")
        return {"balance": {**bal, "bizmoney": _won(bal.get("bizmoney"))}, "history": kind, "rows": [_money_row(r) for r in rows]}
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
        if job.get("reportTp") == "EXPKEYWORD":
            return {**job, **search_terms(lines)}
        return {**job, "total_lines": len(lines), "preview": lines[:PREVIEW_LINES]}
    if name == "get_media_target":
        c = _client(db, m, acc, False)
        return _naver(lambda: c.media_target(a["adgroup_id"]), "매체 설정 조회")["target"]
    if name == "set_media_target":
        pick = {k: sorted({x for x in a.get(k) or [] if x in ("naver", "partner")}) for k in ("search", "contents")}
        if not pick["search"] and not pick["contents"]:
            raise HTTPException(400, "검색·콘텐츠 매체 중 하나는 켜야 해요")
        everything = pick["search"] == pick["contents"] == ["naver", "partner"]
        target = ({"type": 1, "search": [], "contents": [], "black": {"media": None, "mediaGroup": None}} if everything
                  else {"type": 2, **pick, "black": {"media": [], "mediaGroup": []}})
        target["white"] = {"media": None, "mediaGroup": None}
        c = _client(db, m, acc, True)
        out = _naver(lambda: c.set_media_target(a["adgroup_id"], target), "매체 설정 변경")
        _log(db, m, acc, "UPDATE", "adgroup", a["adgroup_id"], "media",
             after="모든 매체" if everything else f"검색:{'+'.join(pick['search']) or '없음'} 콘텐츠:{'+'.join(pick['contents']) or '없음'}")
        return out
    if name == "list_exp_negative_keywords":
        c = _client(db, m, acc, False)
        return [{"naver_id": k["nccAdgroupRestrictKwdId"], "keyword": k["keyword"]}
                for k in _naver(lambda: c.list_restricted_keywords(a["adgroup_id"], "EXP_SEARCH"), "확장검색 제외검색어 조회")]
    if name == "add_exp_negative_keywords":
        kws = list(dict.fromkeys(k.strip() for k in a["keywords"] if k.strip()))[:20]
        if not kws:
            raise HTTPException(400, "검색어를 넣으세요")
        c = _client(db, m, acc, True)
        done, failed = [], []
        for k in kws:  # 하나가 거부돼도 나머지는 등록하고 결과를 나눠 알린다
            try:
                r = c.create_restricted_keyword(a["adgroup_id"], k, "EXP_SEARCH")
                done.append({"naver_id": r["nccAdgroupRestrictKwdId"], "keyword": k})
                _log(db, m, acc, "CREATE", "negative_keyword", r["nccAdgroupRestrictKwdId"], "exp_search", after=k)
            except NaverApiError as e:
                failed.append({"keyword": k, "error": bulk.UNKNOWN if str(e).startswith("네트워크 오류") else str(e)})
        return {"added": done, "failed": failed}
    if name == "delete_exp_negative_keyword":
        c = _client(db, m, acc, True)
        try:  # 지우면 그 검색어에 다시 노출될 수 있다 → 대량 작업의 제외검색어 삭제와 같은 안전장치
            safety.check(db, m.workspace_id, acc, [("expose",)], lambda: c)
        except safety.SafetyError as e:
            raise HTTPException(400, str(e))
        _naver(lambda: c.delete_restricted_keyword(a["adgroup_id"], a["naver_id"]), "확장검색 제외검색어 삭제")
        _log(db, m, acc, "DELETE", "negative_keyword", a["naver_id"], "exp_search", before=a.get("keyword"))
        return {"ok": True}
    if name == "set_keyword_url":
        pc, mo = a["pc_url"].strip(), (a.get("mobile_url") or a["pc_url"]).strip()
        if not all(u.startswith(("http://", "https://")) for u in (pc, mo)):
            raise HTTPException(400, "URL은 http(s):// 로 시작해야 해요")
        c = _client(db, m, acc, True)
        _naver(lambda: c.set_keyword_url(a["keyword_id"], pc, mo), "키워드 URL 변경")
        _log(db, m, acc, "UPDATE", "keyword", a["keyword_id"], "url", after=pc)
        return {"ok": True, "pc_url": pc, "mobile_url": mo}
    if name == "estimate_bid":
        return _estimate(_client(db, m, acc, False), a)
    if name == "get_inspect_history":
        c = _client(db, m, acc, False)
        return _naver(lambda: c.inspect_history(a["ids"][:100]), "검수 이력 조회")
    if name == "request_inspect":
        if a["kind"] not in ("keyword", "ad"):
            raise HTTPException(400, "kind는 keyword 또는 ad")
        c = _client(db, m, acc, True)
        out = _naver(lambda: c.request_inspect(a["kind"], a["naver_id"]), "재검수 요청")
        _log(db, m, acc, "UPDATE", a["kind"], a["naver_id"], "inspect", after="재검수 요청")
        return out
    if name == "copy_ads":
        ids = list(dict.fromkeys(a["ad_ids"]))[:20]
        c = _client(db, m, acc, True)
        out = _naver(lambda: c.copy_ads(ids, a["target_adgroup_id"]), "소재 복사")
        for x in out or []:
            _log(db, m, acc, "CREATE", "ad", x.get("nccAdId", a["target_adgroup_id"]), "copy", after="OFF로 복사")
        return out
    if name == "set_adgroup_options":
        opts = {k: a[f] for f, k in (("use_exp_search", "useExpSearch"), ("ai_ads_opt_in", "aiAdsOptIn")) if isinstance(a.get(f), bool)}
        ratio = a.get("exp_search_budget_ratio")
        if ratio is not None:
            if not isinstance(ratio, int) or isinstance(ratio, bool) or not 1 <= ratio <= 100:
                raise HTTPException(400, "확장검색 예산 비율은 1~100(%)")
            opts["expSearchBudgetRatio"] = ratio
        if not opts:
            raise HTTPException(400, "use_exp_search, exp_search_budget_ratio, ai_ads_opt_in 중 하나를 넣으세요")
        if opts.get("aiAdsOptIn"):  # 정책(2026-11-02): ADVoost 켜기는 웹 승인 대상
            raise HTTPException(400, "ADVoost Max 켜기는 웹 승인 대상이라 아직 Claude에서 켤 수 없어요. 네이버 광고관리에서 켜 주세요")
        c = _client(db, m, acc, True)
        out = _naver(lambda: c.set_adgroup_options(a["adgroup_id"], opts), "광고그룹 설정 변경")
        for k, v in opts.items():
            _log(db, m, acc, "UPDATE", "adgroup", a["adgroup_id"], k[:20], after=str(v) if isinstance(v, int) and not isinstance(v, bool) else ("ON" if v else "OFF"))
        return {k: out.get(k) for k in ("nccAdgroupId", "name", "useExpSearch", "expSearchBudgetRatio", "aiAdsOptIn")}
    raise HTTPException(400, f"알 수 없는 도구: {name}")


def _estimate(c, a: dict):
    kind, product, keys, device = a["kind"], a.get("product") or "WEB_SITE", list(dict.fromkeys(a["keys"])), a["device"]
    if device not in ("PC", "MOBILE") or not keys or len(keys) > 200:
        raise HTTPException(400, "device는 PC·MOBILE, keys는 1~200개")
    shop = product == "SHOPPING"
    if shop and kind not in ("position", "minimum"):
        raise HTTPException(400, "쇼핑은 position·minimum만 예측할 수 있어요")
    base = "npla-estimate" if shop else "estimate"
    tp = "id" if a.get("by_id") else ("product" if shop else "keyword")
    if kind == "position":
        pos = [p for p in (a.get("positions") or []) if isinstance(p, int) and 1 <= p <= 15]
        if not pos:
            raise HTTPException(400, "positions에 1~15위를 넣으세요")
        body = {"device": device, "items": [{"key": k, "position": p} for k in keys for p in pos][:200]}
        return _naver(lambda: c.estimate(f"{base}/average-position-bid/{tp}", body), "입찰가 예측")
    if kind in ("median", "minimum"):
        path = {"median": "median-bid", "minimum": "exposure-minimum-bid"}[kind]
        body = {"device": device, "period": a.get("period") or "MONTH", "items": keys}
        return _naver(lambda: c.estimate(f"{base}/{path}/{tp}", body), "입찰가 예측")
    if kind != "performance":
        raise HTTPException(400, "kind는 position, median, minimum, performance 중 하나")
    bids = [b for b in (a.get("bids") or []) if isinstance(b, int) and 70 <= b <= 100_000]
    if not bids:
        raise HTTPException(400, "bids에 70~100,000원 입찰가를 넣으세요")
    if a.get("by_id"):  # 여러 키워드용(performance-bulk)은 문구만 받는다
        raise HTTPException(400, "성과 예측은 키워드 문구로만 할 수 있어요")
    items = [{"keyword": k, "bid": b, "device": device, "keywordplus": False} for k in keys for b in bids][:200]
    return _naver(lambda: c.estimate("estimate/performance-bulk", {"items": items}), "성과 예측")


# 확장검색 검색어 보고서(EXPKEYWORD) 칸: 실계정 파일(2026-11-08, 12칸)에서 클릭당 비용이 계정 평균과 맞는 것으로 확인.
# 7번째(0~2)·마지막(전부 0) 칸은 의미 미확인이라 쓰지 않는다
EXP_COLS = {"adgroup_id": 3, "term": 4, "device": 6, "impressions": 8, "clicks": 9, "cost": 10}


def search_terms(lines: list[str], top: int = 100) -> dict:
    """검색어별(광고그룹·검색어) 노출·클릭·비용 합계, 비용 큰 순. 기기·매체별로 나뉜 줄을 합친다."""
    agg: dict[tuple, dict] = {}
    for ln in lines:
        f = ln.split("\t")
        if len(f) < 11:
            continue
        key = (f[EXP_COLS["adgroup_id"]], f[EXP_COLS["term"]])
        r = agg.setdefault(key, {"adgroup_id": key[0], "search_term": key[1], "impressions": 0, "clicks": 0, "cost": 0})
        for k in ("impressions", "clicks", "cost"):
            r[k] += int(f[EXP_COLS[k]]) if f[EXP_COLS[k]].isdigit() else 0
    rows = sorted(agg.values(), key=lambda r: (-r["cost"], -r["clicks"], -r["impressions"]))
    return {"terms": len(rows), "total_cost": sum(r["cost"] for r in rows), "total_clicks": sum(r["clicks"] for r in rows), "rows": rows[:top]}
