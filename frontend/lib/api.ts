export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "https://naverads-api.djkim0509.workers.dev";

export type Product = "" | "WEB_SITE" | "SHOPPING";

export interface Workspace { id: number; name: string; type: string; role: "OWNER" | "ADMIN" | "MEMBER" }
export interface Account {
  id: number; customer_id: string; name: string; is_mock: boolean;
  last_sync: { status: "SUCCESS" | "FAILED"; error: string | null; at: string } | null;
}
export interface Campaign { id: number; ad_account_id: number; naver_id: string; name: string; campaign_tp: string; status: string; daily_budget: number }
export interface AdGroup { id: number; ad_account_id: number; campaign_id: number; naver_id: string; name: string; adgroup_type: string; status: string; bid_amt: number; daily_budget: number | null }
export interface Change { entity_type: string; naver_id: string; field: string; value: string }
export interface JobRow {
  id: number; entity_type: string; naver_id: string; field: string; before: string | null; after: string;
  status: "VALID" | "INVALID" | "SUCCESS" | "FAILED"; error: string | null;
}
export interface Job {
  id: number; status: string; source: string; parent_job_id: number | null; created_by: number;
  created_at: string; executed_at: string | null;
  counts: Record<"VALID" | "INVALID" | "SUCCESS" | "FAILED", number>;
  accounts: { ad_account_id: number | null; name: string | null; rows: JobRow[] }[] | null;
}

export function getToken(): string | null {
  try { return localStorage.getItem("token"); } catch { return null; }
}

export function setToken(t: string | null) {
  try { if (t) localStorage.setItem("token", t); else localStorage.removeItem("token"); } catch { /* 저장 불가 환경 */ }
}

/** 전체 새로고침으로 이동해 메모리에 남은 이전 사용자 데이터를 비운다 */
export function logout() {
  setToken(null);
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
  if (res.status === 401 && !path.startsWith("/auth/")) logout();
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
export const FIELD_LABEL: Record<string, string> = { status: "상태", daily_budget: "일예산", bid_amt: "입찰가", create: "등록", delete: "삭제", keyword: "키워드" };
export const ENTITY_LABEL: Record<string, string> = { campaign: "캠페인", adgroup: "광고그룹", keyword: "키워드", ad: "소재", ad_extension: "확장소재" };
