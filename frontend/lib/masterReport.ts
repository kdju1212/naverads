/** 네이버 마스터 보고서(헤더 없는 TSV) 해석. 칸 번호는 실계정 파일을 앱 DB와 대조해 확인했다(2026-10-21).
 * 외부 import 없이 순수 함수만 둔다(node --test로 바로 확인). */

export interface Keyword { id: string; ad_account_id: number; naver_id: string; adgroup_naver_id: string; keyword: string; status: string; bid_amt: number; use_group_bid: boolean }

export const parseTsv = (text: string): string[][] =>
  text.split(/\r?\n/).filter((l) => l.trim()).map((l) => l.split("\t"));

/** Keyword(13칸): 0 고객 · 1 광고그룹 · 2 키워드 ID · 3 키워드 · 4 입찰가 · 5·6 PC/모바일 URL · 7 OFF(1) · 8 검수 · 9 그룹 입찰가 사용(1) · 10 등록 · 11 삭제 시각 */
export function keywordsFrom(rows: string[][], accountId: number): Keyword[] {
  return rows.filter((r) => r.length >= 10 && !r[11]).map((r) => ({
    id: r[2], ad_account_id: accountId, naver_id: r[2], adgroup_naver_id: r[1], keyword: r[3],
    bid_amt: Number(r[4]), status: r[7] === "1" ? "OFF" : "ON", use_group_bid: r[9] === "1",
  }));
}

/** 나머지 보고서는 ID만 쓰고 내용은 네이버 ids 조회로 채운다(보고서에 운영 상태·문구가 없음).
 * Adgroup·AdExtension은 1번 칸, RsaAd는 2번 칸(실계정 확인). Ad·ShoppingProduct도 RsaAd와 같다고 보고 2번 칸 */
// shortcut: Ad·ShoppingProduct 칸은 실파일 미확인, 그런 소재가 있는 계정이 생기면 확인
export const ID_COL = { Adgroup: 1, AdExtension: 1, RsaAd: 2, Ad: 2, ShoppingProduct: 2 } as const;
export type IdItem = keyof typeof ID_COL;
export const idsFrom = (rows: string[][], item: IdItem): string[] => rows.map((r) => r[ID_COL[item]]).filter(Boolean);
