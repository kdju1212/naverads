"use client";

import { useMemo, useState } from "react";
import { BulkBar } from "@/components/BulkBar";
import { Col, DataTable } from "@/components/DataTable";
import { Badge, Card, ErrorText, PageTitle } from "@/components/ui";
import { AdGroup, fmt } from "@/lib/api";
import { useApp } from "@/lib/store";
import { useFetch } from "@/lib/useFetch";

interface Keyword { id: number; ad_account_id: number; adgroup_id: number; naver_id: string; keyword: string; status: string; bid_amt: number; use_group_bid: boolean }

export default function KeywordsPage() {
  const { ws, query, product, accountName } = useApp();
  const shoppingOnly = product === "SHOPPING";
  const kws = useFetch<Keyword[]>(ws && !shoppingOnly ? `/workspaces/${ws.id}/keywords${query()}` : null);
  const groups = useFetch<AdGroup[]>(ws && !shoppingOnly ? `/workspaces/${ws.id}/adgroups${query({ product: "WEB_SITE" })}` : null);
  const [sel, setSel] = useState<Set<number>>(new Set());
  const rows = useMemo(() => kws.data ?? [], [kws.data]);
  const groupName = useMemo(() => new Map((groups.data ?? []).map((g) => [g.id, g.name])), [groups.data]);

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
  ];
  return (
    <>
      <PageTitle desc="파워링크 키워드의 ON/OFF·입찰가를 대량 변경합니다. 신규 대량 등록은 네이버 공식 API 검증 후 제공됩니다.">키워드 (파워링크)</PageTitle>
      <ErrorText error={kws.error} />
      <DataTable rows={rows} cols={cols} selected={sel} onSelect={setSel} loading={kws.loading}
        toolbar={<BulkBar entityType="keyword" rows={rows.filter((r) => sel.has(r.id))} numberField={{ field: "bid_amt", label: "입찰가" }} />} />
    </>
  );
}
