import { Change } from "./api";
import { NaverData } from "./naverData";

/** 대량 작업 대상(브라우저 보관본의 행). 서버에는 사본이 없어 계정·이전 값·유형을 같이 보낸다. */
export interface Target {
  naver_id: string; ad_account_id: number; status?: string; bid_amt?: number | null; daily_budget?: number | null;
  keyword?: string; name?: string; campaign_tp?: string; adgroup_type?: string; ad_type?: string;
}

const PRODUCT_OF: Record<string, string> = { keyword: "WEB_SITE", ad_extension: "WEB_SITE" };

export function changeFor(entityType: string, t: Target, field: string, value: string): Change {
  const before = field === "status" ? t.status : field === "delete" ? t.keyword ?? t.name
    : field === "bid_amt" ? t.bid_amt : field === "daily_budget" ? t.daily_budget : undefined;
  const product = t.campaign_tp ?? t.adgroup_type
    ?? (t.ad_type ? (t.ad_type === "SHOPPING_PRODUCT_AD" ? "SHOPPING" : "WEB_SITE") : PRODUCT_OF[entityType]);
  return { entity_type: entityType, naver_id: t.naver_id, field, value, ad_account_id: t.ad_account_id,
    before: before == null ? undefined : String(before), product, ad_type: t.ad_type };
}

/** 엑셀 행에 보관본으로 계정·이전 값을 채운다. 보관본에 없는 ID는 실행하지 않는 행으로 보낸다. */
export function enrichExcel(rows: Change[], d: NaverData): Change[] {
  const by = (list: Target[]) => new Map(list.map((x) => [x.naver_id, x]));
  const maps: Record<string, Map<string, Target>> = {
    campaign: by(d.campaigns), adgroup: by(d.adgroups), keyword: by(d.keywords), ad: by(d.ads), ad_extension: by(d.extensions),
  };
  return rows.map((r) => {
    // 제외검색어는 보관본에 없어 광고그룹(등록은 naver_id, 삭제는 value)으로 계정만 찾는다
    if (r.entity_type === "negative_keyword") {
      const g = maps.adgroup.get((r.field === "delete" ? r.value : r.naver_id).trim());
      return g ? { ...r, ad_account_id: g.ad_account_id } : { ...r, invalid: "보관된 데이터에 없는 광고그룹 ID입니다" };
    }
    // 키워드 등록은 naver_id가 광고그룹
    const t = (r.entity_type === "keyword" && r.field === "create" ? maps.adgroup : maps[r.entity_type])?.get(r.naver_id.trim());
    if (!t) return { ...r, invalid: "보관된 데이터에 없는 ID입니다 (ID 확인, 또는 새로고침 후 다시 올리기)" };
    const ch = changeFor(r.entity_type, t, r.field, r.value);
    if (r.field === "create" && d.keywords.some((k) => k.adgroup_naver_id === t.naver_id && k.keyword === r.value.split("|")[0].trim())) {
      return { ...ch, invalid: "이미 등록된 키워드입니다" };
    }
    return ch;
  });
}
