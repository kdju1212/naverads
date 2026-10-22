"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { DataStatus } from "@/components/DataStatus";
import { Button, Card, ErrorText, PageTitle } from "@/components/ui";
import { api, Change, downloadBlob, Job } from "@/lib/api";
import { enrichExcel } from "@/lib/changes";
import { useNaverData } from "@/lib/naverData";
import { useApp } from "@/lib/store";

export default function BulkPage() {
  const { ws } = useApp();
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // 엑셀의 ID가 어느 광고주 것인지 보관본으로 찾는다(서버에는 광고 데이터 사본이 없다)
  const data = useNaverData({ all: true });

  const upload = async () => {
    if (!ws || !file) return;
    setBusy(true);
    setError(null);
    const form = new FormData();
    form.append("file", file);
    try {
      const rows = await api<Change[]>(`/workspaces/${ws.id}/bulk-jobs/excel/parse`, { form });
      const job = await api<Job>(`/workspaces/${ws.id}/bulk-jobs`, { body: { source: "EXCEL", changes: enrichExcel(rows, data) } });
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
          <p className="mb-3 text-sm text-muted">
            열: <code>entity_type</code>(campaign·adgroup·keyword·ad), <code>naver_id</code>, <code>field</code>(status·daily_budget·bid_amt), <code>value</code>.
            네이버 ID는 각 목록 화면에서 확인할 수 있습니다.
            키워드 등록은 <code>keyword</code> · 광고그룹 ID · <code>create</code> · <code>키워드|입찰가</code>(입찰가 비우면 70원),
            삭제는 <code>keyword</code> · 키워드 ID · <code>delete</code> · 빈칸.
          </p>
          <Button variant="secondary" onClick={async () => {
            try { downloadBlob(await api<Blob>("/bulk-jobs/excel-template", { raw: true }), "bulk_template.xlsx"); }
            catch (e) { setError((e as Error).message); }
          }}>템플릿 다운로드 (.xlsx)</Button>
        </Card>
        <Card title="2. 업로드 → 미리보기">
          <div className="flex flex-wrap items-center gap-3">
            <input type="file" accept=".xlsx" aria-label="엑셀 파일" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="text-sm" />
            <Button disabled={!file || busy || data.loading} onClick={upload}>{busy ? "검증 중…" : data.loading ? "광고 데이터 받는 중…" : "업로드하고 미리보기"}</Button>
          </div>
          <p className="mt-2 text-xs text-faint">업로드만으로는 아무것도 변경되지 않습니다. 다음 화면에서 광고주별 변경 전·후와 오류를 확인한 뒤 실행하세요.</p>
          <div className="mt-3"><DataStatus data={data} /><ErrorText error={error} /></div>
        </Card>
      </div>
    </>
  );
}
