"use client";

import { useState } from "react";
import { api, fmt } from "@/lib/api";
import { useApp } from "@/lib/store";
import { Col } from "./DataTable";
import { Button, inputCls } from "./ui";

interface Perf {
  naver_id: string; impressions: number; clicks: number; cost: number; conversions: number | null;
  revenue: number | null; ctr: number | null; cpc: number | null; roas: number | null; avg_rank: number | null;
}
type Target = { ad_account_id: number; naver_id: string };

const LIMIT = 500; // 서버 main.ENTITY_PERF_LIMIT와 같게

/** 선택한 행(키워드·광고그룹)의 기간 성과를 네이버에서 바로 받아 표 칸으로 보여 주는 버튼과 칸. */
export function usePerf<T extends Target>() {
  const { ws } = useApp();
  const [days, setDays] = useState(7);
  const [perf, setPerf] = useState<Map<string, Perf>>(new Map());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const check = async (picked: T[]) => {
    if (!ws) return;
    setBusy(true);
    setError(null);
    const until = new Date(Date.now() - 864e5);
    const since = new Date(until.getTime() - (days - 1) * 864e5);
    const day = (d: Date) => d.toLocaleDateString("sv-SE"); // YYYY-MM-DD (브라우저 시간대)
    try {
      const byAcc = new Map<number, string[]>();
      picked.forEach((r) => byAcc.set(r.ad_account_id, [...(byAcc.get(r.ad_account_id) ?? []), r.naver_id]));
      const got: Perf[] = [];
      for (const [acc, ids] of byAcc) {
        const r = await api<{ rows: Perf[] }>(`/workspaces/${ws.id}/performance/entities`,
          { body: { ad_account_id: acc, ids, since: day(since), until: day(until) } });
        got.push(...r.rows);
      }
      setPerf(new Map(got.map((x) => [x.naver_id, x])));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const num = (key: keyof Perf, label: string, suffix = ""): Col<T> => ({
    key: `perf-${key}`, label, num: true, value: (r) => (perf.get(r.naver_id)?.[key] as number | null) ?? null,
    render: (r) => (perf.has(r.naver_id) ? fmt(perf.get(r.naver_id)![key] as number | null, suffix) : <span className="text-faint">-</span>),
  });
  // 성과를 받기 전에는 칸을 숨겨 표가 넓어지지 않게
  const cols: Col<T>[] = perf.size === 0 ? [] : [num("impressions", "노출"), num("clicks", "클릭"), num("cost", "비용", "원"),
    num("conversions", "전환"), num("roas", "ROAS", "%"), num("avg_rank", "평균 순위")];

  const button = (picked: T[]) => (
    <>
      {error && <span role="alert" className="text-xs text-danger">{error}</span>}
      <select className={inputCls} aria-label="성과 기간" value={days} onChange={(e) => setDays(Number(e.target.value))}>
        <option value={7}>지난 7일</option>
        <option value={30}>지난 30일</option>
      </select>
      <Button variant="secondary" disabled={busy || picked.length === 0 || picked.length > LIMIT} onClick={() => check(picked)}
        title={`선택한 행의 성과를 네이버에서 바로 조회합니다 (한 번에 ${LIMIT}개까지)`}>
        {busy ? "조회 중…" : picked.length > LIMIT ? `성과는 ${LIMIT}개까지` : "성과 보기"}
      </Button>
    </>
  );

  return { cols, button };
}
