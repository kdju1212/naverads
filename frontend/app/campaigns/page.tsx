"use client";

import { useMemo, useState } from "react";
import { BulkBar } from "@/components/BulkBar";
import { Col, DataTable } from "@/components/DataTable";
import { Badge, ErrorText, PageTitle } from "@/components/ui";
import { Campaign, fmt } from "@/lib/api";
import { useApp } from "@/lib/store";
import { useFetch } from "@/lib/useFetch";


export default function CampaignsPage() {
  const { ws, query, product, accountName } = useApp();
  const { data, error, loading } = useFetch<Campaign[]>(ws && `/workspaces/${ws.id}/campaigns${query({ product })}`);
  const [sel, setSel] = useState<Set<number>>(new Set());
  const rows = useMemo(() => data ?? [], [data]);

  const cols: Col<Campaign>[] = [
    { key: "acc", label: "광고주", value: (r) => accountName(r.ad_account_id) },
    { key: "tp", label: "유형", value: (r) => r.campaign_tp, render: (r) => <Badge value={r.campaign_tp} /> },
    { key: "name", label: "캠페인", value: (r) => r.name },
    { key: "status", label: "상태", value: (r) => r.status, render: (r) => <Badge value={r.status} /> },
    { key: "budget", label: "일예산", num: true, value: (r) => r.daily_budget, render: (r) => fmt(r.daily_budget, "원") },
  ];
  return (
    <>
      <PageTitle desc="선택한 계정의 캠페인을 한 번에 조회하고 ON/OFF·일예산을 대량 변경합니다. 변경은 미리보기 후 실행됩니다.">캠페인</PageTitle>
      <ErrorText error={error} />
      <DataTable rows={rows} cols={cols} selected={sel} onSelect={setSel} loading={loading}
        toolbar={<BulkBar entityType="campaign" rows={rows.filter((r) => sel.has(r.id))} numberField={{ field: "daily_budget", label: "일예산" }} />} />
    </>
  );
}
