"use client";

import { useMemo, useState } from "react";
import { BulkBar } from "@/components/BulkBar";
import { Col, DataTable } from "@/components/DataTable";
import { DataStatus } from "@/components/DataStatus";
import { usePerf } from "@/components/PerfCheck";
import { Badge, Button, PageTitle } from "@/components/ui";
import { downloadCsv, fmt, PRODUCT_LABEL, servingLabel } from "@/lib/api";
import { NAdGroup, useNaverData } from "@/lib/naverData";
import { useApp } from "@/lib/store";


// 광고그룹을 끈 경우 네이버는 PAUSED만 주거나 캠페인 쪽 이유를 줄 수 있어, 앱의 ON/OFF를 함께 보여 준다
const serving = (r: NAdGroup) => {
  const reason = servingLabel(r.serving);
  if (r.status !== "OFF") return reason;
  return ["광고그룹 OFF", "중지", "-"].includes(reason) ? "광고그룹 OFF" : `광고그룹 OFF · ${reason}`;
};

export default function AdGroupsPage() {
  const { product, accountName } = useApp();
  const data = useNaverData();
  const [sel, setSel] = useState<Set<string>>(new Set());
  const perf = usePerf<NAdGroup>();
  const rows = useMemo(() => data.adgroups.filter((g) => !product || g.adgroup_type === product), [data.adgroups, product]);
  const campById = useMemo(() => new Map(data.campaigns.map((c) => [c.naver_id, c])), [data.campaigns]);
  // 키워드 등록 엑셀에 넣을 광고그룹 ID를 찾기 쉽게: 상단 계정·유형 필터가 적용된 전체 목록
  const download = () => downloadCsv([
    ["광고주", "유형", "캠페인명", "캠페인 ID", "광고그룹명", "광고그룹 ID", "상태", "운영 상태", "하루예산"],
    ...rows.map((r) => [accountName(r.ad_account_id), PRODUCT_LABEL[r.adgroup_type] ?? r.adgroup_type, campById.get(r.campaign_naver_id)?.name ?? "",
      r.campaign_naver_id, r.name, r.naver_id, r.status, serving(r), r.daily_budget ?? "제한 없음"]),
  ], "adgroups.csv");

  const cols: Col<NAdGroup>[] = [
    { key: "acc", label: "광고주", value: (r) => accountName(r.ad_account_id) },
    { key: "tp", label: "유형", value: (r) => r.adgroup_type, render: (r) => <Badge value={r.adgroup_type} /> },
    { key: "camp", label: "캠페인", value: (r) => campById.get(r.campaign_naver_id)?.name ?? null },
    { key: "name", label: "광고그룹", value: (r) => r.name },
    { key: "status", label: "상태", value: (r) => r.status, render: (r) => <Badge value={r.status} /> },
    { key: "serving", label: "운영 상태", value: serving,
      render: (r) => <span className={r.status === "OFF" || (r.serving && r.serving !== "ELIGIBLE") ? "text-warning" : ""}>{serving(r)}</span> },
    { key: "budget", label: "하루예산", num: true, value: (r) => r.daily_budget, render: (r) => (r.daily_budget == null ? "제한 없음" : fmt(r.daily_budget, "원")) },
    { key: "bid", label: "기본 입찰가", num: true, value: (r) => r.bid_amt, render: (r) => fmt(r.bid_amt, "원") },
    ...perf.cols,
  ];
  return (
    <>
      <PageTitle desc="ON/OFF와 기본 입찰가를 여러 계정에 걸쳐 대량 변경합니다.">광고그룹</PageTitle>
      <DataStatus data={data} />
      <DataTable rows={rows} cols={cols} selected={sel} onSelect={setSel} loading={data.loading && !rows.length}
        toolbar={
          <>
            {perf.button(rows.filter((r) => sel.has(r.id)))}
            <BulkBar entityType="adgroup" rows={rows.filter((r) => sel.has(r.id))} numberField={{ field: "bid_amt", label: "입찰가" }} />
            <Button variant="secondary" disabled={rows.length === 0} onClick={download}>다운로드 (엑셀)</Button>
          </>
        } />
    </>
  );
}
