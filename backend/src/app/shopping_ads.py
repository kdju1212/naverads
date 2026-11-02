"""쇼핑검색 상품소재(SHOPPING_PRODUCT_AD) 등록. 웹(POST /workspaces/{ws}/shopping-ads)과 Claude(create_shopping_ad)가 같은 함수를 쓴다.
파워링크 소재 등록(bulk.create_ad)과 따로 둬서 서로 건드리지 않는다."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import bulk, safety
from .access import membership
from .db import get_db
from .models import AuditLog, Membership
from .naver import NaverApiError, ad_row

router = APIRouter()

TOOL = {"name": "create_shopping_ad", "description": "쇼핑검색 광고그룹에 상품소재를 등록한다(바로 실행, OFF로 만들어져 검수 후 사용자가 켬). "
        "product_id는 네이버쇼핑 상품 ID(nvMid, 숫자)이며 스마트스토어 상품 번호가 아니다. "
        "상품은 광고그룹에 연결된 쇼핑몰 채널(검수 통과)에서 광고 등록이 가능한 상품이어야 한다. "
        "bid_amt를 비우면 광고그룹 입찰가를 쓴다(50~100,000원, 10원 단위). "
        "먼저 계정·광고그룹·상품 번호·입찰가를 채팅에 표로 보여 준 뒤 호출(허용 버튼이 승인).",
        "inputSchema": {"type": "object", "required": ["workspace_id", "ad_account_id", "adgroup_id", "product_id"], "properties": {
            "workspace_id": {"type": "integer", "description": "조직 ID (list_ad_accounts 결과)"},
            "ad_account_id": {"type": "integer", "description": "광고 계정 ID (list_ad_accounts 결과의 id)"},
            "adgroup_id": {"type": "string", "description": "쇼핑검색 광고그룹 ID"},
            "product_id": {"type": "string", "description": "네이버쇼핑 상품 ID(nvMid). 스마트스토어 상품 번호와 다름"},
            "bid_amt": {"type": "integer", "description": "소재 입찰가(원). 비우면 그룹 입찰가"}}},
        "annotations": {"destructiveHint": True}}


class ShoppingAdIn(BaseModel):
    ad_account_id: int
    adgroup_naver_id: str
    product_id: str
    bid_amt: int | None = None


def create_shopping_ad(db: Session, m: Membership, account_id: int, adgroup_naver_id: str, product_id: str,
                       bid_amt: int | None = None) -> dict:
    bulk._check_edit(db, m, account_id)
    product_id = product_id.strip()
    if not product_id.isdigit():
        raise HTTPException(400, "상품 ID는 네이버쇼핑 상품 ID(nvMid, 숫자)로 입력하세요. 스마트스토어 상품 번호와 다릅니다")
    if bid_amt is not None and (err := bulk._money(str(bid_amt), "입찰가", *bulk.BID_RANGE["SHOPPING"])):
        raise HTTPException(400, err)
    client = bulk._client(db, m.workspace_id, account_id)
    try:  # 계정 클릭당 최대 입찰가(광고비 안전장치). 비우면 그룹 입찰가를 물려받으므로 네이버의 지금 그룹 입찰가로 검사한다
        bid = bid_amt or ((client.get_many("adgroups", [adgroup_naver_id]) or [{}])[0].get("bidAmt"))
        if bid is None:
            raise HTTPException(400, "광고그룹을 네이버에서 찾지 못해 실제 입찰가를 확인할 수 없어 등록하지 않았어요")
        safety.check_bids(safety.get(db, m.workspace_id, account_id), [("bid", bid, None, None)])
    except safety.SafetyError as e:
        raise HTTPException(400, str(e) + ("" if bid_amt else " (입찰가를 비워 광고그룹 입찰가를 쓰는 경우)"))
    except NaverApiError as e:
        raise HTTPException(400, f"네이버에서 광고그룹 입찰가를 읽지 못해 등록하지 않았어요: {e}")
    # referenceKey는 네이버쇼핑 상품 ID(nvMid); 실계정에서 연결 채널과 상품의 등록 가능 여부도 충족해야 한다.
    attr = {"bidAmt": bid_amt, "useGroupBidAmt": False} if bid_amt else {"useGroupBidAmt": True}
    try:  # 꺼진 상태로 만들어진다 → 켤 때 합계·실제 입찰가를 다시 검사(safety.check)
        a = client.create_ad(adgroup_naver_id, "SHOPPING_PRODUCT_AD", {}, None, referenceKey=product_id, adAttr=attr)
    except NaverApiError as err:
        raise HTTPException(400, f"네이버 상품소재 등록 실패: {err}")
    row = ad_row(account_id, a)
    row["payload"] = {"productId": product_id, **row["payload"]}  # 상품명은 다음 데이터 받기 때 채워진다
    row["bid_amt"], row["use_group_bid"] = bid_amt, not bid_amt  # 명세상 응답에 adAttr가 안 와서 보낸 값으로 보여 준다
    db.add(AuditLog(workspace_id=m.workspace_id, user_id=m.user_id, ad_account_id=account_id, action="CREATE",
                    entity_type="ad", naver_id=row["naver_id"], field="ad_type", after="SHOPPING_PRODUCT_AD"))
    db.commit()
    return row


@router.post("/workspaces/{ws_id}/shopping-ads")
async def post_shopping_ad(body: ShoppingAdIn, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    return create_shopping_ad(db, m, body.ad_account_id, body.adgroup_naver_id, body.product_id, body.bid_amt)
