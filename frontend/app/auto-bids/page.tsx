"use client";

import { useRouter } from "next/navigation";
import { ReactNode, useMemo, useState } from "react";
import { Col, DataTable } from "@/components/DataTable";
import { DataStatus } from "@/components/DataStatus";
import { useRanks } from "@/components/RankCheck";
import { Button, Card, ErrorText, inputCls, PageTitle } from "@/components/ui";
import { api, fmt } from "@/lib/api";
import { Keyword, refreshAccounts, useNaverData } from "@/lib/naverData";
import { useApp } from "@/lib/store";
import { useFetch } from "@/lib/useFetch";

interface AutoBid {
  id: number; ad_account_id: number; keyword_naver_id: string; keyword: string; device: "PC" | "MOBILE"; target_rank: number;
  max_bid: number; kpi: Kpi | null; kpi_target: number | null; off_cost: number | null; enabled: boolean; last_run_at: string | null; last_result: string | null;
}

const DEVICE_LABEL = { PC: "PC", MOBILE: "모바일" };
type Kpi = "CPA" | "ROAS" | "CPC";
const kpiText = (a: AutoBid) => `${a.kpi} ${fmt(a.kpi_target, a.kpi === "ROAS" ? "%" : "원")}` + (a.off_cost ? ` · 무전환 ${fmt(a.off_cost, "원")} OFF` : "");

