"""메타 광고 조회를 Claude 도구로(작업정리 32). 구글 google_ads_search처럼 기능마다 도구를 만들지 않고
메타 Graph API GET을 그대로 받는다: 광고세트·광고별·일별·나이·성별·게재 위치 성과, 광고 목록·예산, 소재, 검토 거부 사유, 픽셀, 지출 한도.
조회만(연결 토큰은 ads_read, 리드·페이지·카탈로그·광고 라이브러리는 토큰에 그 권한이 있을 때만). Graph API는 GET에 method=post 같은 덮어쓰기 칸을 받아 줘서 그 칸은 막는다."""
import json
import re

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .access import ADMIN_ROLES
from .channels import ChannelError, _meta_get
from .models import ChannelConnection, Membership
from .security import decrypt

ROWS = 200
PATH = re.compile(r"(act_\d+|\d+)(/[a-z_]+)?")
GLOBAL = {"search", "ads_archive", "me/adaccounts", "me/businesses"}  # 관심사·지역 찾기, 광고 라이브러리, 내 계정 목록
BLOCKED = {"method", "access_token", "appsecret_proof", "batch"}


def _conn(db: Session, m: Membership, account_id: str) -> ChannelConnection:
    if m.role not in ADMIN_ROLES:
        raise HTTPException(403, "메타 광고계정은 관리자만 쓸 수 있습니다")
    row = db.scalar(select(ChannelConnection).where(ChannelConnection.workspace_id == m.workspace_id, ChannelConnection.channel == "META",
                                                    ChannelConnection.account_id == str(account_id).strip().removeprefix("act_")))
    if not row:
        raise HTTPException(404, "연결된 메타 광고계정이 아닙니다(list_ad_accounts의 other_channels 확인, 관리자가 웹 설정에서 연결)")
    return row


def search_tool(db: Session, m: Membership, a: dict) -> dict:
    c = _conn(db, m, a["account_id"])
    path = (a.get("path") or "insights").strip().strip("/")
    if path not in GLOBAL and not path.startswith("act_") and not path.split("/")[0].isdigit():
        path = f"act_{c.account_id}/{path}"  # 'insights', 'ads'처럼 계정 아래 목록
    # 객체 ID는 이 연결의 토큰이 볼 수 있는 것만 나온다(같은 비즈니스의 다른 계정 객체도 보일 수 있음 — 토큰을 넣은 관리자 권한 안)
    if (path not in GLOBAL and not PATH.fullmatch(path)) or (path.startswith("act_") and path.split("/")[0] != f"act_{c.account_id}"):
        raise HTTPException(400, f"path는 act_{c.account_id}/insights, act_{c.account_id}/ads, 또는 캠페인·광고세트·광고 ID(/insights) 모양")
    params = {k: v if isinstance(v, str) else json.dumps(v) for k, v in (a.get("params") or {}).items()}
    if bad := BLOCKED & {k.lower() for k in params}:
        raise HTTPException(400, f"조회 도구에서 쓸 수 없는 칸: {', '.join(sorted(bad))}")
    token = decrypt(c.token_enc)
    try:
        if a.get("async_report"):  # 큰 보고서: 메타가 만들어 두면 report_run_id로 상태('<id>')·결과('<id>/insights')를 받는다
            if path != f"act_{c.account_id}/insights":
                raise HTTPException(400, "async_report는 path가 insights일 때만")
            run = _meta_get("/" + path, token, params, post=True)
            return {"account_id": c.account_id, "report_run_id": run.get("report_run_id"),
                    "next": "path에 report_run_id를 넣어 async_status가 Job Completed인지 보고, '<report_run_id>/insights'로 결과를 받는다"}
        data = _meta_get("/" + path, token, params)
        if "data" not in data:  # 객체 하나(계정 정보·광고 하나)
            return {"account_id": c.account_id, "result": data}
        rows = list(data["data"])
        for _ in range(9):  # 페이지 넘김은 200행까지만
            after = (data.get("paging") or {}).get("cursors", {}).get("after") if (data.get("paging") or {}).get("next") else None
            if not after or len(rows) >= ROWS:
                break
            data = _meta_get("/" + path, token, {**params, "after": after})
            rows += data.get("data", [])
    except ChannelError as e:
        raise HTTPException(400, str(e)) from e
    return {"account_id": c.account_id, "rows": len(rows), "data": rows[:ROWS],
            **({"truncated": f"앞 {ROWS}행만 — filtering·sort·time_range로 좁히세요"} if len(rows) > ROWS else {})}


