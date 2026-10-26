"use client";

import { useEffect, useMemo, useSyncExternalStore } from "react";
import { api, Job } from "./api";
import { loadLocal, localKeys, removeLocal, saveLocal } from "./localData";
import { idsFrom, Keyword, keywordsFrom, parseTsv } from "./masterReport";
import { useApp } from "./store";

/** 광고 데이터(캠페인~확장소재)는 서버 DB에 두지 않고 네이버 마스터 보고서로 받아 브라우저에만 보관한다.
 * 광고주 계정 단위로 받고, 7일 지난 보관본은 새로 받는다. ID는 네이버 ID(id = naver_id). */

export type { Keyword };
export interface NCampaign { id: string; ad_account_id: number; naver_id: string; name: string; campaign_tp: string; status: string; daily_budget: number }
export interface NAdGroup {
  id: string; ad_account_id: number; naver_id: string; campaign_naver_id: string; name: string; adgroup_type: string;
  status: string; bid_amt: number; daily_budget: number | null; serving: string | null;
}
export interface NAd {
  id: string; ad_account_id: number; naver_id: string; adgroup_naver_id: string; ad_type: string; status: string;
  inspect_status: string; bid_amt: number | null; use_group_bid: boolean; payload: Record<string, unknown>;
}
export interface NExtension {
  id: string; ad_account_id: number; naver_id: string; owner_naver_id: string; ext_type: string; status: string;
  inspect_status: string; payload: unknown;
}
export interface AccountData { fetchedAt: number; campaigns: NCampaign[]; adgroups: NAdGroup[]; keywords: Keyword[]; ads: NAd[]; extensions: NExtension[] }
export type NaverData = Omit<AccountData, "fetchedAt">;

const MAX_AGE = 7 * 24 * 3600_000;
const POLL_MS = 2000;
const POLL_TRIES = 120; // 보고서 생성 최대 4분 대기
const LOOKUP_CHUNK = 200; // 서버 한 번에 500개까지(네이버에는 100개씩)

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const withId = <T extends { naver_id: string }>(rows: T[]) => rows.map((r) => ({ ...r, id: r.naver_id }));

async function report(base: string, item: string): Promise<string[][]> {
  const job = await api<{ id: string; status: string }>(`${base}/master-reports?item=${item}`, { method: "POST" });
  try {
    for (let i = 0; i < POLL_TRIES; i++) {
      const j = await api<{ status: string }>(`${base}/master-reports/${job.id}`);
      if (j.status === "BUILT") return parseTsv(await (await api<Blob>(`${base}/master-reports/${job.id}/file`, { raw: true })).text());
      if (j.status === "NONE") return []; // 해당 항목이 없는 계정
      if (j.status === "ERROR") throw new Error(`네이버가 ${item} 보고서를 만들지 못했습니다`);
      await sleep(POLL_MS);
    }
    throw new Error(`${item} 보고서가 너무 오래 걸립니다. 잠시 후 새로고침하세요`);
  } finally {
    // 네이버는 계정당 보고서 100개까지라 다 쓴 보고서는 지운다. 실패해도 다음 생성 때 서버가 비운다
    api(`${base}/master-reports/${job.id}`, { method: "DELETE" }).catch(() => {});
  }
}

async function lookup<T extends { naver_id: string }>(base: string, kind: string, ids: string[]): Promise<(T & { id: string })[]> {
  const out: T[] = [];
  for (let i = 0; i < ids.length; i += LOOKUP_CHUNK) {
    out.push(...await api<T[]>(`${base}/naver/${kind}?ids=${ids.slice(i, i + LOOKUP_CHUNK).join(",")}`));
  }
  return withId(out);
}

async function fetchAccount(wsId: number, accountId: number): Promise<AccountData> {
  const base = `/workspaces/${wsId}/ad-accounts/${accountId}`;
  const [campaigns, kw, grp, ad, rsa, shop, ext] = await Promise.all([
    api<NCampaign[]>(`${base}/naver/campaigns`).then(withId),
    report(base, "Keyword"), report(base, "Adgroup"), report(base, "Ad"), report(base, "RsaAd"),
    report(base, "ShoppingProduct"), report(base, "AdExtension"),
  ]);
  // 보고서에 없는 운영 상태·소재 문구·확장소재 내용은 ID로 따로 조회
  const camp = new Set(campaigns.map((c) => c.naver_id));
  const adgroups = (await lookup<NAdGroup>(base, "adgroups", idsFrom(grp, "Adgroup"))).filter((g) => camp.has(g.campaign_naver_id));
  const groups = new Set(adgroups.map((g) => g.naver_id));
  const ads = await lookup<NAd>(base, "ads", [...idsFrom(ad, "Ad"), ...idsFrom(rsa, "RsaAd"), ...idsFrom(shop, "ShoppingProduct")]);
  const extensions = await lookup<NExtension>(base, "ad-extensions", idsFrom(ext, "AdExtension"));
  // 앱이 다루지 않는 캠페인 유형(플레이스 등)에 속한 것은 뺀다
  return {
    fetchedAt: Date.now(), campaigns, adgroups,
    keywords: keywordsFrom(kw, accountId).filter((k) => groups.has(k.adgroup_naver_id)),
    ads: ads.filter((a) => groups.has(a.adgroup_naver_id)),
    extensions: extensions.filter((e) => groups.has(e.owner_naver_id) || camp.has(e.owner_naver_id)),
  };
}

// ---- 화면 간 공유하는 메모리 상태 ----
interface Entry { data: AccountData | null; loading: boolean; error: string | null }
const entries = new Map<string, Entry>();
const listeners = new Set<() => void>();
let version = 0;
const keyOf = (wsId: number, accountId: number) => `${wsId}:${accountId}`;

