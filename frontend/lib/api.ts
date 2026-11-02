import { csvCell } from "./csv";
import { clearLocal } from "./localData";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "https://naverads-api.djkim0509.workers.dev";

export type Product = "" | "WEB_SITE" | "SHOPPING";

export interface Workspace { id: number; name: string; type: string; role: "OWNER" | "ADMIN" | "MEMBER" }
export interface Account {
  id: number; customer_id: string; name: string; is_mock: boolean;
  last_sync: { status: "SUCCESS" | "FAILED"; error: string | null; at: string } | null;
  safety: { daily_budget_limit: number; max_bid: number } | null; // 광고비 안전장치(없으면 광고 켜기·증액·입찰가 변경 막힘)
}
/** 실행 전 안전장치 검사 결과(계정별). 서버: backend/src/app/safety.py */
export interface SafetyCheck { ad_account_id: number; ok: boolean; reason?: string; total_after?: number; daily_budget_limit?: number; max_bid?: number; uncontrolled?: string[]; note: string }
export interface Change {
  entity_type: string; naver_id: string; field: string; value: string;
  // 서버에 광고 데이터 사본이 없어 화면이 같이 보낸다(lib/changes.ts)
  ad_account_id?: number; before?: string; product?: string; ad_type?: string; invalid?: string;
}
export interface JobRow {
  id: number; entity_type: string; naver_id: string; field: string; before: string | null; after: string;
  status: "VALID" | "INVALID" | "SUCCESS" | "FAILED"; error: string | null;
}
export interface Job {
  id: number; status: string; source: string; parent_job_id: number | null; created_by: number;
  created_at: string; executed_at: string | null; scheduled_at: string | null;
  counts: Record<"VALID" | "INVALID" | "SUCCESS" | "FAILED", number>;
  accounts: { ad_account_id: number | null; name: string | null; rows: JobRow[] }[] | null;
  safety?: SafetyCheck[]; // 미리보기일 때: 계정별 변경 후 하루예산 설정액 합계·최대 입찰가(네이버 지금 값 기준)
  approval?: { approval_id: number; status: string; message: string }; // 실행·예약했는데 웹 승인이 필요하면(실행 안 됨)
}

/** 작업 완료 알림(components/ui Toaster가 보여준다) */
export function toast(msg: string) {
  window.dispatchEvent(new CustomEvent("app-toast", { detail: msg }));
}

// 로그인 토큰은 서버가 심는 HttpOnly 쿠키에만 있다(JS가 읽을 수 없음). 브라우저에는 '로그인했음' 표시(무작위 값, 비밀 아님)만 둔다:
// 로그인 화면으로 보낼지, 화면 캐시를 사용자별로 나눌지 정하는 데만 쓴다
const SESSION_MARK = "session";
/** 쿠키 로그인의 쓰기 요청에 붙이는 CSRF 헤더(서버 access.CSRF_HEADER). 다른 사이트의 폼·링크는 이 헤더를 붙일 수 없다 */
const CSRF = { "X-Naverads-CSRF": "1" };

export function getSession(): string | null {
  try { return localStorage.getItem(SESSION_MARK); } catch { return null; }
}

/** 로그인·로그아웃 모두 브라우저에 보관한 광고 데이터를 지운다(이전 사용자 것이 남지 않게) */
export async function setSession(on: boolean) {
  await clearLocal();
  try {
    if (on) localStorage.setItem(SESSION_MARK, crypto.randomUUID());
    else localStorage.removeItem(SESSION_MARK);
    localStorage.removeItem("token"); // 예전 버전이 보관하던 토큰
  } catch { /* 저장 불가 환경 */ }
}

/** 예전 버전(localStorage 토큰)으로 로그인해 있던 브라우저: 그 토큰으로 한 번 쿠키 로그인으로 옮기고 토큰은 지운다(서버가 예전 토큰을 무효로 함) */
export async function migrateLegacyToken() {
  let t: string | null = null;
  try { t = localStorage.getItem("token"); } catch { return; }
  if (!t) return;
  const r = await fetch(`${API_URL}/auth/session`, { method: "POST", credentials: "include", headers: { Authorization: `Bearer ${t}` } }).catch(() => null);
  try {
    localStorage.removeItem("token");
    if (r?.ok) localStorage.setItem(SESSION_MARK, crypto.randomUUID());
  } catch { /* 저장 불가 환경 */ }
}

/** 전체 새로고침으로 이동해 메모리에 남은 이전 사용자 데이터를 비운다 */
export async function logout() {
  // 서버에서 이 기기 토큰을 무효로 하고 쿠키를 지운다. 실패해도(이미 만료·네트워크) 브라우저에서는 로그아웃 표시를 지운다
  await fetch(`${API_URL}/auth/logout`, { method: "POST", credentials: "include", headers: CSRF }).catch(() => {});
  await setSession(false);
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination -- 상태 초기화를 위해 의도적으로 전체 새로고침
  location.href = "/login";
}

