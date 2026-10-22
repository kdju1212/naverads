"use client";

import { useMemo, useState } from "react";
import { BulkBar } from "@/components/BulkBar";
import { Col, DataTable } from "@/components/DataTable";
import { DataStatus } from "@/components/DataStatus";
import { Badge, PageTitle } from "@/components/ui";
import { fmt, inspectLabel } from "@/lib/api";
import { NAd as Ad, useNaverData } from "@/lib/naverData";
import { useApp } from "@/lib/store";

type AdType = "TEXT_45" | "SHOPPING_PRODUCT_AD";
const str = (v: unknown) => (typeof v === "string" ? v : null);
// RSA_AD는 제목·설명이 여러 개(headlines/descriptions)로 온다
const texts = (v: unknown) => (Array.isArray(v) && v.length ? v.join(" / ") : null);

export default function AdsPage() {
  const { product, accountName } = useApp();
  const data = useNaverData();
  const [picked, setTab] = useState<AdType>("TEXT_45");
  // 상단 광고 유형 필터가 한쪽이면 그 탭만 의미가 있다
  const tab: AdType = product === "SHOPPING" ? "SHOPPING_PRODUCT_AD" : product === "WEB_SITE" ? "TEXT_45" : picked;
  const [sel, setSel] = useState<Set<string>>(new Set());
  // 파워링크 소재 탭에는 반응형 검색광고(RSA_AD)도 함께 보여 준다
  const rows = useMemo(() => data.ads.filter((a) => (tab === "TEXT_45" ? a.ad_type !== "SHOPPING_PRODUCT_AD" : a.ad_type === tab)), [data.ads, tab]);

  const common: Col<Ad>[] = [
    { key: "acc", label: "광고주", value: (r) => accountName(r.ad_account_id) },
    { key: "status", label: "상태", value: (r) => r.status, render: (r) => <Badge value={r.status} /> },
    { key: "inspect", label: "검수", value: (r) => inspectLabel(r.inspect_status) },
  ];
  const cols: Col<Ad>[] = tab === "TEXT_45" ? [
    common[0],
    { key: "type", label: "유형", value: (r) => (r.ad_type === "RSA_AD" ? "반응형" : "텍스트") },
    { key: "headline", label: "제목", value: (r) => str(r.payload.headline) ?? texts(r.payload.headlines) },
    { key: "desc", label: "설명", value: (r) => str(r.payload.description) ?? texts(r.payload.descriptions) },
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
      <DataStatus data={data} />
      <DataTable key={tab} rows={rows} cols={cols} selected={sel} onSelect={setSel} loading={data.loading && !rows.length}
        toolbar={<BulkBar entityType="ad" rows={rows.filter((r) => sel.has(r.id))}
          numberField={tab === "SHOPPING_PRODUCT_AD" ? { field: "bid_amt", label: "입찰가" } : undefined} />} />
    </>
  );
}
