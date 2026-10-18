"use client";

import { useMemo, useState } from "react";
import { BulkBar } from "@/components/BulkBar";
import { Col, DataTable } from "@/components/DataTable";
import { Badge, ErrorText, PageTitle } from "@/components/ui";
import { fmt } from "@/lib/api";
import { useApp } from "@/lib/store";
import { useFetch } from "@/lib/useFetch";

type AdType = "TEXT_45" | "SHOPPING_PRODUCT_AD";
interface Ad {
  id: number; ad_account_id: number; adgroup_id: number; naver_id: string; ad_type: AdType; status: string;
  inspect_status: string; bid_amt: number | null; use_group_bid: boolean; payload: Record<string, unknown>;
}
const str = (v: unknown) => (typeof v === "string" ? v : null);

export default function AdsPage() {
  const { ws, query, product, accountName } = useApp();
  const [picked, setTab] = useState<AdType>("TEXT_45");
  // 상단 광고 유형 필터가 한쪽이면 그 탭만 의미가 있다
  const tab: AdType = product === "SHOPPING" ? "SHOPPING_PRODUCT_AD" : product === "WEB_SITE" ? "TEXT_45" : picked;
  const { data, error, loading } = useFetch<Ad[]>(ws && `/workspaces/${ws.id}/ads${query({ ad_type: tab })}`);
  const [sel, setSel] = useState<Set<number>>(new Set());
  const rows = useMemo(() => data ?? [], [data]);

  const common: Col<Ad>[] = [
    { key: "acc", label: "광고주", value: (r) => accountName(r.ad_account_id) },
    { key: "status", label: "상태", value: (r) => r.status, render: (r) => <Badge value={r.status} /> },
    { key: "inspect", label: "검수", value: (r) => r.inspect_status },
  ];
  const cols: Col<Ad>[] = tab === "TEXT_45" ? [
    common[0],
    { key: "headline", label: "제목", value: (r) => str(r.payload.headline) },
    { key: "desc", label: "설명", value: (r) => str(r.payload.description) },
    { key: "url", label: "연결 URL", value: (r) => str((r.payload.pc as { final?: string } | undefined)?.final) },
    ...common.slice(1),
  ] : [
    common[0],
    { key: "product", label: "상품명", value: (r) => str(r.payload.productName) },
    { key: "pid", label: "상품 ID", value: (r) => str(r.payload.productId) },
    ...common.slice(1),
    { key: "bid", label: "입찰가", num: true, value: (r) => r.bid_amt, render: (r) => (r.use_group_bid ? "그룹 입찰가" : fmt(r.bid_amt, "원")) },
  ];

  return (
    <>
      <PageTitle desc="파워링크 텍스트 소재와 쇼핑검색 상품소재는 구조가 달라 탭을 나눠 관리합니다. 상품 원본 정보는 수정하지 않습니다.">소재 · 상품소재</PageTitle>
      <div className="mb-3 flex gap-1" role="tablist">
        {([["TEXT_45", "파워링크 소재"], ["SHOPPING_PRODUCT_AD", "쇼핑 상품소재"]] as [AdType, string][]).map(([v, label]) => (
          <button key={v} role="tab" aria-selected={tab === v} disabled={product !== "" && tab !== v}
            onClick={() => { setTab(v); setSel(new Set()); }}
            className={`rounded-md px-3 py-1.5 text-sm disabled:opacity-40 ${tab === v ? "bg-gray-900 text-white" : "bg-white border border-gray-300"}`}>{label}</button>
        ))}
      </div>
      <ErrorText error={error} />
      <DataTable key={tab} rows={rows} cols={cols} selected={sel} onSelect={setSel} loading={loading}
        toolbar={<BulkBar entityType="ad" rows={rows.filter((r) => sel.has(r.id))}
          numberField={tab === "SHOPPING_PRODUCT_AD" ? { field: "bid_amt", label: "입찰가" } : undefined} />} />
    </>
  );
}