/** 선택한 키워드에 목표 순위 또는 KPI 자동입찰을 설정·해제하고, 지금 실행한다. 순위는 10분마다, KPI는 하루 한 번 자동 실행된다. */
function AutoBidBar({ picked, onDone, rankButton }: { picked: Keyword[]; onDone: () => void; rankButton: ReactNode }) {
  const { ws } = useApp();
  const router = useRouter();
  const [device, setDevice] = useState<"PC" | "MOBILE">("PC");
  const [rank, setRank] = useState("3");
  const [maxBid, setMaxBid] = useState("");
  const [kpi, setKpi] = useState<Kpi | "">("");
  const [kpiTarget, setKpiTarget] = useState("");
  const [offCost, setOffCost] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const call = async (path: string, body: unknown, method = "POST") => {
    if (!ws) return;
    setBusy(true);
    setError(null);
    try {
      const r = await api<{ job_ids?: number[] }>(`/workspaces/${ws.id}/auto-bids${path}`, { method, body });
      onDone();
      if (r.job_ids?.length) router.push(`/jobs?id=${r.job_ids[0]}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const none = busy || picked.length === 0;
  const keywords = picked.map((k) => ({ ad_account_id: k.ad_account_id, naver_id: k.naver_id, keyword: k.keyword }));
  const ranks = device === "PC" ? 10 : 5;
  const num = (set: (v: string) => void) => (e: { target: { value: string } }) => set(e.target.value.replace(/[^0-9]/g, ""));
  const rule = kpi
    ? { kpi, kpi_target: Number(kpiTarget), off_cost: offCost ? Number(offCost) : null }
    : { device, target_rank: Number(rank) };
  return (
    <div className="flex flex-wrap items-center gap-2">
      {error && <span role="alert" className="text-xs text-danger">{error}</span>}
      {rankButton}
      <select className={inputCls} aria-label="기준" value={kpi} onChange={(e) => setKpi(e.target.value as Kpi | "")}>
        <option value="">목표 순위</option>
        <option value="CPA">CPA (전환당 비용)</option>
        <option value="ROAS">ROAS (광고수익률)</option>
        <option value="CPC">CPC (클릭당 비용)</option>
      </select>
      {kpi ? (
        <>
          <input className={`${inputCls} w-32`} inputMode="numeric" placeholder={kpi === "ROAS" ? "목표 ROAS(%)" : `목표 ${kpi}(원)`}
            aria-label="KPI 목표" value={kpiTarget} onChange={num(setKpiTarget)} />
          <input className={`${inputCls} w-40`} inputMode="numeric" placeholder="무전환 OFF 비용(선택)" aria-label="무전환 OFF 기준 비용"
            title="최근 7일 비용이 이 금액 이상인데 전환이 0이면 키워드를 끕니다" value={offCost} onChange={num(setOffCost)} />
        </>
      ) : (<>
      <select className={inputCls} aria-label="기기" value={device}
        onChange={(e) => { const d = e.target.value as "PC" | "MOBILE"; setDevice(d); if (d === "MOBILE" && Number(rank) > 5) setRank("5"); }}>
        <option value="PC">PC</option>
        <option value="MOBILE">모바일</option>
      </select>
      <select className={inputCls} aria-label="목표 순위" value={rank} onChange={(e) => setRank(e.target.value)}>
        {Array.from({ length: ranks }, (_, i) => <option key={i + 1} value={i + 1}>{i + 1}위</option>)}
      </select>
      </>)}
      <input className={`${inputCls} w-32`} inputMode="numeric" placeholder="최대 입찰가(원)" aria-label="최대 입찰가"
        value={maxBid} onChange={num(setMaxBid)} />
      <Button disabled={none || !maxBid || (!!kpi && !kpiTarget)}
        onClick={() => call("", { keywords, ...rule, max_bid: Number(maxBid) }, "PUT")}>자동입찰 설정</Button>
      <Button variant="secondary" disabled={none} onClick={() => call("/run", { keywords })}>지금 실행</Button>
      <Button variant="danger" disabled={none} onClick={() => confirm(`${picked.length}개 키워드의 자동입찰을 해제할까요?`) && call("/delete", { keywords })}>해제</Button>
    </div>
  );
}

export default function AutoBidsPage() {
  const { ws, product, accountName } = useApp();
  const shoppingOnly = product === "SHOPPING";
  const data = useNaverData();
  const rank = useRanks();
  const autoBids = useFetch<AutoBid[]>(ws && !shoppingOnly ? `/workspaces/${ws.id}/auto-bids` : null);
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [addSel, setAddSel] = useState<Set<string>>(new Set());
  const groupName = useMemo(() => new Map(data.adgroups.map((g) => [g.naver_id, g.name])), [data.adgroups]);
  const rule = useMemo(() => new Map((autoBids.data ?? []).map((r) => [r.keyword_naver_id, r])), [autoBids.data]);
  const rows = data.keywords.filter((k) => rule.has(k.naver_id));
  const others = data.keywords.filter((k) => !rule.has(k.naver_id));

  if (shoppingOnly) {
    return (
      <>
        <PageTitle>자동입찰</PageTitle>
        <Card><p className="text-sm text-muted">자동입찰은 파워링크 키워드 전용입니다.</p></Card>
      </>
    );
  }

  const cols: Col<Keyword>[] = [
    { key: "acc", label: "광고주", value: (r) => accountName(r.ad_account_id) },
    { key: "grp", label: "광고그룹", value: (r) => groupName.get(r.adgroup_naver_id) ?? null },
    { key: "kw", label: "키워드", value: (r) => r.keyword },
    { key: "bid", label: "현재 입찰가", num: true, value: (r) => r.bid_amt, render: (r) => (r.use_group_bid ? "그룹 입찰가" : fmt(r.bid_amt, "원")) },
    {
      key: "auto", label: "자동입찰", value: (r) => { const a = rule.get(r.naver_id); return a ? (a.kpi ? kpiText(a) : a.target_rank) : null; },
      render: (r) => {
        const a = rule.get(r.naver_id);
        if (!a) return <span className="text-faint">-</span>;
        return <span className="text-xs">{a.kpi ? kpiText(a) : `${DEVICE_LABEL[a.device]} ${a.target_rank}위`} · 최대 {fmt(a.max_bid, "원")}</span>;
      },
    },
    {
      key: "result", label: "최근 실행", value: (r) => rule.get(r.naver_id)?.last_result ?? null,
      render: (r) => {
        const a = rule.get(r.naver_id);
        return a?.last_result ? <span className="text-xs text-faint" title={a.last_run_at ?? undefined}>{a.last_result}</span> : <span className="text-faint">-</span>;
      },
    },
  ];
  const selected = rows.filter((r) => sel.has(r.id));
  const adding = others.filter((r) => addSel.has(r.id));
  const done = (picked: Keyword[]) => {
    autoBids.reload();
    // 지금 실행으로 입찰가가 바뀌었을 수 있다
    if (ws) void refreshAccounts(ws.id, [...new Set(picked.map((k) => k.ad_account_id))]);
  };
  return (
    <>
      <PageTitle desc="파워링크 키워드에 목표 순위를 정해 두면 10분마다 네이버 검색 화면에서 지금 순위를 확인해, 목표보다 아래면 입찰가를 20% 올리고 위면 10% 내립니다. KPI(CPA·ROAS·CPC, 비용은 VAT 포함)를 고르면 매일 오전 9시 이후 한 번 최근 7일 성과를 보고, 목표보다 10% 넘게 좋으면 10% 올리고 나쁘면 10% 내립니다(클릭 10회 미만·전환 없음이면 그대로). 무전환 OFF 비용을 넣으면 7일 비용이 그 이상인데 전환이 0인 키워드를 끕니다. 최대 입찰가는 넘지 않고, OFF인 키워드·광고그룹은 건너뜁니다.">자동입찰</PageTitle>
      <DataStatus data={data} />
      <ErrorText error={autoBids.error} />
      <DataTable rows={rows} cols={cols} selected={sel} onSelect={setSel} loading={(data.loading || autoBids.loading) && !rows.length}
        toolbar={<AutoBidBar picked={selected} rankButton={rank.button(selected)} onDone={() => { done(selected); setSel(new Set()); }} />} />
      <details className="mt-3 rounded-panel border border-line bg-surface">
        <summary className="cursor-pointer px-4 py-3 text-[15px] font-semibold">자동입찰 추가 · 아직 설정 안 된 키워드 {fmt(others.length)}개</summary>
        <div className="p-2">
          <DataTable rows={others} cols={[...cols.slice(0, 4), rank.col]} selected={addSel} onSelect={setAddSel} loading={data.loading && !others.length}
            toolbar={<AutoBidBar picked={adding} rankButton={rank.button(adding)} onDone={() => { done(adding); setAddSel(new Set()); }} />} />
        </div>
      </details>
    </>
  );
}
