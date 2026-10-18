"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, Card, ErrorText, PageTitle } from "@/components/ui";
import { api, downloadBlob, Job } from "@/lib/api";
import { useApp } from "@/lib/store";

export default function BulkPage() {
  const { ws } = useApp();
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const upload = async () => {
    if (!ws || !file) return;
    setBusy(true);
    setError(null);
    const form = new FormData();
    form.append("file", file);
    try {
      const job = await api<Job>(`/workspaces/${ws.id}/bulk-jobs/excel`, { form });
      router.push(`/jobs?id=${job.id}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  };

  return (
    <>
      <PageTitle desc="여러 광고주 계정의 변경을 엑셀 한 장으로 올리고, 미리보기에서 확인한 뒤 실행합니다.">엑셀 대량 작업</PageTitle>
      <div className="grid max-w-3xl gap-4">
        <Card title="1. 템플릿 받기">
          <p className="mb-3 text-sm text-gray-600">
            열: <code>entity_type</code>(campaign·adgroup·keyword·ad), <code>naver_id</code>, <code>field</code>(status·daily_budget·bid_amt), <code>value</code>.
            네이버 ID는 각 목록 화면에서 확인할 수 있습니다.
          </p>
          <Button variant="secondary" onClick={async () => {
            try { downloadBlob(await api<Blob>("/bulk-jobs/excel-template", { raw: true }), "bulk_template.xlsx"); }
            catch (e) { setError((e as Error).message); }
          }}>템플릿 다운로드 (.xlsx)</Button>
        </Card>
        <Card title="2. 업로드 → 미리보기">
          <div className="flex flex-wrap items-center gap-3">
            <input type="file" accept=".xlsx" aria-label="엑셀 파일" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="text-sm" />
            <Button disabled={!file || busy} onClick={upload}>{busy ? "검증 중…" : "업로드하고 미리보기"}</Button>
          </div>
          <p className="mt-2 text-xs text-gray-500">업로드만으로는 아무것도 변경되지 않습니다. 다음 화면에서 광고주별 변경 전·후와 오류를 확인한 뒤 실행하세요.</p>
          <div className="mt-3"><ErrorText error={error} /></div>
        </Card>
      </div>
    </>
  );
}
