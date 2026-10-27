"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { TrendChart } from "@/components/TrendChart";
import { Badge, Button, Card, ErrorText, inputCls, PageTitle } from "@/components/ui";
import { api, fmt, Job } from "@/lib/api";
import { NaverData, useNaverData } from "@/lib/naverData";
import { useApp } from "@/lib/store";
import { useFetch } from "@/lib/useFetch";

interface Perf { impressions: number; clicks: number; cost: number; conversions: number | null; revenue: number | null; ctr: number | null; cpc: number | null; roas: number | null }
interface AccountPerf { ad_account_id: number; name: string; WEB_SITE: Perf | null; SHOPPING: Perf | null }
interface Daily { date: string; impressions: number; clicks: number; cost: number; conversions: number | null; revenue: number | null }
interface Dashboard { connected_accounts: number; recent_jobs: Job[]; failed_jobs: number[]; sync_errors: { ad_account_id: number; error: string; at: string }[]; auto_bids: number }

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
  if (prev === 0) return now === 0 ? <span className="text-xs text-faint">변동 없음</span> : <span className="text-xs text-faint">이전 기간 0</span>;
  const r = Math.round(((now - prev) / prev) * 1000) / 10;
  return <span className="text-xs text-faint tabular-nums">{r > 0 ? "▲" : r < 0 ? "▼" : ""} {Math.abs(r)}% <span className="text-faint">이전 기간 대비</span></span>;
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
  const naver = useNaverData();

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

      <div className="grid grid-cols-2 gap-px overflow-hidden rounded-panel border border-line bg-line lg:grid-cols-4">
        {kpis.map(([label, k, unit]) => (
          <div key={label} className="bg-surface px-4 py-3">
            <div className="text-xs font-medium text-muted">{label}</div>
            <div className="mt-1 text-2xl font-bold tabular-nums">
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
              <thead className="text-left text-xs text-faint">
                <tr><th className="py-2 pr-3">날짜</th><th className="px-3 text-right">광고비</th><th className="px-3 text-right">노출</th>
                  <th className="px-3 text-right">클릭</th><th className="px-3 text-right">전환수</th><th className="pl-3 text-right">매출</th></tr>
              </thead>
              <tbody>
                {series.map((d) => (
                  <tr key={d.date} className="border-t border-line">
                    <td className="py-1.5 pr-3">{d.date}</td><td className="px-3 text-right">{fmt(d.cost)}</td>
                    <td className="px-3 text-right">{fmt(d.impressions)}</td><td className="px-3 text-right">{fmt(d.clicks)}</td>
                    <td className="px-3 text-right">{fmt(d.conversions)}</td><td className="pl-3 text-right">{fmt(d.revenue)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : daily.loading ? (
          <p className="py-10 text-center text-sm text-faint">불러오는 중…</p>
        ) : (
          // 단위가 다른 지표는 한 축에 겹치지 않고 각자 그래프로
          <div className="grid gap-6 lg:grid-cols-3">
            <TrendChart title="광고비" unit="원" dates={dates} values={series.map((d) => d.cost)} />
            <TrendChart title="클릭수" dates={dates} values={series.map((d) => d.clicks)} />
            <TrendChart title="전환수" dates={dates} values={series.map((d) => d.conversions)} />
          </div>
        )}
      </Card>

      {product !== "SHOPPING" && <GoalCard accounts={rows.map((r) => ({ id: r.ad_account_id, name: r.name, roas: r.pl?.roas, days }))} />}

      <OpsSummary data={naver.loading ? null : naver} autoBids={dash.data?.auto_bids} connected={dash.data?.connected_accounts} />

      <Card title="광고주별 성과">
        <div className="overflow-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-faint">
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
                <tr key={r.ad_account_id} className="border-t border-line">
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
                <tr><td colSpan={13} className="py-6 text-center text-faint">연결된 광고 계정이 없습니다. <Link className="text-primary underline" href="/settings">설정에서 연결</Link></td></tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="최근 대량 작업" actions={<Link href="/jobs" className="text-xs text-primary">전체 보기</Link>}>
          <ul className="flex flex-col divide-y divide-line text-sm">
            {(dash.data?.recent_jobs ?? []).map((j) => (
              <li key={j.id} className="flex items-center gap-2 py-2">
                <Link href={`/jobs?id=${j.id}`} className="font-medium hover:underline">작업 #{j.id}</Link>
                <Badge value={j.status} />
                <span className="text-xs text-faint">성공 {j.counts.SUCCESS} · 실패 {j.counts.FAILED}</span>
                <span className="ml-auto text-xs text-faint">{j.executed_at && new Date(j.executed_at).toLocaleString("ko-KR")}</span>
              </li>
            ))}
            {dash.data?.recent_jobs.length === 0 && <li className="py-2 text-faint">실행한 작업이 없습니다</li>}
          </ul>
        </Card>
        <Card title="동기화 오류 · 실패 작업">
          <ul className="flex flex-col divide-y divide-line text-sm">
            {(dash.data?.sync_errors ?? []).map((s) => (
              <li key={s.ad_account_id} className="py-2"><b>{accountName(s.ad_account_id)}</b> 동기화 실패: <span className="text-danger">{s.error}</span></li>
            ))}
            {(dash.data?.failed_jobs ?? []).map((id) => (
              <li key={id} className="py-2"><Link href={`/jobs?id=${id}`} className="text-danger hover:underline">작업 #{id}에 실패한 행이 있습니다 → 확인·재실행</Link></li>
            ))}
            {dash.data && !dash.data.sync_errors.length && !dash.data.failed_jobs.length && <li className="py-2 text-faint">문제 없음</li>}
          </ul>
        </Card>
      </div>
    </div>
  );
}

interface Goal { ad_account_id: number; roas_target: number; max_bid: number; off_cost: number | null; enabled: boolean; last_run_at: string | null; last_result: string | null }

/** 광고주 계정 목표 ROAS. 서버가 매일 오전 9시 이후 파워링크 키워드를 광고그룹씩 나눠 조정한다(bulk.run_goal_step). */
function GoalCard({ accounts }: { accounts: { id: number; name: string; roas: number | null | undefined; days: number }[] }) {
  const { ws } = useApp();
  const goals = useFetch<Goal[]>(ws && `/workspaces/${ws.id}/account-goals`);
  const byId = new Map((goals.data ?? []).map((g) => [g.ad_account_id, g]));
  return (
    <Card title="목표 ROAS 자동운영">
      <p className="mb-3 text-xs text-muted">
        매일 오전 9시 이후 파워링크 키워드마다 최근 7일 ROAS를 보고, 목표 아래면 입찰가를 10% 내리고 목표보다 10% 넘게 높으면 10% 올립니다.
        계정 전체 ROAS가 목표 아래인 날엔 올리지 않습니다. 클릭 10회 미만·전환 없는 키워드는 그대로 두고, 무전환 OFF 비용을 넣으면
        7일 비용이 그 이상인데 전환이 0인 키워드를 끕니다. 광고그룹이 많으면 10분마다 나눠 진행합니다. 변경은 작업 이력에 남습니다.
      </p>
      <ErrorText error={goals.error} />
      <div className="overflow-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-faint">
            <tr><th className="py-2 pr-3">광고주</th><th className="px-3 text-right">파워링크 ROAS</th><th className="px-3">목표 설정</th><th className="pl-3">최근 실행</th></tr>
          </thead>
          <tbody>
            {accounts.map((a) => (
              <GoalRow key={`${a.id}-${byId.get(a.id)?.roas_target ?? ""}`} account={a} goal={byId.get(a.id)} onDone={goals.reload} />
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function GoalRow({ account, goal, onDone }: { account: { id: number; name: string; roas: number | null | undefined; days: number }; goal?: Goal; onDone: () => void }) {
  const { ws } = useApp();
  const [target, setTarget] = useState(goal ? String(goal.roas_target) : "");
  const [maxBid, setMaxBid] = useState(goal ? String(goal.max_bid) : "");
  const [offCost, setOffCost] = useState(goal?.off_cost ? String(goal.off_cost) : "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const num = (set: (v: string) => void) => (e: { target: { value: string } }) => set(e.target.value.replace(/[^0-9]/g, ""));
  const base = ws ? `/workspaces/${ws.id}/account-goals` : "";
  const call = async (path: string, method: string, body?: unknown) => {
    setBusy(true);
    setError(null);
    try {
      await api(base + path, { method, body });
      onDone();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const save = (enabled: boolean) => call("", "PUT", { ad_account_id: account.id, roas_target: Number(target), max_bid: Number(maxBid), off_cost: offCost ? Number(offCost) : null, enabled });
  return (
    <tr className="border-t border-line align-top">
      <td className="whitespace-nowrap py-2 pr-3 font-medium">{account.name}{goal && !goal.enabled && <span className="ml-1 text-xs text-faint">(중지)</span>}</td>
      <td className="px-3 py-2 text-right tabular-nums" title={`최근 ${account.days}일`}>{account.roas == null ? "-" : `${account.roas}%`}</td>
      <td className="px-3 py-2">
        <div className="flex flex-wrap items-center gap-2">
          <input className={`${inputCls} w-28`} inputMode="numeric" placeholder="목표 ROAS(%)" aria-label={`${account.name} 목표 ROAS`} value={target} onChange={num(setTarget)} />
          <input className={`${inputCls} w-32`} inputMode="numeric" placeholder="최대 입찰가(원)" aria-label={`${account.name} 최대 입찰가`} value={maxBid} onChange={num(setMaxBid)} />
          <input className={`${inputCls} w-40`} inputMode="numeric" placeholder="무전환 OFF 비용(선택)" aria-label={`${account.name} 무전환 OFF 기준 비용`}
            title="키워드의 최근 7일 비용(VAT 포함)이 이 금액 이상인데 전환이 0이면 끕니다" value={offCost} onChange={num(setOffCost)} />
          <Button disabled={busy || !target || !maxBid} onClick={() => save(true)}>{goal ? "저장" : "자동운영 시작"}</Button>
          {goal && <>
            <Button variant="secondary" disabled={busy} onClick={() => call(`/${account.id}/run`, "POST")}>지금 실행</Button>
            <Button variant="secondary" disabled={busy} onClick={() => save(!goal.enabled)}>{goal.enabled ? "중지" : "다시 켜기"}</Button>
            <Button variant="danger" disabled={busy} onClick={() => confirm(`${account.name}의 목표 ROAS 자동운영을 해제할까요?`) && call(`/${account.id}`, "DELETE")}>해제</Button>
          </>}
        </div>
        {error && <p role="alert" className="mt-1 text-xs text-danger">{error}</p>}
      </td>
      <td className="pl-3 py-2 text-xs text-faint" title={goal?.last_run_at ?? undefined}>{goal?.last_result ?? "-"}</td>
    </tr>
  );
}

const REVIEW = ["UNDER_REVIEW", "PENDING"], REJECTED = ["DENIED", "REJECTED", "DISAPPROVED"];

/** 광고 데이터 개수는 브라우저 보관본으로 센다(서버에는 사본이 없다). */
function OpsSummary({ data, autoBids, connected }: { data: NaverData | null; autoBids?: number; connected?: number }) {
  const onOff = (list?: { status: string }[]) => (list ? `${fmt(list.filter((x) => x.status === "ON").length)} / ${fmt(list.filter((x) => x.status === "OFF").length)}` : "-");
  const inspect = (list?: { inspect_status: string }[]) => (list
    ? `${list.filter((x) => REVIEW.includes(x.inspect_status)).length} · ${list.filter((x) => REJECTED.includes(x.inspect_status)).length}` : "-");
  const items: [string, string, string][] = [
    ["연결된 광고 계정", fmt(connected, "개"), "/settings"],
    ["캠페인 ON / OFF", onOff(data?.campaigns), "/campaigns"],
    ["광고그룹 ON / OFF", onOff(data?.adgroups), "/adgroups"],
    ["키워드 ON / OFF", onOff(data?.keywords), "/keywords"],
    ["소재 검수 중 · 반려", inspect(data?.ads), "/ads"],
    ["확장소재 검수 중 · 반려", inspect(data?.extensions), "/extensions"],
    ["자동입찰 키워드", fmt(autoBids, "개"), "/auto-bids"],
  ];
  return (
    <Card title="운영 현황">
      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-4 lg:grid-cols-7">
        {items.map(([label, v, href]) => (
          <div key={label}>
            <dt className="text-xs text-faint">{label}</dt>
            <dd className="mt-0.5 font-semibold tabular-nums">
              <Link href={href} className="hover:underline">{v}</Link>
            </dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}
