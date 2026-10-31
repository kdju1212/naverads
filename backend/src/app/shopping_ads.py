"""쇼핑검색 상품소재(SHOPPING_PRODUCT_AD) 등록. 웹(POST /workspaces/{ws}/shopping-ads)과 Claude(create_shopping_ad)가 같은 함수를 쓴다.
파워링크 소재 등록(bulk.create_ad)과 따로 둬서 서로 건드리지 않는다."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import bulk
from .access import membership
from .db import get_db
from .models import AuditLog, Membership
from .naver import NaverApiError, ad_row

router = APIRouter()

TOOL = {"name": "create_shopping_ad", "description": "쇼핑검색 광고그룹에 상품소재를 등록한다(바로 실행, OFF로 만들어져 검수 후 사용자가 켬). "
        "product_id는 네이버쇼핑 상품 번호(숫자). bid_amt를 비우면 광고그룹 입찰가를 쓴다(50~100,000원, 10원 단위). "
        "먼저 계정·광고그룹·상품 번호·입찰가를 채팅에 표로 보여 준 뒤 호출(허용 버튼이 승인).",
        "inputSchema": {"type": "object", "required": ["workspace_id", "ad_account_id", "adgroup_id", "product_id"], "properties": {
            "workspace_id": {"type": "integer", "description": "조직 ID (list_ad_accounts 결과)"},
            "ad_account_id": {"type": "integer", "description": "광고 계정 ID (list_ad_accounts 결과의 id)"},
            "adgroup_id": {"type": "string", "description": "쇼핑검색 광고그룹 ID"},
            "product_id": {"type": "string", "description": "네이버쇼핑 상품 번호"},
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
        raise HTTPException(400, "상품 ID는 네이버쇼핑 상품 번호(숫자)로 입력하세요")
    if bid_amt is not None and (err := bulk._money(str(bid_amt), "입찰가", *bulk.BID_RANGE["SHOPPING"])):
        raise HTTPException(400, err)
    # shortcut: 명세에 쇼핑 소재 형식이 없어 referenceKey=상품 번호·adAttr=입찰가로 가정(실계정 미확인), 네이버가 거부하면 여기만 고친다
    attr = {"bidAmt": bid_amt, "useGroupBidAmt": False} if bid_amt else {"useGroupBidAmt": True}
    try:
        a = bulk._client(db, m.workspace_id, account_id).create_ad(adgroup_naver_id, "SHOPPING_PRODUCT_AD", {}, None,
                                                                   referenceKey=product_id, adAttr=attr)
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
