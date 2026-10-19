"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { TrendChart } from "@/components/TrendChart";
import { Badge, Button, Card, ErrorText, inputCls, PageTitle } from "@/components/ui";
import { fmt, Job } from "@/lib/api";
import { useApp } from "@/lib/store";
import { useFetch } from "@/lib/useFetch";

interface Perf { impressions: number; clicks: number; cost: number; conversions: number | null; revenue: number | null; ctr: number | null; cpc: number | null; roas: number | null }
interface AccountPerf { ad_account_id: number; name: string; WEB_SITE: Perf | null; SHOPPING: Perf | null }
interface Daily { date: string; impressions: number; clicks: number; cost: number; conversions: number | null; revenue: number | null }
type Counts = Record<string, number>;
interface Ops { campaign: Counts; adgroup: Counts; keyword: Counts; ad_inspect: Counts; ext_inspect: Counts; auto_bids: number }
interface Dashboard { connected_accounts: number; recent_jobs: Job[]; failed_jobs: number[]; sync_errors: { ad_account_id: number; error: string; at: string }[]; ops: Ops }

const DAY = 86400000;
const day = (d: Date) => d.toISOString().slice(0, 10);

type Agg = { impressions: number | null; cost: number | null; clicks: number | null; conversions: number | null; revenue: number | null };

function sum(list: (Agg | null)[]) {
  const ps = list.filter((p): p is Agg => !!p);
  if (!ps.length) return null;
  const add = (k: keyof Agg) => (ps.some((p) => p[k] != null) ? ps.reduce((s, p) => s + (p[k] ?? 0), 0) : null);
  const cost = add("cost") ?? 0, revenue = add("revenue"), clicks = add("clicks"), impressions = add("impressions");
  return {
    cost, clicks, impressions, conversions: add("conversions"), revenue,
    ctr: impressions && clicks != null ? Math.round((clicks / impressions) * 10000) / 100 : null,
    cpc: clicks ? Math.round(cost / clicks) : null,
    // 매출 미제공(null)이면 ROAS도 미제공 — 0과 구분
    roas: revenue != null && cost ? Math.round((revenue / cost) * 1000) / 10 : null,
  };
}
type Total = NonNullable<ReturnType<typeof sum>>;

const pct = (v: number | null | undefined, suffix = "%") => (v == null ? "-" : `${v}${suffix}`);

/** 직전 같은 기간 대비. 좋고 나쁨은 지표마다 달라(광고비 증가 등) 색 없이 화살표와 숫자만 */
function Delta({ now, prev }: { now: number | null | undefined; prev: number | null | undefined }) {
  if (now == null || prev == null) return null;
  if (prev === 0) return now === 0 ? <span className="text-xs text-gray-400">변동 없음</span> : <span className="text-xs text-gray-500">이전 기간 0</span>;
  const r = Math.round(((now - prev) / prev) * 1000) / 10;
  return <span className="text-xs text-gray-500 tabular-nums">{r > 0 ? "▲" : r < 0 ? "▼" : ""} {Math.abs(r)}% <span className="text-gray-400">이전 기간 대비</span></span>;
}