function setEntry(k: string, e: Partial<Entry>) {
  entries.set(k, { data: null, loading: false, error: null, ...entries.get(k), ...e });
  version++;
  listeners.forEach((l) => l());
}

/** 보관본이 있으면 그것을, 없거나 7일 지났거나 force면 네이버에서 새로 받는다. */
export async function ensureAccount(wsId: number, accountId: number, force = false) {
  const k = keyOf(wsId, accountId);
  const cur = entries.get(k);
  if (cur?.loading || (!force && cur?.data)) return;
  setEntry(k, { loading: true, error: null });
  try {
    const saved = force ? undefined : await loadLocal<AccountData>(k);
    if (saved && Date.now() - saved.fetchedAt < MAX_AGE) {
      setEntry(k, { data: saved, loading: false });
      return;
    }
    const data = await fetchAccount(wsId, accountId);
    await saveLocal(k, data);
    setEntry(k, { data, loading: false });
  } catch (e) {
    setEntry(k, { loading: false, error: (e as Error).message });
  }
}

/** 접근할 수 없게 된 계정(해제·권한 회수)의 보관본을 지운다. */
async function pruneAccounts(wsId: number, allowed: number[]) {
  for (const k of await localKeys()) {
    const [w, a] = k.split(":").map(Number);
    if (w === wsId && !allowed.includes(a)) {
      await removeLocal(k);
      entries.delete(k);
    }
  }
}

const empty: NaverData = { campaigns: [], adgroups: [], keywords: [], ads: [], extensions: [] };

/** 보관본을 바로 고친다(네이버에 반영한 변경을 다시 받지 않고 화면에 보이게). */
export async function patchAccount(wsId: number, accountId: number, fn: (d: AccountData) => AccountData) {
  const k = keyOf(wsId, accountId);
  // 작업 화면을 새로 불러왔으면(배포 직후 이동 등) 메모리가 비어 있다 → 브라우저 보관본을 고친다
  const cur = entries.get(k)?.data ?? await loadLocal<AccountData>(k);
  if (!cur) return;
  const data = fn(cur);
  setEntry(k, { data });
  await saveLocal(k, data);
}

const LIST_OF: Record<string, keyof NaverData> = { campaign: "campaigns", adgroup: "adgroups", keyword: "keywords", ad: "ads", ad_extension: "extensions" };

/** 실행이 끝난 작업의 성공 행을 보관본에 반영. 키워드 등록은 새 ID를 알아야 해서 그 계정을 다시 받는다. */
export async function applyJob(wsId: number, job: Job) {
  for (const acc of job.accounts ?? []) {
    const ok = acc.rows.filter((r) => r.status === "SUCCESS");
    if (acc.ad_account_id == null || !ok.length) continue;
    if (ok.some((r) => r.field === "create")) {
      await ensureAccount(wsId, acc.ad_account_id, true);
      continue;
    }
    await patchAccount(wsId, acc.ad_account_id, (d) => {
      const next = { ...d };
      for (const r of ok) {
        const key = LIST_OF[r.entity_type];
        const list = next[key] as unknown as Record<string, unknown>[];
        (next[key] as unknown) = r.field === "delete" ? list.filter((x) => x.naver_id !== r.naver_id)
          : list.map((x) => x.naver_id !== r.naver_id ? x : {
            ...x, [r.field]: r.field === "status" ? r.after : Number(r.after), ...(r.field === "bid_amt" && "use_group_bid" in x ? { use_group_bid: false } : {}),
          });
      }
      return next;
    });
  }
}

/** 작업 실행 후 등: 그 계정들을 네이버에서 다시 받는다. */
export const refreshAccounts = (wsId: number, accountIds: number[]) => Promise.all(accountIds.map((id) => ensureAccount(wsId, id, true)));

/** 상단에서 선택한 계정(없으면 접근 가능한 전체)의 데이터를 합쳐서 준다. all이면 선택과 상관없이 전체(엑셀 대조용). */
export function useNaverData({ all = false } = {}) {
  const { ws, accounts, selected } = useApp();
  const ids = useMemo(() => (selected.length && !all ? selected : accounts.map((a) => a.id)), [selected, accounts, all]);
  const v = useSyncExternalStore((l) => { listeners.add(l); return () => listeners.delete(l); }, () => version, () => 0);

  useEffect(() => {
    if (!ws) return;
    void pruneAccounts(ws.id, accounts.map((a) => a.id));
  }, [ws, accounts]);
  useEffect(() => {
    if (ws) ids.forEach((id) => void ensureAccount(ws.id, id));
  }, [ws, ids]);

  return useMemo(() => {
    const list = ws ? ids.map((id) => ({ id, e: entries.get(keyOf(ws.id, id)) })) : [];
    const merged = { ...empty };
    for (const { e } of list) {
      if (!e?.data) continue;
      for (const k of Object.keys(empty) as (keyof typeof empty)[]) (merged[k] as unknown[]) = [...merged[k], ...e.data[k]];
    }
    return {
      ...merged,
      loading: list.some(({ e }) => !e || e.loading),
      errors: list.filter(({ e }) => e?.error).map(({ id, e }) => ({ ad_account_id: id, error: e!.error! })),
      fetchedAt: list.map(({ e }) => e?.data?.fetchedAt ?? 0).filter(Boolean).reduce((a, b) => Math.min(a, b), Infinity),
      refresh: (accountIds: number[] = ids) => refreshAccounts(ws!.id, accountIds),
    };
    // v: 다른 화면에서 받은 데이터가 바뀌면 다시 합친다
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ws, ids, v]);
}
