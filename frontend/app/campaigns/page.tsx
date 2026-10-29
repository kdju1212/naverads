"use client";

import { useMemo, useState } from "react";
import { BulkBar } from "@/components/BulkBar";
import { Col, DataTable } from "@/components/DataTable";
import { CampaignCreate } from "@/components/CreateForms";
import { DataStatus } from "@/components/DataStatus";
import { Badge, PageTitle } from "@/components/ui";
import { fmt } from "@/lib/api";
import { NCampaign, useNaverData } from "@/lib/naverData";
import { useApp } from "@/lib/store";


export default function CampaignsPage() {
  const { product, accountName } = useApp();
  const data = useNaverData();
  const [sel, setSel] = useState<Set<string>>(new Set());
  const rows = useMemo(() => data.campaigns.filter((c) => !product || c.campaign_tp === product), [data.campaigns, product]);

  const cols: Col<NCampaign>[] = [
    { key: "acc", label: "광고주", value: (r) => accountName(r.ad_account_id) },
    { key: "tp", label: "유형", value: (r) => r.campaign_tp, render: (r) => <Badge value={r.campaign_tp} /> },
    { key: "name", label: "캠페인", value: (r) => r.name },
    { key: "status", filter: true, label: "상태", value: (r) => r.status, render: (r) => <Badge value={r.status} /> },
    { key: "budget", label: "일예산", num: true, value: (r) => r.daily_budget, render: (r) => fmt(r.daily_budget, "원") },
  ];
  return (
    <>
      <PageTitle desc="선택한 계정의 캠페인을 한 번에 조회하고 ON/OFF·일예산을 대량 변경하거나 새 캠페인을 만들고, OFF인 캠페인을 삭제합니다(안의 광고그룹·키워드·소재까지 삭제). 변경은 미리보기 후 실행됩니다.">캠페인</PageTitle>
      <DataStatus data={data} />
      <DataTable rows={rows} cols={cols} selected={sel} onSelect={setSel} loading={data.loading && !rows.length}
        toolbar={<BulkBar entityType="campaign" rows={rows.filter((r) => sel.has(r.id))} numberField={{ field: "daily_budget", label: "일예산" }} deletable />} />
      <CampaignCreate />
    </>
  );
}
