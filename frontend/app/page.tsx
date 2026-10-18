"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Badge, Card, ErrorText, inputCls, PageTitle } from "@/components/ui";
import { fmt, Job } from "@/lib/api";
import { useApp } from "@/lib/store";
import { useFetch } from "@/lib/useFetch";

interface Perf { impressions: number; clicks: number; cost: number; conversions: number | null; revenue: number | null; ctr: number | null; cpc: number | null; roas: number | null }
interface AccountPerf { ad_account_id: number; name: string; WEB_SITE: Perf | null; SHOPPING: Perf | null }
interface Dashboard { connected_accounts: number; recent_jobs: Job[]; failed_jobs: number[]; sync_errors: { ad_account_id: number; error: string; at: string }[] }

const day = (d: Date) => d.toISOString().slice(0, 10);

type Agg = { cost: number | null; clicks: number | null; conversions: number | null; revenue: number | null };

function sum(list: (Agg | null)[]) {
  const ps = list.filter((p): p is Agg => !!p);
  if (!ps.length) return null;
  const add = (k: keyof Agg) => (ps.some((p) => p[k] != null) ? ps.reduce((s, p) => s + (p[k] ?? 0), 0) : null);
  const cost = add("cost") ?? 0, revenue = add("revenue");
  // 매출 미제공(null)이면 ROAS도 미제공 — 0과 구분
  return { cost, clicks: add("clicks"), conversions: add("conversions"), revenue, roas: revenue != null && cost ? Math.round((revenue / cost) * 1000) / 10 : null };
}

export default function DashboardPage() {
  const { ws, query, accountName, product } = useApp();
  const [days, setDays] = useState(7);
  const [today] = useState(() => Date.now());
  const until = new Date(today - 86400000);
  const since = new Date(until.getTime() - (days - 1) * 86400000);
  const perf = useFetch<AccountPerf[]>(ws && `/workspaces/${ws.id}/performance/accounts${query({ since: day(since), until: day(until) })}`);
  const dash = useFetch<Dashboard>(ws && `/workspaces/${ws.id}/dashboard`);

  const rows = useMemo(() => (perf.data ?? []).map((a) => {
    const pl = product === "SHOPPING" ? null : a.WEB_SITE, sh = product === "WEB_SITE" ? null : a.SHOPPING;
    return { ...a, pl, sh, total: sum([pl, sh]) };
  }), [perf.data, product]);
  const total = sum(rows.map((r) => r.total));

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-end justify-between">
        <PageTitle desc="선택한 광고주 계정의 운영 현황">대시보드</PageTitle>
        <select className={inputCls} value={days} onChange={(e) => setDays(Number(e.target.value))} aria-label="기간">
          {[7, 14, 30].map((d) => <option key={d} value={d}>최근 {d}일</option>)}
        </select>
      </div>
      <ErrorText error={perf.error ?? dash.error} />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[
          ["연결된 광고 계정", fmt(dash.data?.connected_accounts, "개")],
          ["광고비", fmt(total?.cost, "원")],
          ["전환수", fmt(total?.conversions)],
          ["ROAS", total?.roas == null ? "-" : `${total.roas}%`],
        ].map(([label, v]) => (
          <div key={label} className="rounded-lg border border-gray-200 bg-white p-4">
            <div className="text-xs text-gray-500">{label}</div>
            <div className="mt-1 text-xl font-bold tabular-nums">{perf.loading && label !== "연결된 광고 계정" ? "…" : v}</div>
          </div>
        ))}
      </div>

      <Card title="광고주별 성과">
        <div className="overflow-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-gray-500">
              <tr>
                <th className="py-2 pr-3">광고주</th>
                <th className="px-3 text-right">파워링크 광고비</th><th className="px-3 text-right">파워링크 ROAS</th>
                <th className="px-3 text-right">쇼핑 광고비</th><th className="px-3 text-right">쇼핑 ROAS</th>
                <th className="px-3 text-right">총 광고비</th><th className="px-3 text-right">클릭</th>
                <th className="px-3 text-right">전환수</th><th className="px-3 text-right">매출</th><th className="pl-3 text-right">ROAS</th>
              </tr>
            </thead>
            <tbody className="tabular-nums">
              {rows.map((r) => (
                <tr key={r.ad_account_id} className="border-t border-gray-100">
                  <td className="py-2 pr-3 font-medium">{r.name}</td>
                  <td className="px-3 text-right">{fmt(r.pl?.cost)}</td><td className="px-3 text-right">{r.pl?.roas == null ? "-" : `${r.pl.roas}%`}</td>
                  <td className="px-3 text-right">{fmt(r.sh?.cost)}</td><td className="px-3 text-right">{r.sh?.roas == null ? "-" : `${r.sh.roas}%`}</td>
                  <td className="px-3 text-right font-semibold">{fmt(r.total?.cost)}</td><td className="px-3 text-right">{fmt(r.total?.clicks)}</td>
                  <td className="px-3 text-right">{fmt(r.total?.conversions)}</td><td className="px-3 text-right">{fmt(r.total?.revenue)}</td>
                  <td className="pl-3 text-right">{r.total?.roas == null ? "-" : `${r.total.roas}%`}</td>
                </tr>
              ))}
              {!perf.loading && rows.length === 0 && (
                <tr><td colSpan={10} className="py-6 text-center text-gray-400">연결된 광고 계정이 없습니다. <Link prefetch={false} className="text-emerald-700 underline" href="/settings">설정에서 연결</Link></td></tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="최근 대량 작업" actions={<Link prefetch={false} href="/jobs" className="text-xs text-emerald-700">전체 보기</Link>}>
          <ul className="flex flex-col divide-y divide-gray-100 text-sm">
            {(dash.data?.recent_jobs ?? []).map((j) => (
              <li key={j.id} className="flex items-center gap-2 py-2">
                <Link prefetch={false} href={`/jobs?id=${j.id}`} className="font-medium hover:underline">작업 #{j.id}</Link>
                <Badge value={j.status} />
                <span className="text-xs text-gray-500">성공 {j.counts.SUCCESS} · 실패 {j.counts.FAILED}</span>
                <span className="ml-auto text-xs text-gray-400">{j.executed_at && new Date(j.executed_at).toLocaleString("ko-KR")}</span>
              </li>
            ))}
            {dash.data?.recent_jobs.length === 0 && <li className="py-2 text-gray-400">실행한 작업이 없습니다</li>}
          </ul>
        </Card>
        <Card title="동기화 오류 · 실패 작업">
          <ul className="flex flex-col divide-y divide-gray-100 text-sm">
            {(dash.data?.sync_errors ?? []).map((s) => (
              <li key={s.ad_account_id} className="py-2"><b>{accountName(s.ad_account_id)}</b> 동기화 실패: <span className="text-red-700">{s.error}</span></li>
            ))}
            {(dash.data?.failed_jobs ?? []).map((id) => (
              <li key={id} className="py-2"><Link prefetch={false} href={`/jobs?id=${id}`} className="text-red-700 hover:underline">작업 #{id}에 실패한 행이 있습니다 → 확인·재실행</Link></li>
            ))}
            {dash.data && !dash.data.sync_errors.length && !dash.data.failed_jobs.length && <li className="py-2 text-gray-400">문제 없음</li>}
          </ul>
        </Card>
      </div>
    </div>
  );
}
