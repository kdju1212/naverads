"use client";

import { useState } from "react";
import { Button, ErrorText, inputCls } from "@/components/ui";
import { api, fmt } from "@/lib/api";
import { useApp } from "@/lib/store";
import { useFetch } from "@/lib/useFetch";

// 서버: backend/src/app/safety.py · 문서: docs/AD_SAFETY_AND_APPROVALS.md
type Status = {
  configured: boolean; claude_direct: boolean; daily_budget_limit: number | null; max_bid: number | null; set_at: string | null; note: string;
  total: number | null; campaigns: { id: string; name: string; type: string; daily_budget: number; from: string }[];
  problems: string[]; needs_action: boolean; actions: string[];
};
const digits = (v: string) => v.replace(/[^0-9]/g, "");

/** 광고 계정 하나의 광고비 안전장치: 네이버 지금 하루예산 설정액 현황을 보여 주고, 관리자가 금액을 직접 정해 확인한다(미리 채우지 않음). */
export function SafetyPanel({ accountId, isAdmin, onSaved }: { accountId: number; isAdmin: boolean; onSaved: () => void }) {
  const { ws } = useApp();
  const st = useFetch<Status>(ws && `/workspaces/${ws.id}/ad-accounts/${accountId}/safety`);
  const [form, setForm] = useState({ limit: "", bid: "", ok: false });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const s = st.data;

  const save = async () => {
    if (!ws) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/workspaces/${ws.id}/ad-accounts/${accountId}/safety`, {
        method: "PUT", body: { daily_budget_limit: Number(form.limit), max_bid: Number(form.bid), confirmed: form.ok },
      });
      setForm({ limit: "", bid: "", ok: false });
      await st.reload();
      onSaved();
    } catch (e) { setError((e as Error).message); }
    setBusy(false);
  };

  const setDirect = async (on: boolean) => {
    if (!ws) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/workspaces/${ws.id}/ad-accounts/${accountId}/safety/claude-direct`, { method: "PUT", body: { on } });
      await st.reload();
    } catch (e) { setError((e as Error).message); }
    setBusy(false);
  };

  if (!s) return <div className="p-3 text-sm text-faint">{st.error ?? "네이버에서 지금 예산 설정을 읽는 중…"}</div>;
  return (
    <div className="grid gap-3 bg-subtle p-3 text-sm">
      <ErrorText error={error ?? st.error} />
      <div>
        <b>지금 켜진 캠페인의 하루예산 설정액</b>
        <span className="ml-2">합계 {s.total == null ? <span className="text-danger">계산할 수 없음</span> : `${fmt(s.total)}원`}</span>
        <ul className="mt-1 text-xs text-muted">
          {s.campaigns.map((c) => <li key={c.id}>{c.name}: {fmt(c.daily_budget)}원{c.from === "adgroups" ? " (캠페인 예산이 없어 광고그룹 예산 합)" : ""}</li>)}
          {!s.campaigns.length && <li>켜진 캠페인이 없어요</li>}
        </ul>
        {s.problems.map((p) => <p key={p} className="text-xs text-danger">· {p}</p>)}
      </div>
      <p className="text-xs text-faint">{s.note} 그래서 아래 금액은 &apos;하루예산 설정액&apos;을 관리하는 기준이에요.</p>
      {s.configured
        ? <p>관리 기준: 하루예산 설정액 합계 <b>{fmt(s.daily_budget_limit)}원</b> 이하 · 클릭당 최대 입찰가 <b>{fmt(s.max_bid)}원</b>
            {s.set_at && <span className="text-xs text-faint"> ({new Date(s.set_at).toLocaleString("ko-KR")} 설정)</span>}</p>
        : <p className="text-warning">아직 정하지 않았어요. 정하기 전에는 광고 켜기·예산 올리기·입찰가 바꾸기가 막혀요(끄기·조회는 돼요).</p>}
      {s.configured && (
        <div className="grid gap-1">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={s.claude_direct} disabled={!isAdmin || busy} onChange={(e) => setDirect(e.target.checked)} />
            <b>Claude에서 바로 실행</b>
          </label>
          <p className="text-xs text-muted">켜면 이 계정의 캠페인 켜기·하루예산 올리기·ADVoost 켜기도 웹 승인 없이 Claude 화면의 허용 버튼으로 실행돼요.
            위 관리 기준·최대 입찰가 검사는 그대로예요. 끄면 다시 웹에서 승인해야 해요.</p>
        </div>
      )}
      {s.actions.length > 0 && <ul className="text-xs text-warning">{s.actions.map((a) => <li key={a}>→ {a}</li>)}</ul>}
      {isAdmin ? (
        <form className="grid gap-2" onSubmit={(e) => { e.preventDefault(); save(); }}>
          <label className="grid gap-1">하루예산 관리 기준 (켜진 캠페인 하루예산 설정액 합계가 이 금액을 넘으면 켜기·증액을 막아요)
            <input className={`${inputCls} w-48`} inputMode="numeric" placeholder="예: 30000" value={form.limit} onChange={(e) => setForm({ ...form, limit: digits(e.target.value) })} required />
          </label>
          <label className="grid gap-1">클릭당 최대 입찰가 (광고를 한 번 누를 때 낼 수 있는 최대 금액)
            <input className={`${inputCls} w-48`} inputMode="numeric" placeholder="예: 500" value={form.bid} onChange={(e) => setForm({ ...form, bid: digits(e.target.value) })} required />
          </label>
          {form.limit && <p className="text-xs text-muted">하루 {fmt(Number(form.limit))}원 × 31일 = 한 달 하루예산 설정액 최대 약 {fmt(Number(form.limit) * 31)}원 (실제 과금은 조금 더 나올 수 있어요)</p>}
          <label className="flex items-center gap-2"><input type="checkbox" checked={form.ok} onChange={(e) => setForm({ ...form, ok: e.target.checked })} />
            위 현황과 금액을 확인했어요</label>
          <Button type="submit" disabled={busy || !form.ok || !form.limit || !form.bid}>{s.configured ? "바꾸기" : "정하기"}</Button>
        </form>
      ) : <p className="text-xs text-faint">금액은 관리자가 정해요.</p>}
    </div>
  );
}
