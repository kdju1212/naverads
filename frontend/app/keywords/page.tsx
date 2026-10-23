"use client";

import { useMemo, useState } from "react";
import { BulkBar } from "@/components/BulkBar";
import { Col, DataTable } from "@/components/DataTable";
import { DataStatus } from "@/components/DataStatus";
import { useRanks } from "@/components/RankCheck";
import { Badge, Card, PageTitle } from "@/components/ui";
import { fmt } from "@/lib/api";
import { Keyword, useNaverData } from "@/lib/naverData";
import { useApp } from "@/lib/store";

export default function KeywordsPage() {
  const { product, accountName } = useApp();
  const shoppingOnly = product === "SHOPPING";
  const data = useNaverData();
  const rank = useRanks();
  const [sel, setSel] = useState<Set<string>>(new Set());
  const rows = data.keywords;
  const groupName = useMemo(() => new Map(data.adgroups.map((g) => [g.naver_id, g.name])), [data.adgroups]);

  if (shoppingOnly) {
    return (
      <>
        <PageTitle>키워드</PageTitle>
        <Card><p className="text-sm text-muted">키워드는 파워링크 전용입니다. 쇼핑검색광고는 <b>소재·상품소재</b> 메뉴에서 상품소재 단위로 관리합니다.</p></Card>
      </>
    );
  }

  const cols: Col<Keyword>[] = [
    { key: "acc", label: "광고주", value: (r) => accountName(r.ad_account_id) },
    { key: "grp", label: "광고그룹", value: (r) => groupName.get(r.adgroup_naver_id) ?? null },
    { key: "kw", label: "키워드", value: (r) => r.keyword },
    { key: "status", label: "상태", value: (r) => r.status, render: (r) => <Badge value={r.status} /> },
    { key: "bid", label: "입찰가", num: true, value: (r) => r.bid_amt, render: (r) => (r.use_group_bid ? "그룹 입찰가" : fmt(r.bid_amt, "원")) },
    rank.col,
  ];
  const selected = rows.filter((r) => sel.has(r.id));
  return (
    <>
      <PageTitle desc="파워링크 키워드를 대량 삭제하고 ON/OFF·입찰가를 대량 변경합니다. 등록은 '키워드 등록', 자동입찰은 '자동입찰' 메뉴에서 합니다.">키워드 (파워링크)</PageTitle>
      <DataStatus data={data} />
      <DataTable rows={rows} cols={cols} selected={sel} onSelect={setSel} loading={data.loading && !rows.length}
        toolbar={<div className="flex flex-wrap items-center gap-2">{rank.button(selected)}
          <BulkBar entityType="keyword" rows={selected} numberField={{ field: "bid_amt", label: "입찰가" }} deletable /></div>} />
    </>
  );
}
