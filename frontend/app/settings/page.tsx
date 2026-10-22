"use client";

import { useState } from "react";
import { Badge, Button, Card, ErrorText, inputCls, PageTitle } from "@/components/ui";
import { api, fmt } from "@/lib/api";
import { refreshAccounts } from "@/lib/naverData";
import { useApp } from "@/lib/store";
import { useFetch } from "@/lib/useFetch";

interface Member { membership_id: number; user_id: number; email: string; name: string; role: string; access: { ad_account_id: number; level: "VIEW" | "EDIT" }[] }
interface Sub { plan: string; status: string; trial_ends_at: string | null; billable_accounts: number; price_per_account: number; monthly_total: number }

export default function SettingsPage() {
  const { ws, accounts } = useApp();
  const isAdmin = ws?.role === "OWNER" || ws?.role === "ADMIN";
  return (
    <>
      <PageTitle desc={isAdmin ? "광고 계정 연결, 직원과 담당 계정 배정, 구독 정보" : "계정 연결·직원 관리는 관리자만 할 수 있습니다."}>설정</PageTitle>
      <div className="flex flex-col gap-4">
        <Accounts isAdmin={isAdmin} />
        {isAdmin && <Members />}
        {/* 계정 연결·해제 시 과금 계정 수를 다시 불러온다 */}
        {isAdmin && <Subscription key={accounts.length} />}
      </div>
    </>
  );
}

function useAction() {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try { await fn(); } catch (e) { setError((e as Error).message); }
    setBusy(false);
  };
  return { error, busy, run };
}

function Accounts({ isAdmin }: { isAdmin: boolean }) {
  const { ws, accounts, reloadAccounts } = useApp();
  const creds = useFetch<{ id: number; label: string; is_mock: boolean }[]>(ws && isAdmin ? `/workspaces/${ws.id}/credentials` : null);
  const credList = creds.data ?? [];
  const [cred, setCred] = useState({ label: "Mock 테스트", api_key: "", secret_key: "", is_mock: true });
  const [acc, setAcc] = useState({ credential_id: "", customer_id: "", name: "" });
  const [syncing, setSyncing] = useState<number | null>(null);
  const { error, busy, run } = useAction();

  const doSync = async (id: number) => {
    setSyncing(id);
    try {
      const r = await api<{ status: string; error: string | null }>(`/workspaces/${ws!.id}/ad-accounts/${id}/sync`, { method: "POST" });
      if (r.status === "FAILED") throw new Error(`동기화 실패: ${r.error}`);
      await refreshAccounts(ws!.id, [id]); // 광고 데이터는 브라우저 보관본을 새로 받는다(서버는 성과 통계만)
    } finally {
      setSyncing(null);
      await reloadAccounts();
    }
  };
  const sync = (id: number) => run(() => doSync(id));

  return (
    <Card title="광고 계정">
      <ErrorText error={error} />
      <table className="mb-4 w-full text-sm">
        <thead className="text-left text-xs text-faint"><tr><th className="py-2">광고주</th><th>CUSTOMER_ID</th><th>구분</th><th>마지막 동기화</th><th /></tr></thead>
        <tbody>
          {accounts.map((a) => (
            <tr key={a.id} className="border-t border-line">
              <td className="py-2 font-medium">{a.name}</td>
              <td className="font-mono text-xs">{a.customer_id}</td>
              <td>{a.is_mock ? "Mock" : "실계정"}</td>
              <td>{a.last_sync ? <><Badge value={a.last_sync.status} /> <span className="text-xs text-faint">{a.last_sync.at && new Date(a.last_sync.at).toLocaleString("ko-KR")}</span>{a.last_sync.error && <div className="text-xs text-danger">{a.last_sync.error}</div>}</> : <span className="text-xs text-warning">동기화 필요</span>}</td>
              <td className="text-right">
                <div className="flex justify-end gap-2">
                  <Button variant="secondary" disabled={busy} onClick={() => sync(a.id)}>{syncing === a.id ? "동기화 중…" : "동기화"}</Button>
                  {isAdmin && <Button variant="danger" disabled={busy} onClick={() => confirm(`${a.name} 연결을 해제할까요? 데이터와 이력은 보존되고 접근만 차단됩니다.`) && run(async () => {
                    await api(`/workspaces/${ws!.id}/ad-accounts/${a.id}`, { method: "DELETE" });
                    await reloadAccounts();
                  })}>해제</Button>}
                </div>
              </td>
            </tr>
          ))}
          {accounts.length === 0 && <tr><td colSpan={5} className="py-4 text-center text-faint">연결된 광고 계정이 없습니다</td></tr>}
        </tbody>
      </table>

      {isAdmin && (
        <div className="grid gap-4 border-t border-line pt-4 lg:grid-cols-2">
          <form className="flex flex-col gap-2" onSubmit={(e) => { e.preventDefault(); run(async () => {
            const r = await api<{ id: number; label: string; is_mock: boolean }>(`/workspaces/${ws!.id}/credentials`, { body: cred });
            await creds.reload();
            setAcc((a) => ({ ...a, credential_id: String(r.id) }));
            setCred({ ...cred, api_key: "", secret_key: "" });
          }); }}>
            <h3 className="text-[15px] font-semibold">① 네이버 검색광고 API 자격증명 등록</h3>
            <input className={inputCls} placeholder="이름 (예: 대행사 마스터 API)" value={cred.label} onChange={(e) => setCred({ ...cred, label: e.target.value })} required aria-label="자격증명 이름" />
            <input className={inputCls} placeholder="API Key (액세스 라이선스)" value={cred.api_key} onChange={(e) => setCred({ ...cred, api_key: e.target.value })} required aria-label="API Key" />
            <input className={inputCls} type="password" placeholder="Secret Key (저장 후 다시 표시되지 않음)" value={cred.secret_key} onChange={(e) => setCred({ ...cred, secret_key: e.target.value })} required aria-label="Secret Key" autoComplete="off" />
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={cred.is_mock} onChange={(e) => setCred({ ...cred, is_mock: e.target.checked })} /> Mock 모드 (가짜 데이터, 실계정 연동은 API 검증 후)</label>
            <Button type="submit" disabled={busy}>자격증명 등록</Button>
          </form>

          <form className="flex flex-col gap-2" onSubmit={(e) => { e.preventDefault(); run(async () => {
            const r = await api<{ id: number }>(`/workspaces/${ws!.id}/ad-accounts`, { body: { ...acc, credential_id: Number(acc.credential_id) } });
            setAcc({ ...acc, customer_id: "", name: "" });
            await reloadAccounts();
            await doSync(r.id);
          }); }}>
            <h3 className="text-[15px] font-semibold">② 광고 계정 연결</h3>
            <select className={inputCls} value={acc.credential_id} onChange={(e) => setAcc({ ...acc, credential_id: e.target.value })} required aria-label="자격증명">
              <option value="">자격증명 선택</option>
              {credList.map((c) => <option key={c.id} value={c.id}>{c.label}{c.is_mock ? " (Mock)" : ""}</option>)}
            </select>
            {credList.length === 0 && <p className="text-xs text-faint">먼저 ①에서 자격증명을 등록하세요.</p>}
            <input className={inputCls} placeholder="CUSTOMER_ID (숫자)" inputMode="numeric" value={acc.customer_id} onChange={(e) => setAcc({ ...acc, customer_id: e.target.value.trim() })} required aria-label="CUSTOMER_ID" />
            <input className={inputCls} placeholder="광고주 이름" value={acc.name} onChange={(e) => setAcc({ ...acc, name: e.target.value })} required aria-label="광고주 이름" />
            <Button type="submit" disabled={busy}>접근 확인 후 연결 · 동기화</Button>
          </form>
        </div>
      )}
    </Card>
  );
}