export default function DashboardPage() {
  const { ws, query, accountName, product } = useApp();
  const [days, setDays] = useState(7);
  const [showTable, setShowTable] = useState(false);
  const [today] = useState(() => Date.now());
  const until = new Date(today - DAY);
  const since = new Date(until.getTime() - (days - 1) * DAY);
  const prevUntil = new Date(since.getTime() - DAY), prevSince = new Date(prevUntil.getTime() - (days - 1) * DAY);
  const perf = useFetch<AccountPerf[]>(ws && `/workspaces/${ws.id}/performance/accounts${query({ since: day(since), until: day(until) })}`);
  const prev = useFetch<AccountPerf[]>(ws && `/workspaces/${ws.id}/performance/accounts${query({ since: day(prevSince), until: day(prevUntil) })}`);
  const daily = useFetch<Daily[]>(ws && `/workspaces/${ws.id}/performance/daily${query({ since: day(since), until: day(until), product })}`);
  const dash = useFetch<Dashboard>(ws && `/workspaces/${ws.id}/dashboard${query()}`);

  const pick = useMemo(() => (list: AccountPerf[] | null) => (list ?? []).map((a) => {
    const pl = product === "SHOPPING" ? null : a.WEB_SITE, sh = product === "WEB_SITE" ? null : a.SHOPPING;
    return { ...a, pl, sh, total: sum([pl, sh]) };
  }), [product]);
  const rows = useMemo(() => pick(perf.data), [pick, perf.data]);
  const total = sum(rows.map((r) => r.total));
  const prevTotal = sum(pick(prev.data).map((r) => r.total));
  const series = daily.data ?? [];
  const dates = series.map((d) => d.date);

  const kpis: [string, keyof Total, string][] = [
    ["광고비", "cost", "원"], ["노출수", "impressions", ""], ["클릭수", "clicks", ""], ["CTR", "ctr", "%"],
    ["CPC", "cpc", "원"], ["전환수", "conversions", ""], ["매출", "revenue", "원"], ["ROAS", "roas", "%"],
  ];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-end justify-between">
        <PageTitle desc="선택한 광고주 계정의 운영 현황">대시보드</PageTitle>
        <select className={inputCls} value={days} onChange={(e) => setDays(Number(e.target.value))} aria-label="기간">
          {[7, 14, 30].map((d) => <option key={d} value={d}>최근 {d}일</option>)}
        </select>
      </div>
      <ErrorText error={perf.error ?? daily.error ?? dash.error} />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {kpis.map(([label, k, unit]) => (
          <div key={label} className="rounded-lg border border-gray-200 bg-white p-4">
            <div className="text-xs text-gray-500">{label}</div>
            <div className="mt-1 text-xl font-bold tabular-nums">
              {perf.loading ? "…" : unit === "%" ? pct(total?.[k]) : fmt(total?.[k], unit)}
            </div>
            <div className="mt-0.5 h-4">{!perf.loading && !prev.loading && <Delta now={total?.[k]} prev={prevTotal?.[k]} />}</div>
          </div>
        ))}
      </div>

      <Card title="일별 추이" actions={<Button variant="secondary" onClick={() => setShowTable(!showTable)}>{showTable ? "그래프로 보기" : "표로 보기"}</Button>}>
        {showTable ? (
          <div className="overflow-auto">
            <table className="w-full text-sm tabular-nums">
              <thead className="text-left text-xs text-gray-500">
                <tr><th className="py-2 pr-3">날짜</th><th className="px-3 text-right">광고비</th><th className="px-3 text-right">노출</th>
                  <th className="px-3 text-right">클릭</th><th className="px-3 text-right">전환수</th><th className="pl-3 text-right">매출</th></tr>
              </thead>
              <tbody>
                {series.map((d) => (
                  <tr key={d.date} className="border-t border-gray-100">
                    <td className="py-1.5 pr-3">{d.date}</td><td className="px-3 text-right">{fmt(d.cost)}</td>
                    <td className="px-3 text-right">{fmt(d.impressions)}</td><td className="px-3 text-right">{fmt(d.clicks)}</td>
                    <td className="px-3 text-right">{fmt(d.conversions)}</td><td className="pl-3 text-right">{fmt(d.revenue)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : daily.loading ? (
          <p className="py-10 text-center text-sm text-gray-400">불러오는 중…</p>
        ) : (
          // 단위가 다른 지표는 한 축에 겹치지 않고 각자 그래프로
          <div className="grid gap-6 lg:grid-cols-3">
            <TrendChart title="광고비" unit="원" dates={dates} values={series.map((d) => d.cost)} />
            <TrendChart title="클릭수" dates={dates} values={series.map((d) => d.clicks)} />
            <TrendChart title="전환수" dates={dates} values={series.map((d) => d.conversions)} />
          </div>
        )}
      </Card>

      <OpsSummary ops={dash.data?.ops} connected={dash.data?.connected_accounts} />

      <Card title="광고주별 성과">
        <div className="overflow-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-gray-500">
              <tr>
                <th className="py-2 pr-3">광고주</th>
                <th className="px-3 text-right">파워링크 광고비</th><th className="px-3 text-right">파워링크 ROAS</th>
                <th className="px-3 text-right">쇼핑 광고비</th><th className="px-3 text-right">쇼핑 ROAS</th>
                <th className="px-3 text-right">총 광고비</th><th className="px-3 text-right">노출</th><th className="px-3 text-right">클릭</th>
                <th className="px-3 text-right">CTR</th><th className="px-3 text-right">CPC</th>
                <th className="px-3 text-right">전환수</th><th className="px-3 text-right">매출</th><th className="pl-3 text-right">ROAS</th>
              </tr>
            </thead>
            <tbody className="tabular-nums">
              {rows.map((r) => (
                <tr key={r.ad_account_id} className="border-t border-gray-100">
                  <td className="py-2 pr-3 font-medium">{r.name}</td>
                  <td className="px-3 text-right">{fmt(r.pl?.cost)}</td><td className="px-3 text-right">{pct(r.pl?.roas)}</td>
                  <td className="px-3 text-right">{fmt(r.sh?.cost)}</td><td className="px-3 text-right">{pct(r.sh?.roas)}</td>
                  <td className="px-3 text-right font-semibold">{fmt(r.total?.cost)}</td><td className="px-3 text-right">{fmt(r.total?.impressions)}</td>
                  <td className="px-3 text-right">{fmt(r.total?.clicks)}</td><td className="px-3 text-right">{pct(r.total?.ctr)}</td>
                  <td className="px-3 text-right">{fmt(r.total?.cpc)}</td>
                  <td className="px-3 text-right">{fmt(r.total?.conversions)}</td><td className="px-3 text-right">{fmt(r.total?.revenue)}</td>
                  <td className="pl-3 text-right">{pct(r.total?.roas)}</td>
                </tr>
              ))}
              {!perf.loading && rows.length === 0 && (
                <tr><td colSpan={13} className="py-6 text-center text-gray-400">연결된 광고 계정이 없습니다. <Link prefetch={false} className="text-emerald-700 underline" href="/settings">설정에서 연결</Link></td></tr>
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

const REVIEW = ["UNDER_REVIEW", "PENDING"], REJECTED = ["DENIED", "REJECTED", "DISAPPROVED"];
const pickSum = (c: Counts | undefined, keys: string[]) => keys.reduce((s, k) => s + (c?.[k] ?? 0), 0);

function OpsSummary({ ops, connected }: { ops?: Ops; connected?: number }) {
  const onOff = (c?: Counts) => (c ? `${fmt(c.ON ?? 0)} / ${fmt(c.OFF ?? 0)}` : "-");
  const items: [string, string, string][] = [
    ["연결된 광고 계정", fmt(connected, "개"), "/settings"],
    ["캠페인 ON / OFF", onOff(ops?.campaign), "/campaigns"],
    ["광고그룹 ON / OFF", onOff(ops?.adgroup), "/adgroups"],
    ["키워드 ON / OFF", onOff(ops?.keyword), "/keywords"],
    ["소재 검수 중 · 반려", ops ? `${pickSum(ops.ad_inspect, REVIEW)} · ${pickSum(ops.ad_inspect, REJECTED)}` : "-", "/ads"],
    ["확장소재 검수 중 · 반려", ops ? `${pickSum(ops.ext_inspect, REVIEW)} · ${pickSum(ops.ext_inspect, REJECTED)}` : "-", "/extensions"],
    ["자동입찰 키워드", fmt(ops?.auto_bids, "개"), "/keywords"],
  ];
  return (
    <Card title="운영 현황">
      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-4 lg:grid-cols-7">
        {items.map(([label, v, href]) => (
          <div key={label}>
            <dt className="text-xs text-gray-500">{label}</dt>
            <dd className="mt-0.5 font-semibold tabular-nums">
              <Link prefetch={false} href={href} className="hover:underline">{v}</Link>
            </dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}
