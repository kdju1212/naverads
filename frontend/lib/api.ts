import { clearLocal } from "./localData";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "https://naverads-api.djkim0509.workers.dev";

export type Product = "" | "WEB_SITE" | "SHOPPING";

export interface Workspace { id: number; name: string; type: string; role: "OWNER" | "ADMIN" | "MEMBER" }
export interface Account {
  id: number; customer_id: string; name: string; is_mock: boolean;
  last_sync: { status: "SUCCESS" | "FAILED"; error: string | null; at: string } | null;
}
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
}

/** 작업 완료 알림(components/ui Toaster가 보여준다) */
export function toast(msg: string) {
  window.dispatchEvent(new CustomEvent("app-toast", { detail: msg }));
}

export function getToken(): string | null {
  try { return localStorage.getItem("token"); } catch { return null; }
}

/** 로그인·로그아웃 모두 브라우저에 보관한 광고 데이터를 지운다(이전 사용자 것이 남지 않게) */
export async function setToken(t: string | null) {
  await clearLocal();
  try { if (t) localStorage.setItem("token", t); else localStorage.removeItem("token"); } catch { /* 저장 불가 환경 */ }
}

/** 전체 새로고침으로 이동해 메모리에 남은 이전 사용자 데이터를 비운다 */
export async function logout() {
  await setToken(null);
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination -- 상태 초기화를 위해 의도적으로 전체 새로고침
  location.href = "/login";
}

export async function api<T>(path: string, opts: { method?: string; body?: unknown; form?: FormData; raw?: boolean } = {}): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  let res: Response;
  try {
    res = await fetch(API_URL + path, { method: opts.method ?? (body ? "POST" : "GET"), headers, body });
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
  const esc = (v: string | number | null) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  // BOM: 엑셀에서 한글이 깨지지 않게
  downloadBlob(new Blob(["﻿" + rows.map((r) => r.map(esc).join(",")).join("\n")], { type: "text/csv" }), filename);
}

export const fmt = (n: number | null | undefined, suffix = "") => (n == null ? "-" : n.toLocaleString("ko-KR") + suffix);

export const PRODUCT_LABEL: Record<string, string> = { WEB_SITE: "파워링크", SHOPPING: "쇼핑검색" };
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
