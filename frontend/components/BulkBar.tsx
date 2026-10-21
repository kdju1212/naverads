"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, Job } from "@/lib/api";
import { changeFor, Target } from "@/lib/changes";
import { useApp } from "@/lib/store";
import { Button, inputCls } from "./ui";

/** 선택한 행에 같은 변경을 적용하는 대량 작업을 만들고 미리보기 화면으로 이동한다. 즉시 반영하지 않는다. */
export function BulkBar({ entityType, rows, numberField, deletable }: {
  entityType: string;
  rows: Target[];
  numberField?: { field: "daily_budget" | "bid_amt"; label: string };
  deletable?: boolean;
}) {
  const { ws } = useApp();
  const router = useRouter();
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const create = async (field: string, v: string) => {
    if (!ws || rows.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      const changes = rows.map((r) => changeFor(entityType, r, field, v));
      const job = await api<Job>(`/workspaces/${ws.id}/bulk-jobs`, { body: { changes } });
      router.push(`/jobs?id=${job.id}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  };

  const disabled = busy || rows.length === 0;
  return (
    <div className="flex flex-wrap items-center gap-2">
      {error && <span role="alert" className="text-xs text-red-600">{error}</span>}
      <Button variant="secondary" disabled={disabled} onClick={() => create("status", "ON")}>ON</Button>
      <Button variant="secondary" disabled={disabled} onClick={() => create("status", "OFF")}>OFF</Button>
      {numberField && (
        <>
          <input className={`${inputCls} w-28`} inputMode="numeric" placeholder={`${numberField.label}(원)`} aria-label={numberField.label}
            value={value} onChange={(e) => setValue(e.target.value.replace(/[^0-9]/g, ""))} />
          <Button disabled={disabled || !value} onClick={() => create(numberField.field, value)}>{numberField.label} 변경</Button>
        </>
      )}
      {deletable && <Button variant="danger" disabled={disabled} onClick={() => create("delete", "")}>삭제</Button>}
    </div>
  );
}
