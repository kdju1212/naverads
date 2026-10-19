"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { BulkBar } from "@/components/BulkBar";
import { Col, DataTable } from "@/components/DataTable";
import { Badge, Button, Card, ErrorText, inputCls, PageTitle } from "@/components/ui";
import { AdGroup, api, fmt } from "@/lib/api";
import { useApp } from "@/lib/store";
import { useFetch } from "@/lib/useFetch";

interface Keyword { id: number; ad_account_id: number; adgroup_id: number; naver_id: string; keyword: string; status: string; bid_amt: number; use_group_bid: boolean }
interface AutoBid { id: number; keyword_id: number; device: "PC" | "MOBILE"; target_rank: number; max_bid: number; enabled: boolean; last_run_at: string | null; last_result: string | null }

const DEVICE_LABEL = { PC: "PC", MOBILE: "모바일" };

/** 선택한 키워드에 목표 순위 자동입찰을 설정·해제하고, 지금 실행한다. 매시 정각에도 자동 실행된다. */
function AutoBidBar({ ids, onDone }: { ids: number[]; onDone: () => void }) {
  const { ws } = useApp();
  const router = useRouter();
  const [device, setDevice] = useState<"PC" | "MOBILE">("PC");
  const [rank, setRank] = useState("3");
  const [maxBid, setMaxBid] = useState("");
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

  const none = busy || ids.length === 0;
  const ranks = device === "PC" ? 10 : 5;
  return (
    <div className="flex flex-wrap items-center gap-2">
      {error && <span role="alert" className="text-xs text-red-600">{error}</span>}
      <select className={inputCls} aria-label="기기" value={device}
        onChange={(e) => { const d = e.target.value as "PC" | "MOBILE"; setDevice(d); if (d === "MOBILE" && Number(rank) > 5) setRank("5"); }}>
        <option value="PC">PC</option>
        <option value="MOBILE">모바일</option>
      </select>
      <select className={inputCls} aria-label="목표 순위" value={rank} onChange={(e) => setRank(e.target.value)}>
        {Array.from({ length: ranks }, (_, i) => <option key={i + 1} value={i + 1}>{i + 1}위</option>)}
      </select>
      <input className={`${inputCls} w-32`} inputMode="numeric" placeholder="최대 입찰가(원)" aria-label="최대 입찰가"
        value={maxBid} onChange={(e) => setMaxBid(e.target.value.replace(/[^0-9]/g, ""))} />
      <Button disabled={none || !maxBid}
        onClick={() => call("", { keyword_ids: ids, device, target_rank: Number(rank), max_bid: Number(maxBid) }, "PUT")}>자동입찰 설정</Button>
      <Button variant="secondary" disabled={none} onClick={() => call("/run", { keyword_ids: ids })}>지금 실행</Button>
      <Button variant="danger" disabled={none} onClick={() => confirm(`${ids.length}개 키워드의 자동입찰을 해제할까요?`) && call("/delete", { keyword_ids: ids })}>해제</Button>
    </div>
  );
}

export default function KeywordsPage() {
  const { ws, query, product, accountName } = useApp();
  const shoppingOnly = product === "SHOPPING";
  const kws = useFetch<Keyword[]>(ws && !shoppingOnly ? `/workspaces/${ws.id}/keywords${query()}` : null);
  const groups = useFetch<AdGroup[]>(ws && !shoppingOnly ? `/workspaces/${ws.id}/adgroups${query({ product: "WEB_SITE" })}` : null);
  const autoBids = useFetch<AutoBid[]>(ws && !shoppingOnly ? `/workspaces/${ws.id}/auto-bids` : null);
  const [sel, setSel] = useState<Set<number>>(new Set());
  const rows = useMemo(() => kws.data ?? [], [kws.data]);
  const groupName = useMemo(() => new Map((groups.data ?? []).map((g) => [g.id, g.name])), [groups.data]);
  const rule = useMemo(() => new Map((autoBids.data ?? []).map((r) => [r.keyword_id, r])), [autoBids.data]);

  if (shoppingOnly) {
    return (
      <>
        <PageTitle>키워드</PageTitle>
        <Card><p className="text-sm text-gray-600">키워드는 파워링크 전용입니다. 쇼핑검색광고는 <b>소재·상품소재</b> 메뉴에서 상품소재 단위로 관리합니다.</p></Card>
      </>
    );
  }

  const cols: Col<Keyword>[] = [
    { key: "acc", label: "광고주", value: (r) => accountName(r.ad_account_id) },
    { key: "grp", label: "광고그룹", value: (r) => groupName.get(r.adgroup_id) ?? null },
    { key: "kw", label: "키워드", value: (r) => r.keyword },
    { key: "status", label: "상태", value: (r) => r.status, render: (r) => <Badge value={r.status} /> },
    { key: "bid", label: "입찰가", num: true, value: (r) => r.bid_amt, render: (r) => (r.use_group_bid ? "그룹 입찰가" : fmt(r.bid_amt, "원")) },
    {
      key: "auto", label: "자동입찰", value: (r) => rule.get(r.id)?.target_rank ?? null,
      render: (r) => {
        const a = rule.get(r.id);
        if (!a) return <span className="text-gray-400">-</span>;
        return (
          <div className="text-xs">
            <div>{DEVICE_LABEL[a.device]} {a.target_rank}위 · 최대 {fmt(a.max_bid, "원")}</div>
            {a.last_result && <div className="text-gray-500" title={a.last_run_at ?? undefined}>{a.last_result}</div>}
          </div>
        );
      },
    },
  ];
  const selected = rows.filter((r) => sel.has(r.id));
  return (
    <>
      <PageTitle desc="파워링크 키워드의 ON/OFF·입찰가를 대량 변경합니다. 자동입찰은 네이버 '순위별 예상 입찰가'로 매시 정각에 입찰가를 맞추며 최대 입찰가를 넘지 않습니다.">키워드 (파워링크)</PageTitle>
      <ErrorText error={kws.error ?? autoBids.error} />
      <DataTable rows={rows} cols={cols} selected={sel} onSelect={setSel} loading={kws.loading}
        toolbar={
          <div className="flex flex-col gap-2">
            <BulkBar entityType="keyword" rows={selected} numberField={{ field: "bid_amt", label: "입찰가" }} />
            <AutoBidBar ids={selected.map((r) => r.id)} onDone={() => { autoBids.reload(); kws.reload(); }} />
          </div>
        } />
    </>
  );
}
