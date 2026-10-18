"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Badge, Button, Card, ErrorText, PageTitle } from "@/components/ui";
import { api, downloadCsv, ENTITY_LABEL, FIELD_LABEL, fmt, Job } from "@/lib/api";
import { useApp } from "@/lib/store";
import { useFetch } from "@/lib/useFetch";

const SOURCE: Record<string, string> = { UI: "화면", EXCEL: "엑셀", RETRY: "재실행" };
const value = (field: string, v: string | null) => (v == null ? "-" : field === "status" ? v : fmt(Number(v), "원"));

export default function JobsPage() {
  // 정적 내보내기에서 useSearchParams는 Suspense 경계가 필요하다
  return <Suspense><JobsRouter /></Suspense>;
}

function JobsRouter() {
  const id = useSearchParams().get("id");
  return id ? <JobDetail key={id} id={id} /> : <JobList />;
}

function JobList() {
  const { ws } = useApp();
  const { data, error, loading } = useFetch<Job[]>(ws && `/workspaces/${ws.id}/bulk-jobs`);
  return (
    <>
      <PageTitle desc="대량 작업의 미리보기·실행 결과. 실패한 행만 다시 실행할 수 있습니다.">작업 결과</PageTitle>
      <ErrorText error={error} />
      <Card>
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-gray-500"><tr><th className="py-2">작업</th><th>출처</th><th>상태</th><th>생성</th><th>실행</th></tr></thead>
          <tbody>
            {(data ?? []).map((j) => (
              <tr key={j.id} className="border-t border-gray-100">
                <td className="py-2"><Link prefetch={false} href={`/jobs?id=${j.id}`} className="font-medium text-emerald-700 hover:underline">#{j.id}</Link>{j.parent_job_id && <span className="ml-1 text-xs text-gray-400">(#{j.parent_job_id} 재실행)</span>}</td>
                <td>{SOURCE[j.source] ?? j.source}</td>
                <td><Badge value={j.status} /></td>
                <td className="text-gray-500">{new Date(j.created_at).toLocaleString("ko-KR")}</td>
                <td className="text-gray-500">{j.executed_at ? new Date(j.executed_at).toLocaleString("ko-KR") : "-"}</td>
              </tr>
            ))}
            {!loading && data?.length === 0 && <tr><td colSpan={5} className="py-6 text-center text-gray-400">작업이 없습니다</td></tr>}
          </tbody>
        </table>
      </Card>
    </>
  );
}

function JobDetail({ id }: { id: string }) {
  const { ws } = useApp();
  const router = useRouter();
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (ws) api<Job>(`/workspaces/${ws.id}/bulk-jobs/${id}`).then(setJob, (e) => setError(e.message));
  }, [ws, id]);

  const act = async (path: string, confirmMsg?: string) => {
    if (!ws || (confirmMsg && !confirm(confirmMsg))) return;
    setBusy(true);
    setError(null);
    try {
      const j = await api<Job>(`/workspaces/${ws.id}/bulk-jobs/${id}/${path}`, { method: "POST" });
      if (String(j.id) !== id) router.push(`/jobs?id=${j.id}`); else setJob(j);
    } catch (e) { setError((e as Error).message); }
    setBusy(false);
  };

  if (!job) return <><PageTitle>작업 #{id}</PageTitle><ErrorText error={error} />{!error && <p className="text-gray-400">불러오는 중…</p>}</>;
  const c = job.counts;
  const problemRows = (job.accounts ?? []).flatMap((a) => a.rows.filter((r) => r.status === "FAILED" || r.status === "INVALID").map((r) => [a.name, r.entity_type, r.naver_id, r.field, r.after, r.status, r.error]));

  return (
    <>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Link prefetch={false} href="/jobs" className="text-sm text-gray-500 hover:text-gray-800">← 작업 목록</Link>
        <h1 className="text-lg font-bold">작업 #{job.id}</h1>
        <Badge value={job.status} />
        {job.parent_job_id && <Link prefetch={false} href={`/jobs?id=${job.parent_job_id}`} className="text-xs text-gray-500 underline">원본 #{job.parent_job_id}</Link>}
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-3 rounded-lg border border-gray-200 bg-white p-3 text-sm">
        <span>광고주 <b>{job.accounts?.length ?? 0}</b>개</span>
        {job.status === "PREVIEW" ? (
          <><span>실행 가능 <b className="text-sky-700">{c.VALID}</b>건</span><span>오류 <b className="text-red-700">{c.INVALID}</b>건 (실행되지 않음)</span></>
        ) : (
          <><span>성공 <b className="text-emerald-700">{c.SUCCESS}</b>건</span><span>실패 <b className="text-red-700">{c.FAILED}</b>건</span><span>제외(오류) {c.INVALID}건</span></>
        )}
        <div className="ml-auto flex gap-2">
          {problemRows.length > 0 && (
            <Button variant="secondary" onClick={() => downloadCsv([["광고주", "유형", "네이버ID", "항목", "값", "상태", "사유"], ...problemRows], `job_${job.id}_errors.csv`)}>오류·실패 행 다운로드</Button>
          )}
          {job.status === "PREVIEW" && (
            <Button disabled={busy || c.VALID === 0} onClick={() => act("execute", `광고주 ${job.accounts?.length}개, ${c.VALID}건을 실제로 변경합니다. 실행할까요?`)}>
              {busy ? "실행 중…" : `${c.VALID}건 실행`}
            </Button>
          )}
          {c.FAILED > 0 && <Button variant="danger" disabled={busy} onClick={() => act("retry-failed")}>실패 {c.FAILED}건만 재실행 준비</Button>}
        </div>
      </div>
      <ErrorText error={error} />

      <div className="flex flex-col gap-4">
        {(job.accounts ?? []).map((a) => (
          <Card key={a.ad_account_id ?? "none"} title={a.name ?? "대상 없음 / 권한 없음"} actions={<span className="text-xs text-gray-500">{a.rows.length}건</span>}>
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-gray-500">
                <tr><th className="py-1.5">대상</th><th>네이버 ID</th><th>항목</th><th className="text-right">변경 전</th><th className="text-center">→</th><th>변경 후</th><th>상태</th><th>사유</th></tr>
              </thead>
              <tbody>
                {a.rows.map((r) => (
                  <tr key={r.id} className={`border-t border-gray-100 ${r.status === "INVALID" || r.status === "FAILED" ? "bg-red-50/40" : ""}`}>
                    <td className="py-1.5">{ENTITY_LABEL[r.entity_type] ?? r.entity_type}</td>
                    <td className="font-mono text-xs text-gray-500">{r.naver_id}</td>
                    <td>{FIELD_LABEL[r.field] ?? r.field}</td>
                    <td className="text-right tabular-nums text-gray-500">{value(r.field, r.before)}</td>
                    <td className="text-center text-gray-400">→</td>
                    <td className="font-semibold tabular-nums">{value(r.field, r.after)}</td>
                    <td><Badge value={r.status} /></td>
                    <td className="text-xs text-red-700">{r.error}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        ))}
      </div>
    </>
  );
}
