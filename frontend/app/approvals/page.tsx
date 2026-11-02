"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Button, Card, ErrorText, PageTitle } from "@/components/ui";
import { api, ENTITY_LABEL, FIELD_LABEL, fmt, Job, SafetyCheck, toast } from "@/lib/api";
import { applyJob } from "@/lib/naverData";
import { useApp } from "@/lib/store";
import { useFetch } from "@/lib/useFetch";

/** 서버: backend/src/app/approvals.py. 계정 하루예산 합계가 늘 수 있는 변경(예산 올리기·캠페인/광고그룹 켜기·ADVoost 켜기)만 여기서 승인한다 */
interface JobRowSummary { account: string | null; entity_type: string; naver_id: string; what: string; before: string | null; after: string; claimed_before?: string | null }
interface Approval {
  approval_id: number; kind: "job" | "place"; status: string; job_id: number | null; ad_account_id: number | null;
  created_at: string; expires_at: string; decided_at: string | null;
  summary: {
    title?: string; why?: string; rows?: JobRowSummary[]; more_rows?: number; safety?: SafetyCheck[] | SafetyCheck; note?: string;
    label?: string; target?: string; before?: string; after?: string; spend_text?: string; notes?: string[];
  } | null;
  result: { job_status?: string; steps?: { step: string; ok: boolean; error?: string }[]; error?: string | null } | null;
}

const STATUS: Record<string, [string, string]> = {
  PENDING: ["승인 기다리는 중", "text-warning"], APPROVED: ["승인함 · 예약 시각에 실행", "text-info"], RUNNING: ["실행 중", "text-info"],
  DONE: ["실행 완료", "text-accent"], PARTIAL: ["일부만 실행됨", "text-warning"], FAILED: ["실행하지 못함", "text-danger"],
  REJECTED: ["거절함", "text-faint"], EXPIRED: ["시간이 지나 무효", "text-faint"],
};
const when = (v: string) => new Date(v.endsWith("Z") || v.includes("+") ? v : v + "Z").toLocaleString("ko-KR");
const money = (what: string, v: string | null) => (v && /^\d+$/.test(v) && what !== "상태" ? fmt(Number(v), "원") : v ?? "-");

export default function ApprovalsPage() {
  return <Suspense><Approvals /></Suspense>; // 정적 내보내기에서 useSearchParams는 Suspense 경계가 필요하다
}