export async function api<T>(path: string, opts: { method?: string; body?: unknown; form?: FormData; raw?: boolean } = {}): Promise<T> {
  const method = opts.method ?? (opts.body !== undefined || opts.form ? "POST" : "GET");
  // 쓰기 요청에만 CSRF 헤더(GET에 붙이면 요청마다 CORS 사전 요청이 한 번 더 간다)
  const headers: Record<string, string> = method === "GET" ? {} : { ...CSRF };
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  let res: Response;
  try {
    res = await fetch(API_URL + path, { method, headers, body, credentials: "include" });
  } catch {
    // Cloudflare가 CPU 한도로 끊으면 CORS 헤더 없는 503이 와서 네트워크 오류로 보인다
    throw new Error("서버 응답이 없습니다. 잠시 후 다시 시도하세요. (무료 플랜 일시 제한일 수 있음)");
  }
  if (res.status === 401 && !path.startsWith("/auth/")) void logout();
  if (opts.raw && res.ok) return (await res.blob()) as T;
  const data = res.headers.get("content-type")?.includes("json") ? await res.json() : null;
  if (!res.ok) {
    const d = data?.detail;
    throw new Error(typeof d === "string" ? d : Array.isArray(d) ? d.map((x: { msg: string }) => x.msg).join(", ") : `요청 실패 (${res.status})`);
  }
  return data as T;
}

export function downloadBlob(blob: Blob, filename: string) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

export function downloadCsv(rows: (string | number | null)[][], filename: string) {
  // BOM: 엑셀에서 한글이 깨지지 않게
  downloadBlob(new Blob(["﻿" + rows.map((r) => r.map(csvCell).join(",")).join("\n")], { type: "text/csv" }), filename);
}

export const fmt = (n: number | null | undefined, suffix = "") => (n == null ? "-" : n.toLocaleString("ko-KR") + suffix);

export const PRODUCT_LABEL: Record<string, string> = { WEB_SITE: "파워링크", SHOPPING: "쇼핑검색", PLACE: "플레이스" };
// 네이버 광고그룹 statusReason/status (공식 명세 enum). 동기화 시점 기준
export const SERVING_LABEL: Record<string, string> = {
  ELIGIBLE: "노출 가능", LIMITED_ELIGIBLE: "일부 제한", PAUSED: "중지", DELETED: "삭제됨",
  CAMPAIGN_PAUSED: "캠페인 OFF", CAMPAIGN_PENDING: "캠페인 시작 전", CAMPAIGN_ENDED: "캠페인 종료",
  CAMPAIGN_LIMITED_BY_BUDGET: "캠페인 예산 소진", GROUP_PAUSED: "광고그룹 OFF", GROUP_LIMITED_BY_BUDGET: "광고그룹 예산 소진",
  GROUP_DELETED: "광고그룹 삭제됨", BUSINESS_CHANNEL_PAUSED: "비즈채널 중지", BUSINESS_CHANNEL_DISAPPROVED: "비즈채널 반려",
  BUSINESS_CHANNEL_UNDER_REVIEW: "비즈채널 검수 중", PC_BUSINESS_CHANNEL_APPROVED: "PC 비즈채널 승인",
  PC_BUSINESS_CHANNEL_DISAPPROVED: "PC 비즈채널 반려", PC_BUSINESS_CHANNEL_UNDER_REVIEW: "PC 비즈채널 검수 중",
  MOBILE_BUSINESS_CHANNEL_APPROVED: "모바일 비즈채널 승인", MOBILE_BUSINESS_CHANNEL_DISAPPROVED: "모바일 비즈채널 반려",
  MOBILE_BUSINESS_CHANNEL_UNDER_REVIEW: "모바일 비즈채널 검수 중",
};
// 소재·확장소재 검수 상태 (inspectStatus)
export const INSPECT_LABEL: Record<string, string> = {
  UNDER_REVIEW: "검수 중", PENDING: "검수 대기", APPROVED: "승인", ELIGIBLE: "승인", LIMITED_ELIGIBLE: "일부 승인",
  DENIED: "반려", REJECTED: "반려", DISAPPROVED: "반려",
};
export const inspectLabel = (v: string | null) => (v ? INSPECT_LABEL[v] ?? v : "-");
export const servingLabel = (v: string | null) => (v ? SERVING_LABEL[v] ?? v : "-");
export const FIELD_LABEL: Record<string, string> = { status: "상태", daily_budget: "일예산", bid_amt: "입찰가", create: "등록", delete: "삭제", keyword: "키워드" };
export const ENTITY_LABEL: Record<string, string> = { campaign: "캠페인", adgroup: "광고그룹", keyword: "키워드", ad: "소재", ad_extension: "확장소재", negative_keyword: "제외검색어" };
