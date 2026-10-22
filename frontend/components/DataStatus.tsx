"use client";

import { useApp } from "@/lib/store";
import { Button } from "./ui";

/** 브라우저 보관본 상태: 받은 시각, 받는 중, 계정별 오류, 새로고침(네이버에서 다시 받기). */
export function DataStatus({ data }: {
  data: { loading: boolean; errors: { ad_account_id: number; error: string }[]; fetchedAt: number; refresh: () => Promise<unknown> };
}) {
  const { accountName } = useApp();
  return (
    <div className="mb-3 flex flex-col gap-1">
      <div className="flex flex-wrap items-center gap-2 text-xs text-faint">
        {data.loading ? <span>네이버에서 받는 중… (계정이 크면 1분 이상 걸릴 수 있습니다)</span>
          : Number.isFinite(data.fetchedAt) && <span>{new Date(data.fetchedAt).toLocaleString("ko-KR")} 기준 · 이 브라우저에 보관</span>}
        <Button variant="secondary" disabled={data.loading} onClick={() => data.refresh()}>새로고침</Button>
      </div>
      {data.errors.map((e) => (
        <p key={e.ad_account_id} role="alert" className="rounded-control bg-danger-soft px-3 py-1.5 text-sm text-danger">
          {accountName(e.ad_account_id)}: {e.error}
        </p>
      ))}
    </div>
  );
}