function Approvals() {
  const { ws } = useApp();
  const focus = Number(useSearchParams().get("id")) || null;
  const { data, error, reload } = useFetch<Approval[]>(ws && `/workspaces/${ws.id}/approvals`);
  const list = data ?? [];
  const open = list.filter((a) => a.status === "PENDING" || a.approval_id === focus);
  const done = list.filter((a) => !open.includes(a));
  return (
    <>
      <PageTitle desc="캠페인 하루예산 올리기, 캠페인·광고그룹 켜기, ADVoost 켜기는 돈이 새로 나가기 시작할 수 있어 여기서 직접 승인해야 실행돼요. Claude는 요청만 만들 수 있어요.">
        승인
      </PageTitle>
      <ErrorText error={error} />
      {!open.length && <p className="mb-4 text-sm text-faint">승인을 기다리는 요청이 없어요.</p>}
      {open.map((a) => <ApprovalCard key={a.approval_id} a={a} onChange={reload} />)}
      {!!done.length && (
        <Card title="최근 결과">
          <ul className="divide-y divide-line text-sm">
            {done.map((a) => (
              <li key={a.approval_id} className="flex flex-wrap items-center gap-3 py-2">
                <span className="text-faint">#{a.approval_id}</span>
                <span>{a.summary?.title ?? a.summary?.label ?? "변경"}{a.summary?.target ? ` · ${a.summary.target}` : ""}</span>
                <span className={STATUS[a.status]?.[1]}>{STATUS[a.status]?.[0] ?? a.status}</span>
                {a.job_id && <Link className="text-primary hover:underline" href={`/jobs?id=${a.job_id}`}>작업 #{a.job_id}</Link>}
                <span className="text-xs text-faint">{when(a.created_at)}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </>
  );
}

function ApprovalCard({ a, onChange }: { a: Approval; onChange: () => void }) {
  const { ws, accountName } = useApp();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const s = a.summary ?? {};
  const safety = Array.isArray(s.safety) ? s.safety : s.safety ? [s.safety] : [];
  const pending = a.status === "PENDING";
  // 100건이 넘는 작업은 전체 행을 펼쳐 본 뒤에만 승인할 수 있다(실행되는 행 = 이 작업의 행, 서버가 해시로 묶음)
  const [allRows, setAllRows] = useState<JobRowSummary[] | null>(null);
  const showAll = async () => {
    if (!ws || !a.job_id) return;
    try {
      const j = await api<Job>(`/workspaces/${ws.id}/bulk-jobs/${a.job_id}`);
      setAllRows((j.accounts ?? []).flatMap((acc) => acc.rows.filter((r) => r.status === "VALID" || !pending).map((r) => ({
        account: acc.name, entity_type: r.entity_type, naver_id: r.naver_id, what: FIELD_LABEL[r.field] ?? r.field, before: r.before, after: r.after }))));
    } catch (e) { setError((e as Error).message); }
  };
  const rows = allRows ?? s.rows;
  const mustExpand = pending && !!s.more_rows && !allRows;

  const approve = async () => {
    if (!ws || !confirm("이 변경을 승인하고 바로 실행할까요? (예약 작업은 예약 시각에 실행돼요)")) return;
    setBusy(true);
    setError(null);
    try {
      const r = await api<{ status: string; job?: Job; place?: { status: string } }>(`/workspaces/${ws.id}/approvals/${a.approval_id}/approve`, { method: "POST" });
      let j = r.job;
      // 큰 작업은 서버가 몇 건씩 나눠 실행한다(무료 플랜 요청당 호출 한도) → 남은 건을 이어서 요청
      while (j && j.status === "RUNNING") j = await api<Job>(`/workspaces/${ws.id}/bulk-jobs/${j.id}/execute`, { method: "POST" });
      if (j) {
        await applyJob(ws.id, j);
        toast(`작업 #${j.id}: 성공 ${j.counts.SUCCESS}건${j.counts.FAILED ? `, 실패 ${j.counts.FAILED}건(이유는 작업 결과에서)` : ""}`);
      }
    } catch (e) { setError((e as Error).message); }
    setBusy(false);
    onChange();
  };
  const reject = async () => {
    if (!ws) return;
    setBusy(true);
    try { await api(`/workspaces/${ws.id}/approvals/${a.approval_id}/reject`, { method: "POST" }); } catch (e) { setError((e as Error).message); }
    setBusy(false);
    onChange();
  };

  return (
    <Card title={`#${a.approval_id} ${s.title ?? s.label ?? "변경 승인"}`} className="mb-4">
      <p className={`mb-2 text-sm font-semibold ${STATUS[a.status]?.[1] ?? ""}`}>{STATUS[a.status]?.[0] ?? a.status}</p>
      {s.why && <p className="mb-2 text-sm">{s.why}</p>}
      {a.ad_account_id && <p className="mb-2 text-sm">광고 계정: <strong>{accountName(a.ad_account_id)}</strong></p>}
      {rows && (
        <div className="mb-2 overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="text-left text-muted"><th className="pr-3">광고 계정</th><th className="pr-3">대상</th><th className="pr-3">항목</th><th className="pr-3">지금</th><th>바뀐 뒤</th></tr></thead>
            <tbody>{rows.map((r, i) => (
              <tr key={`${r.naver_id}-${r.what}-${i}`} className="border-t border-line">
                <td className="pr-3">{r.account ?? "-"}</td><td className="pr-3">{ENTITY_LABEL[r.entity_type] ?? r.entity_type} {r.naver_id}</td>
                <td className="pr-3">{r.what}</td>
                <td className="pr-3">{money(r.what, r.before)}
                  {r.claimed_before != null && <span className="block text-xs text-warning">요청에 적힌 값 {money(r.what, r.claimed_before)}와 달라요(네이버 기준으로 실행)</span>}</td>
                <td className="font-medium">{money(r.what, r.after)}</td>
              </tr>))}</tbody>
          </table>
          {!!s.more_rows && !allRows && (
            <Button variant="secondary" className="mt-2" onClick={showAll}>전체 {(s.rows?.length ?? 0) + s.more_rows}건 펼쳐 보기</Button>
          )}
        </div>
      )}
      {s.target && (
        <table className="mb-2 text-sm"><tbody>
          {([["대상", s.target], ["지금", s.before], ["바뀐 뒤", s.after], ["지출", s.spend_text]] as const).map(([k, v]) => (
            <tr key={k}><th className="pr-4 text-left font-medium text-muted">{k}</th><td>{v}</td></tr>))}
        </tbody></table>
      )}
      {safety.map((x, i) => (
        <div key={i} className="mb-2 rounded-control bg-line/30 px-3 py-2 text-sm">
          {x.ok === false ? <p className="text-danger">지금 네이버 설정으로는 실행되지 않아요: {x.reason}</p> : <>
            {x.total_after != null && <p>변경 후 켜진 캠페인 하루예산 설정액 합계 <strong>{fmt(x.total_after, "원")}</strong>
              {x.daily_budget_limit != null && <> (관리 기준 {fmt(x.daily_budget_limit, "원")})</>}</p>}
            {x.max_bid != null && <p>이 계정의 클릭당 최대 입찰가 {fmt(x.max_bid, "원")}</p>}
            {x.uncontrolled?.map((n) => <p key={n} className="text-warning">· {n}</p>)}
          </>}
        </div>
      ))}
      {s.notes?.map((n) => <p key={n} className="text-xs text-faint">· {n}</p>)}
      <p className="mt-1 text-xs text-muted">{s.note ?? "하루예산 설정액은 실제 과금의 절대 상한이 아니에요. 네이버가 광고를 멈추는 데 시간이 걸려 설정액보다 조금 더 과금될 수 있어요."}</p>
      <p className="text-xs text-faint">승인하면 실행 직전에 권한과 네이버의 지금 값을 다시 확인해요. 그사이 값이 바뀌었거나 안전장치에 걸리면 실행하지 않아요.
        {pending && <> 이 요청은 {when(a.expires_at)}까지, 한 번만 승인할 수 있어요.</>}</p>
      {a.result?.error && <p className="mt-2 text-sm text-danger">{a.result.error}</p>}
      {a.result?.steps?.map((x) => <p key={x.step} className="text-sm">{x.ok ? "✓" : "✗"} {x.step}{x.error && <span className="text-danger"> — {x.error}</span>}</p>)}
      {a.job_id && !pending && <Link className="mt-2 inline-block text-sm text-primary hover:underline" href={`/jobs?id=${a.job_id}`}>작업 #{a.job_id} 결과 보기</Link>}
      <ErrorText error={error} />
      {pending && (
        <div className="mt-3 flex gap-2">
          <Button disabled={busy || mustExpand} onClick={approve} title={mustExpand ? "전체 항목을 펼쳐 본 뒤 승인할 수 있어요" : undefined}>
            {busy ? "실행 중…" : "승인하고 실행"}</Button>
          <Button variant="secondary" disabled={busy} onClick={reject}>거절</Button>
        </div>
      )}
    </Card>
  );
}