function Members() {
  const { ws, accounts } = useApp();
  const { data, error: loadError, reload } = useFetch<Member[]>(ws && `/workspaces/${ws.id}/members`);
  const [form, setForm] = useState({ email: "", role: "MEMBER" });
  const { error, busy, run } = useAction();

  const setAccess = (m: Member, accountId: number, level: string) => run(async () => {
    await api(`/workspaces/${ws!.id}/members/${m.membership_id}/access`, { method: "PUT", body: { ad_account_id: accountId, level: level || null } });
    await reload();
  });

  return (
    <Card title="직원 · 담당 계정 배정">
      <ErrorText error={error ?? loadError} />
      <form className="mb-4 flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); run(async () => {
        await api(`/workspaces/${ws!.id}/members`, { body: form });
        setForm({ ...form, email: "" });
        await reload();
      }); }}>
        <input className={`${inputCls} w-64`} type="email" placeholder="가입한 직원 이메일" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required aria-label="직원 이메일" />
        <select className={inputCls} value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} aria-label="역할">
          <option value="MEMBER">직원 (배정 계정만)</option>
          <option value="ADMIN">관리자 (전체 계정)</option>
        </select>
        <Button type="submit" disabled={busy}>직원 추가</Button>
      </form>
      <div className="overflow-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-faint">
            <tr><th className="py-2">직원</th><th>역할</th>{accounts.map((a) => <th key={a.id} className="px-2">{a.name}</th>)}</tr>
          </thead>
          <tbody>
            {(data ?? []).map((m) => (
              <tr key={m.membership_id} className="border-t border-line">
                <td className="py-2"><div className="font-medium">{m.name}</div><div className="text-xs text-faint">{m.email}</div></td>
                <td>{{ OWNER: "대표", ADMIN: "관리자", MEMBER: "직원" }[m.role] ?? m.role}</td>
                {accounts.map((a) => (
                  <td key={a.id} className="px-2">
                    {m.role === "MEMBER" ? (
                      <select className={inputCls} disabled={busy} aria-label={`${m.name} ${a.name} 권한`}
                        value={m.access.find((x) => x.ad_account_id === a.id)?.level ?? ""} onChange={(e) => setAccess(m, a.id, e.target.value)}>
                        <option value="">없음</option><option value="VIEW">보기</option><option value="EDIT">수정</option>
                      </select>
                    ) : <span className="text-xs text-faint">전체</span>}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function Subscription() {
  const { ws } = useApp();
  const { data, error } = useFetch<Sub>(ws && `/workspaces/${ws.id}/subscription`);
  return (
    <Card title="구독">
      <ErrorText error={error} />
      {data && (
        <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-4">
          <div><dt className="text-xs text-faint">플랜</dt><dd>{data.plan}</dd></div>
          <div><dt className="text-xs text-faint">상태</dt><dd>{data.status === "TRIALING" ? `무료 체험 (~${data.trial_ends_at && new Date(data.trial_ends_at).toLocaleDateString("ko-KR")})` : data.status}</dd></div>
          <div><dt className="text-xs text-faint">과금 대상 계정</dt><dd>{data.billable_accounts}개 × {fmt(data.price_per_account, "원")}</dd></div>
          <div><dt className="text-xs text-faint">월 예상 금액</dt><dd className="font-semibold">{fmt(data.monthly_total, "원")}</dd></div>
        </dl>
      )}
      <p className="mt-3 text-xs text-faint">결제 연동은 요금 정책 확정 후 제공됩니다.</p>
    </Card>
  );
}
