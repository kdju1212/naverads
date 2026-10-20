"use client";

import { useMemo, useState } from "react";
import { BulkBar } from "@/components/BulkBar";
import { Col, DataTable } from "@/components/DataTable";
import { Badge, Button, ErrorText, PageTitle } from "@/components/ui";
import { AdGroup, Campaign, downloadCsv, fmt, PRODUCT_LABEL, servingLabel } from "@/lib/api";
import { useApp } from "@/lib/store";
import { useFetch } from "@/lib/useFetch";


export default function AdGroupsPage() {
  const { ws, query, product, accountName } = useApp();
  const groups = useFetch<AdGroup[]>(ws && `/workspaces/${ws.id}/adgroups${query({ product })}`);
  const camps = useFetch<Campaign[]>(ws && `/workspaces/${ws.id}/campaigns${query({ product })}`);
  const [sel, setSel] = useState<Set<number>>(new Set());
  const rows = useMemo(() => groups.data ?? [], [groups.data]);
  const campById = useMemo(() => new Map((camps.data ?? []).map((c) => [c.id, c])), [camps.data]);
  const campName = useMemo(() => new Map([...campById].map(([id, c]) => [id, c.name])), [campById]);
  // 키워드 등록 엑셀에 넣을 광고그룹 ID를 찾기 쉽게: 상단 계정·유형 필터가 적용된 전체 목록
  const download = () => downloadCsv([
    ["광고주", "유형", "캠페인명", "캠페인 ID", "광고그룹명", "광고그룹 ID", "상태", "운영 상태", "하루예산"],
    ...rows.map((r) => [accountName(r.ad_account_id), PRODUCT_LABEL[r.adgroup_type] ?? r.adgroup_type, campById.get(r.campaign_id)?.name ?? "",
      campById.get(r.campaign_id)?.naver_id ?? "", r.name, r.naver_id, r.status, servingLabel(r.serving), r.daily_budget ?? "제한 없음"]),
  ], "adgroups.csv");

  const cols: Col<AdGroup>[] = [
    { key: "acc", label: "광고주", value: (r) => accountName(r.ad_account_id) },
    { key: "tp", label: "유형", value: (r) => r.adgroup_type, render: (r) => <Badge value={r.adgroup_type} /> },
    { key: "camp", label: "캠페인", value: (r) => campName.get(r.campaign_id) ?? null },
    { key: "name", label: "광고그룹", value: (r) => r.name },
    { key: "status", label: "상태", value: (r) => r.status, render: (r) => <Badge value={r.status} /> },
    { key: "serving", label: "운영 상태", value: (r) => servingLabel(r.serving),
      render: (r) => <span className={r.serving && r.serving !== "ELIGIBLE" ? "text-amber-700" : ""}>{servingLabel(r.serving)}</span> },
    { key: "budget", label: "하루예산", num: true, value: (r) => r.daily_budget, render: (r) => (r.daily_budget == null ? "제한 없음" : fmt(r.daily_budget, "원")) },
    { key: "bid", label: "기본 입찰가", num: true, value: (r) => r.bid_amt, render: (r) => fmt(r.bid_amt, "원") },
  ];
  return (
    <>
      <PageTitle desc="ON/OFF와 기본 입찰가를 여러 계정에 걸쳐 대량 변경합니다.">광고그룹</PageTitle>
      <ErrorText error={groups.error} />
      <DataTable rows={rows} cols={cols} selected={sel} onSelect={setSel} loading={groups.loading}
        toolbar={
          <>
            <BulkBar entityType="adgroup" rows={rows.filter((r) => sel.has(r.id))} numberField={{ field: "bid_amt", label: "입찰가" }} />
            <Button variant="secondary" disabled={rows.length === 0} onClick={download}>다운로드 (엑셀)</Button>
          </>
        } />
    </>
  );
}