TOOLS = [
    {"name": "meta_ads_search",
     "description": "메타 광고 조회: 메타 Graph API GET을 그대로 실행(앞 200행). path는 계정 아래 목록('insights', 'campaigns', 'adsets', 'ads', 'adcreatives', 'adspixels', 빈칸=insights), "
                    "'act_<계정ID>'(계정 정보), 또는 캠페인·광고세트·광고 ID('123', '123/insights'). params는 Graph API 칸 그대로. 예: "
                    "성과 = insights {level: campaign|adset|ad, fields: 'campaign_name,adset_name,ad_name,impressions,reach,frequency,clicks,spend,cpm,ctr,actions,action_values', "
                    "time_range: {since, until} 또는 date_preset: last_7d, time_increment: 1(일별), breakdowns: 'age,gender' | 'publisher_platform,platform_position' | 'region' | 'device_platform'}; "
                    "전환은 actions의 action_type(omni_purchase·purchase, add_to_cart, initiate_checkout, lead 등, 구매는 omni_purchase 하나만 — 나머지와 겹침), "
                    "광고 순위 진단은 level ad + fields quality_ranking,engagement_rate_ranking,conversion_rate_ranking; "
                    "광고 목록 = ads {fields: 'name,effective_status,adset_id,creative{title,body,image_url,thumbnail_url,object_story_spec,call_to_action_type},ad_review_feedback,issues_info', "
                    "filtering: [{field: 'effective_status', operator: 'IN', value: ['ACTIVE']}]}; 예산은 campaigns·adsets의 daily_budget·lifetime_budget(원, 계정 통화 최소 단위); "
                    "찾기 = search {type: 'adinterest', q: '육아'}(관심사 ID) | {type: 'adgeolocation', q: '서울', location_types: ['region','city']}(지역 키); "
                    "내 광고계정 목록 = me/adaccounts; 광고 라이브러리 = ads_archive {search_terms, ad_reached_countries: ['KR']}(메타 신원 확인 필요); "
                    "리드 양식 응답 = <양식ID>/leads, 페이지 게시물 성과 = <페이지ID>/insights(토큰에 그 권한 필요); 결과가 많은 insights는 async_report=true. "
                    "픽셀 = adspixels {fields: 'name,last_fired_time'}; 지출 한도 = act_<ID> {fields: 'spend_cap,amount_spent,balance,account_status,disable_reason'}. "
                    "비용(spend)은 VAT 별도. 관리자만, 조회만 한다.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "account_id"], "properties": {
         "workspace_id": {"type": "integer", "description": "조직 ID (list_ad_accounts 결과)"},
         "account_id": {"type": "string", "description": "메타 광고계정 ID(list_ad_accounts의 other_channels, act_ 없이)"},
         "path": {"type": "string", "description": "insights | campaigns | adsets | ads | adcreatives | adspixels | act_<ID> | <객체ID>[/insights]"},
         "params": {"type": "object", "description": "Graph API 칸(fields, level, time_range, breakdowns, filtering, limit 등)"},
         "async_report": {"type": "boolean", "description": "true면 큰 insights 보고서를 메타가 만들어 두게 하고 report_run_id를 돌려준다"}}},
     "annotations": {"readOnlyHint": True}},
]
CALLS = {"meta_ads_search": search_tool}
