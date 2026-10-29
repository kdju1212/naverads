// 실행: node --test --experimental-strip-types lib/changes.test.ts
import assert from "node:assert/strict";
import { test } from "node:test";
import { changeFor, enrichExcel } from "./changes.ts";
import type { NaverData } from "./naverData.ts";

const camp = { id: "c1", ad_account_id: 1, naver_id: "c1", name: "브랜드", campaign_tp: "WEB_SITE", status: "OFF", daily_budget: 5000 };
const grp = { id: "g1", ad_account_id: 1, naver_id: "g1", campaign_naver_id: "c1", name: "그룹", adgroup_type: "WEB_SITE",
  status: "ON", bid_amt: 300, daily_budget: null, serving: null };
const kw = { id: "k1", ad_account_id: 1, naver_id: "k1", adgroup_naver_id: "g1", keyword: "원피스", status: "ON", bid_amt: 500 };
const data = { campaigns: [camp], adgroups: [grp], keywords: [kw], ads: [], extensions: [] } as unknown as NaverData;
const row = (entity_type: string, naver_id: string, field: string, value = "") => ({ entity_type, naver_id, field, value });

test("changeFor: 이전 값·유형", () => {
  assert.equal(changeFor("campaign", camp, "status", "ON").before, "OFF");
  assert.equal(changeFor("campaign", camp, "daily_budget", "9000").before, "5000");
  assert.equal(changeFor("campaign", camp, "delete", "").before, "브랜드");          // 캠페인 삭제는 이름
  assert.equal(changeFor("keyword", kw, "delete", "").before, "원피스");             // 키워드 삭제는 문구
  assert.equal(changeFor("adgroup", grp, "bid_amt", "400").product, "WEB_SITE");
  assert.equal(changeFor("keyword", kw, "bid_amt", "600").product, "WEB_SITE");     // 키워드는 파워링크
  assert.equal(changeFor("ad", { naver_id: "a", ad_account_id: 1, ad_type: "SHOPPING_PRODUCT_AD" }, "bid_amt", "100").product, "SHOPPING");
});

test("enrichExcel: 보관본으로 계정·이전 값 채우기", () => {
  const [a, b, c, d, e, f] = enrichExcel([
    row("adgroup", " g1 ", "status", "OFF"),
    row("keyword", "g1", "create", "원피스|500"),     // 이미 있는 키워드
    row("keyword", "g1", "create", "셔츠"),
    row("keyword", "없는ID", "status", "OFF"),
    row("negative_keyword", "g1", "create", "무료"),
    row("negative_keyword", "nrk-1", "delete", "없는그룹"),
  ], data);
  assert.equal(a.ad_account_id, 1);
  assert.equal(a.before, "ON");
  assert.equal(a.invalid, undefined);
  assert.equal(b.invalid, "이미 등록된 키워드입니다");
  assert.equal(c.ad_account_id, 1);
  assert.equal(c.invalid, undefined);
  assert.match(d.invalid ?? "", /보관된 데이터에 없는 ID/);
  assert.equal(e.ad_account_id, 1);                     // 제외검색어 등록: 광고그룹으로 계정 찾기
  assert.match(f.invalid ?? "", /없는 광고그룹/);         // 제외검색어 삭제: value가 광고그룹
});
