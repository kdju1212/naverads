"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Badge, Button, Card, ErrorText, PageTitle } from "@/components/ui";
import { api, toast } from "@/lib/api";
import { useApp } from "@/lib/store";
import { useFetch } from "@/lib/useFetch";

interface Approval {
  approval_id: number; tool: string; payload: Record<string, unknown>; status: string; result: Record<string, unknown> | null;
  requested_by: number; created_at: string; expires_at: string; decided_at: string | null;
}

const TOOL: Record<string, string> = {
  create_ad: "소재 등록", create_ad_extension: "확장소재 등록", set_auto_bid: "자동입찰 설정", delete_auto_bid: "자동입찰 해제",
  run_auto_bids: "자동입찰 지금 실행",
};
const FIELD: Record<string, string> = {
  ad_account_id: "광고 계정", adgroup_id: "광고그룹 ID", ad_type: "소재 유형", headlines: "제목", descriptions: "설명", pc_url: "PC URL",
  mobile_url: "모바일 URL", ext_type: "확장소재 유형", heading: "구분·추가제목", description: "설명", links: "링크", keywords: "키워드",
  device: "기기", target_rank: "목표 순위", max_bid: "최대 입찰가", enabled: "사용",
};

function show(key: string, v: unknown, accountName: (id: number) => string): string {
  if (key === "ad_account_id") return accountName(Number(v));
  if (key === "keywords" && Array.isArray(v)) return v.map((k) => `${k.keyword || k.naver_id} (${accountName(Number(k.ad_account_id))})`).join(", ");
  if (key === "max_bid") return `${Number(v).toLocaleString("ko-KR")}원`;
  if (Array.isArray(v)) return v.map((x) => (typeof x === "object" ? `${x.name}: ${x.final}` : String(x))).join(" / ");
  return typeof v === "boolean" ? (v ? "예" : "아니요") : String(v);
}

export default function ApprovalsPage() {
  return <Suspense><Approvals /></Suspense>;
}

/** Claude가 요청한 광고 변경. 여기서 사람이 승인해야 서버가 저장된 내용 그대로 실행한다(Claude는 직접 실행 못 함). */
function Approvals() {
  const { ws, accountName } = useApp();
  const focus = Number(useSearchParams().get("id"));
  const list = useFetch<Approval[]>(ws && `/workspaces/${ws.id}/approvals`);
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const decide = async (a: Approval, decision: "approve" | "reject") => {
    if (!ws) return;
    if (decision === "approve" && !confirm(`${TOOL[a.tool] ?? a.tool}을(를) 실제 광고 계정에 실행합니다. 진행할까요?`)) return;
    setBusy(a.approval_id);
    setError(null);
    try {
      const out = await api<Approval>(`/workspaces/${ws.id}/approvals/${a.approval_id}/${decision}`, { method: "POST" });
      toast(out.status === "DONE" ? "승인해서 실행했습니다" : out.status === "REJECTED" ? "거절했습니다" : "실행하지 못했습니다");
      await list.reload();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const rows = list.data ?? [];
  return (
    <>
      <PageTitle desc="Claude가 요청한 광고 변경입니다. 내용을 확인하고 승인해야 실행됩니다. 요청은 30분이 지나면 만료됩니다. 입찰가·상태 변경 작업은 '작업 결과'에서 실행합니다.">
        승인 대기
      </PageTitle>
      <ErrorText error={error ?? list.error} />
      {list.loading ? <p className="text-sm text-faint">불러오는 중…</p> : rows.length === 0 ? (
        <Card><p className="p-4 text-sm text-faint">승인할 요청이 없습니다</p></Card>
      ) : (
        <div className="flex flex-col gap-3">
          {rows.map((a) => (
            <Card key={a.approval_id} className={a.approval_id === focus ? "ring-2 ring-primary" : ""}
              title={<span className="flex items-center gap-2">#{a.approval_id} {TOOL[a.tool] ?? a.tool} <Badge value={a.status} /></span>}
              actions={a.status === "PENDING" && (
                <div className="flex gap-2">
                  <Button variant="secondary" disabled={busy !== null} onClick={() => decide(a, "reject")}>거절</Button>
                  <Button disabled={busy !== null} onClick={() => decide(a, "approve")}>{busy === a.approval_id ? "실행 중…" : "승인하고 실행"}</Button>
                </div>
              )}>
              <dl className="grid grid-cols-[8rem_1fr] gap-x-3 gap-y-1 p-4 text-sm">
                {Object.entries(a.payload).map(([k, v]) => (
                  <div key={k} className="contents"><dt className="text-faint">{FIELD[k] ?? k}</dt><dd className="break-all">{show(k, v, accountName)}</dd></div>
                ))}
                <dt className="text-faint">요청</dt>
                <dd>{new Date(a.created_at).toLocaleString("ko-KR")} · 만료 {new Date(a.expires_at).toLocaleTimeString("ko-KR")}</dd>
                {a.result && <><dt className="text-faint">결과</dt><dd className="break-all">{"error" in a.result ? String(a.result.error) : "실행됨"}</dd></>}
              </dl>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
