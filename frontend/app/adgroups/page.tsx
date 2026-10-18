"use client";

import { useMemo, useState } from "react";
import { BulkBar } from "@/components/BulkBar";
import { Col, DataTable } from "@/components/DataTable";
import { Badge, ErrorText, PageTitle } from "@/components/ui";
import { AdGroup, Campaign, fmt } from "@/lib/api";
import { useApp } from "@/lib/store";
import { useFetch } from "@/lib/useFetch";


export default function AdGroupsPage() {
  const { ws, query, product, accountName } = useApp();
  const groups = useFetch<AdGroup[]>(ws && `/workspaces/${ws.id}/adgroups${query({ product })}`);
  const camps = useFetch<Campaign[]>(ws && `/workspaces/${ws.id}/campaigns${query({ product })}`);
  const [sel, setSel] = useState<Set<number>>(new Set());
  const rows = useMemo(() => groups.data ?? [], [groups.data]);
  const campName = useMemo(() => new Map((camps.data ?? []).map((c) => [c.id, c.name])), [camps.data]);

  const cols: Col<AdGroup>[] = [
    { key: "acc", label: "광고주", value: (r) => accountName(r.ad_account_id) },
    { key: "tp", label: "유형", value: (r) => r.adgroup_type, render: (r) => <Badge value={r.adgroup_type} /> },
    { key: "camp", label: "캠페인", value: (r) => campName.get(r.campaign_id) ?? null },
    { key: "name", label: "광고그룹", value: (r) => r.name },
    { key: "status", label: "상태", value: (r) => r.status, render: (r) => <Badge value={r.status} /> },
    { key: "bid", label: "기본 입찰가", num: true, value: (r) => r.bid_amt, render: (r) => fmt(r.bid_amt, "원") },
  ];
  return (
    <>
      <PageTitle desc="ON/OFF와 기본 입찰가를 여러 계정에 걸쳐 대량 변경합니다.">광고그룹</PageTitle>
      <ErrorText error={groups.error} />
      <DataTable rows={rows} cols={cols} selected={sel} onSelect={setSel} loading={groups.loading}
        toolbar={<BulkBar entityType="adgroup" rows={rows.filter((r) => sel.has(r.id))} numberField={{ field: "bid_amt", label: "입찰가" }} />} />
    </>
  );
}
