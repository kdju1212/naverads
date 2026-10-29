"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { BulkBar } from "@/components/BulkBar";
import { Col, DataTable } from "@/components/DataTable";
import { AdGroupCreate } from "@/components/CreateForms";
import { DataStatus } from "@/components/DataStatus";
import { usePerf } from "@/components/PerfCheck";
import { Badge, Button, Card, ErrorText, inputCls, PageTitle } from "@/components/ui";
import { api, downloadCsv, fmt, Job, PRODUCT_LABEL, servingLabel } from "@/lib/api";
import { NAdGroup, useNaverData } from "@/lib/naverData";
import { useApp } from "@/lib/store";
import { useFetch } from "@/lib/useFetch";


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
    { key: "status", filter: true, label: "상태", value: (r) => r.status, render: (r) => <Badge value={r.status} /> },
    { key: "serving", filter: true, label: "운영 상태", value: serving,
      render: (r) => <span className={r.status === "OFF" || (r.serving && r.serving !== "ELIGIBLE") ? "text-warning" : ""}>{serving(r)}</span> },
    { key: "budget", label: "하루예산", num: true, value: (r) => r.daily_budget, render: (r) => (r.daily_budget == null ? "제한 없음" : fmt(r.daily_budget, "원")) },
    { key: "bid", label: "기본 입찰가", num: true, value: (r) => r.bid_amt, render: (r) => fmt(r.bid_amt, "원") },
    ...perf.cols,
  ];
  return (
    <>
      <PageTitle desc="ON/OFF와 기본 입찰가를 여러 계정에 걸쳐 대량 변경하거나 새 광고그룹을 만들고, OFF인 광고그룹을 삭제합니다(안의 키워드·소재까지 삭제).">광고그룹</PageTitle>
      <DataStatus data={data} />
      <DataTable rows={rows} cols={cols} selected={sel} onSelect={setSel} loading={data.loading && !rows.length}
        toolbar={
          <>
            {perf.button(rows.filter((r) => sel.has(r.id)))}
            <BulkBar entityType="adgroup" rows={rows.filter((r) => sel.has(r.id))} numberField={{ field: "bid_amt", label: "입찰가" }} deletable />
            <Button variant="secondary" disabled={rows.length === 0} onClick={download}>다운로드 (엑셀)</Button>
          </>
        } />
      <NegativeKeywords groups={rows.filter((r) => sel.has(r.id))} />
      <AdGroupCreate campaigns={data.campaigns.filter((c) => !product || c.campaign_tp === product)} />
    </>
  );
}

interface Negative { naver_id: string; adgroup_naver_id: string; keyword: string }

/** 선택한 광고그룹의 제외검색어. 목록은 광고그룹 1개를 골랐을 때 네이버에서 바로 읽고, 등록·삭제는 대량 작업 미리보기로 만든다(예약 실행 가능). */
function NegativeKeywords({ groups }: { groups: NAdGroup[] }) {
  const { ws } = useApp();
  const router = useRouter();
  const one = groups.length === 1 ? groups[0] : null;
  const list = useFetch<Negative[]>(ws && one && `/workspaces/${ws.id}/ad-accounts/${one.ad_account_id}/adgroups/${one.naver_id}/negative-keywords`);
  const [text, setText] = useState("");
  const [del, setDel] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!groups.length) return null;

  const words = [...new Set(text.split(/[\n,]/).map((w) => w.trim()).filter(Boolean))];
  const submit = async (changes: object[]) => {
    if (!ws) return;
    setBusy(true);
    setError(null);
    try {
      const job = await api<Job>(`/workspaces/${ws.id}/bulk-jobs`, { body: { changes } });
      router.push(`/jobs?id=${job.id}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  };
  const base = (g: { ad_account_id: number }) => ({ entity_type: "negative_keyword", ad_account_id: g.ad_account_id });
  const add = () => submit(groups.flatMap((g) => words.map((w) => ({ ...base(g), naver_id: g.naver_id, field: "create", value: w }))));
  const remove = () => one && submit((list.data ?? []).filter((n) => del.has(n.naver_id))
    .map((n) => ({ ...base(one), naver_id: n.naver_id, field: "delete", value: n.adgroup_naver_id })));

  return (
    <Card className="mt-3" title={one ? `제외검색어 · ${one.name}` : `제외검색어 · 광고그룹 ${groups.length}개`}>
      <p className="mb-3 text-xs text-muted">이 검색어로 검색하면 광고가 노출되지 않습니다. 등록·삭제는 작업 미리보기로 넘어가 바로 실행하거나 시간을 정해 예약할 수 있습니다.</p>
      <ErrorText error={error ?? list.error} />
      {one ? (
        <div className="mb-3">
          {list.loading ? <p className="text-sm text-faint">불러오는 중…</p> : (list.data ?? []).length === 0 ? <p className="text-sm text-faint">등록된 제외검색어가 없습니다</p> : (
            <ul className="flex flex-wrap gap-2">
              {(list.data ?? []).map((n) => (
                <li key={n.naver_id}>
                  <label className="flex items-center gap-1.5 rounded-control border border-line px-2 py-1 text-sm">
                    <input type="checkbox" checked={del.has(n.naver_id)}
                      onChange={(e) => { const s = new Set(del); if (e.target.checked) s.add(n.naver_id); else s.delete(n.naver_id); setDel(s); }} />
                    {n.keyword}
                  </label>
                </li>
              ))}
            </ul>
          )}
          {del.size > 0 && <Button className="mt-2" variant="danger" disabled={busy} onClick={remove}>선택한 {del.size}개 삭제 미리보기</Button>}
        </div>
      ) : <p className="mb-3 text-sm text-faint">목록은 광고그룹을 1개만 골랐을 때 보입니다. 추가는 선택한 광고그룹 모두에 같은 검색어로 등록합니다.</p>}
      <div className="flex flex-wrap items-start gap-2">
        <textarea className={`${inputCls} min-h-16 w-80`} aria-label="추가할 제외검색어" placeholder="추가할 제외검색어 (한 줄에 하나, 쉼표로도 구분)"
          value={text} onChange={(e) => setText(e.target.value)} />
        <Button disabled={busy || !words.length} onClick={add}>{words.length ? `${words.length}개 × 광고그룹 ${groups.length}개 등록 미리보기` : "등록 미리보기"}</Button>
      </div>
    </Card>
  );
}
