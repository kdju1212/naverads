"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Col, DataTable } from "@/components/DataTable";
import { ErrorText, inputCls, PageTitle } from "@/components/ui";
import { ENTITY_LABEL, FIELD_LABEL } from "@/lib/api";
import { useApp } from "@/lib/store";
import { useFetch } from "@/lib/useFetch";

interface Log {
  id: number; user_id: number; ad_account_id: number | null; job_id: number | null; action: string;
  entity_type: string | null; naver_id: string | null; field: string | null; before: string | null; after: string | null; created_at: string;
}
interface Member { user_id: number; name: string; email: string }

const ACTION: Record<string, string> = { UPDATE: "변경", CREATE: "생성", DELETE: "삭제", ACCOUNT_CONNECT: "계정 연결", ACCOUNT_DISCONNECT: "계정 해제", ACCESS_SET: "권한 배정", AUTO_BID_SET: "자동입찰 설정", AUTO_BID_DELETE: "자동입찰 해제" };

export default function HistoryPage() {
  const { ws, selected, accountName } = useApp();
  const [userId, setUserId] = useState("");
  const logs = useFetch<Log[]>(ws && `/workspaces/${ws.id}/audit-logs${userId ? `?user_id=${userId}` : ""}`);
  const members = useFetch<Member[]>(ws && `/workspaces/${ws.id}/members`);
  const userName = useMemo(() => new Map((members.data ?? []).map((m) => [m.user_id, m.name])), [members.data]);
  const rows = useMemo(() => (logs.data ?? []).filter((l) => !selected.length || (l.ad_account_id != null && selected.includes(l.ad_account_id))), [logs.data, selected]);

  const cols: Col<Log>[] = [
    { key: "at", label: "시각", value: (r) => r.created_at, render: (r) => new Date(r.created_at).toLocaleString("ko-KR") },
    { key: "user", label: "담당자", value: (r) => userName.get(r.user_id) ?? `#${r.user_id}` },
    { key: "acc", label: "광고주", value: (r) => accountName(r.ad_account_id) },
    { key: "action", label: "작업", value: (r) => ACTION[r.action] ?? r.action },
    { key: "target", label: "대상", value: (r) => (r.entity_type ? `${ENTITY_LABEL[r.entity_type] ?? r.entity_type} ${r.naver_id}` : null) },
    { key: "field", label: "항목", value: (r) => (r.field ? FIELD_LABEL[r.field] ?? r.field : null) },
    { key: "change", label: "변경 전 → 후", value: (r) => `${r.before ?? "-"} → ${r.after ?? "-"}` },
    { key: "job", label: "작업 ID", value: (r) => r.job_id, render: (r) => (r.job_id ? <Link prefetch={false} className="text-emerald-700 hover:underline" href={`/jobs?id=${r.job_id}`}>#{r.job_id}</Link> : "-") },
  ];
  return (
    <>
      <PageTitle desc="누가 언제 어느 광고주의 무엇을 바꿨는지 기록합니다. 상단에서 선택한 광고 계정 기준으로 표시됩니다.">변경 이력</PageTitle>
      <ErrorText error={logs.error} />
      <DataTable rows={rows} cols={cols} loading={logs.loading} empty="기록이 없습니다"
        toolbar={
          <select className={inputCls} value={userId} onChange={(e) => setUserId(e.target.value)} aria-label="담당자 필터">
            <option value="">전체 담당자</option>
            {(members.data ?? []).map((m) => <option key={m.user_id} value={m.user_id}>{m.name} ({m.email})</option>)}
          </select>
        } />
    </>
  );
}
