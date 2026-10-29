"use client";

import { useState } from "react";
import { Badge, Button, Card, ErrorText, inputCls, PageTitle } from "@/components/ui";
import { api, API_URL, fmt, logout } from "@/lib/api";
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
        <MyAccount />
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
  const [cred, setCred] = useState({ label: "", api_key: "", secret_key: "", is_mock: false });
  const [acc, setAcc] = useState({ credential_id: "", customer_id: "", name: "" });
  const [syncing, setSyncing] = useState<number | null>(null);
  const { error, busy, run } = useAction();

  const doSync = async (id: number) => {
    setSyncing(id);
    try {
      type Sync = { status: string; error: string | null; next_offset: number | null };
      const call = (offset = 0) => api<Sync>(`/workspaces/${ws!.id}/ad-accounts/${id}/sync?offset=${offset}`, { method: "POST" });
      let r = await call();
      while (r.status === "RUNNING") r = await call(r.next_offset!); // 캠페인이 많으면 서버가 나눠 받는다
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
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={cred.is_mock} onChange={(e) => setCred({ ...cred, is_mock: e.target.checked })} /> Mock 모드 (실제 계정 없이 가짜 데이터로 화면 체험)</label>
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

function MyAccount() {
  const { data: me } = useFetch<{ email: string; has_password: boolean }>("/auth/me");
  const [pw, setPw] = useState({ current_password: "", new_password: "" });
  const [done, setDone] = useState(false);
  const { error, busy, run } = useAction();
  const change = () => run(async () => {
    const r = await api<{ token: string }>("/auth/password", { method: "POST", body: pw });
    // 같은 사용자라 setToken처럼 브라우저 보관 데이터를 지우지 않는다
    try { localStorage.setItem("token", r.token); } catch { /* 저장 불가 환경 */ }
    setPw({ current_password: "", new_password: "" });
    setDone(true);
  });
  const [leave, setLeave] = useState("");
  const [claudeOff, setClaudeOff] = useState(false);
  const disconnectClaude = () => confirm("Claude 연결만 끊습니다. 이 웹 로그인은 그대로입니다. 진행할까요?")
    && run(async () => { await api("/auth/disconnect-claude", { method: "POST" }); setClaudeOff(true); });
  const deleteAccount = () => confirm("탈퇴하면 혼자 소유한 조직은 연결 계정·작업 이력까지 모두 지워지고 되돌릴 수 없습니다. 탈퇴할까요?")
    && run(async () => {
      await api("/auth/delete-account", { method: "POST", body: me?.has_password ? { password: leave } : { email: leave } });
      await logout();
    });
  const logoutAll = () => confirm("이 기기와 다른 모든 기기, Claude 연결에서 로그아웃합니다. Claude는 다시 연결해야 합니다. 진행할까요?")
    && run(async () => { await api("/auth/logout-all", { method: "POST" }); await logout(); });
  const [copied, setCopied] = useState(false);
  // claude.ai는 커넥터 주소를 미리 채우는 링크가 없어, 주소 복사 + 커넥터 화면 열기로 대신한다
  const connectClaude = () => {
    navigator.clipboard?.writeText(`${API_URL}/mcp`).then(() => setCopied(true), () => setCopied(false));
    window.open("https://claude.ai/settings/connectors", "_blank", "noopener");
  };
  return (
    <>
    <Card title="Claude 연결">
      <p className="mb-2 text-sm">Claude에서 이 앱으로 광고를 조회·변경할 수 있습니다. 버튼을 누르면 주소가 복사되고 Claude 커넥터 화면이 열립니다.</p>
      <ol className="mb-3 list-decimal pl-5 text-sm">
        <li>열린 화면에서 &quot;커스텀 커넥터 추가&quot;를 누릅니다.</li>
        <li>이름에 &quot;네이버광고&quot;, URL에 복사된 주소를 붙여 넣고 추가합니다.</li>
        <li>&quot;연결&quot;을 누르고 이 앱 계정으로 로그인합니다.</li>
      </ol>
      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" onClick={connectClaude}>Claude에 연결하기</Button>
        <code className="rounded bg-line/40 px-2 py-1 text-xs">{API_URL}/mcp</code>
      </div>
      {copied && <p className="mt-2 text-sm text-info" role="status">주소를 복사했습니다. Claude 화면에서 붙여 넣으세요.</p>}
      <details className="mt-3 border-t border-line pt-3">
        <summary className="cursor-pointer text-sm text-faint">알아두기</summary>
        <ul className="mt-2 list-disc pl-5 text-sm">
          <li>Claude는 내가 속한 조직·담당 계정만 봅니다. 볼 수 있는 범위는 이 앱의 권한과 같습니다.</li>
          <li>입찰가·소재 등 변경은 Claude가 먼저 미리보기를 보여 주고, 승인해야만 실행(또는 예약)됩니다.</li>
          <li>Claude에게 &quot;내 광고 계정 보여줘&quot;, &quot;캠페인 목록 보여줘&quot;처럼 말하면 됩니다.</li>
          <li>연결은 7일 동안 쓰지 않으면 끊깁니다. 끊기면 Claude 커넥터 화면에서 &quot;연결&quot;을 다시 누르세요.</li>
          <li>Google로 가입했다면 로그인 화면에서도 Google로 로그인하세요.</li>
          <li>회사(Team·Enterprise) Claude는 관리자가 커넥터를 추가해야 할 수 있습니다.</li>
          <li>끊으려면 아래 &quot;Claude 연결만 끊기&quot;를 누르거나 Claude 커넥터 화면에서 제거하세요.</li>
        </ul>
      </details>
    </Card>
    <Card title="내 계정">
      {me && !me.has_password && <p className="mb-2 text-sm">Google로 로그인한 계정입니다 ({me.email}). 비밀번호는 Google에서 관리합니다.</p>}
      <form className="flex flex-wrap items-end gap-2" onSubmit={(e) => { e.preventDefault(); change(); }}>
        {me?.has_password && <>
        <label className="text-sm">현재 비밀번호
          <input type="password" autoComplete="current-password" required className={`${inputCls} mt-1 block`}
            value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} />
        </label>
        <label className="text-sm">새 비밀번호 (8자 이상)
          <input type="password" autoComplete="new-password" required minLength={8} className={`${inputCls} mt-1 block`}
            value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} />
        </label>
        <Button type="submit" disabled={busy}>비밀번호 변경</Button>
        </>}
        <Button type="button" variant="secondary" disabled={busy} onClick={logoutAll}>모든 기기에서 로그아웃</Button>
        <Button type="button" variant="secondary" disabled={busy} onClick={disconnectClaude}>Claude 연결만 끊기</Button>
      </form>
      {claudeOff && <p className="mt-2 text-sm text-info" role="status">Claude 연결을 끊었습니다. 다시 쓰려면 Claude에서 다시 연결하세요.</p>}
      {done && <p className="mt-2 text-sm text-info" role="status">비밀번호를 바꿨습니다. 다른 기기와 Claude 연결은 로그아웃되었습니다.</p>}
      <ErrorText error={error} />
      <p className="mt-3 text-xs text-faint">{me?.has_password && "비밀번호를 바꾸거나 "}모든 기기에서 로그아웃하면 Claude 연결도 끊겨 다시 연결해야 합니다.</p>
      {me && (
        <details className="mt-4 border-t border-line pt-3">
          <summary className="cursor-pointer text-sm text-faint">회원 탈퇴</summary>
          <form className="mt-2 flex flex-wrap items-end gap-2" onSubmit={(e) => { e.preventDefault(); deleteAccount(); }}>
            <label className="text-sm">{me.has_password ? "비밀번호 확인" : `이메일 확인 (${me.email})`}
              <input type={me.has_password ? "password" : "email"} autoComplete={me.has_password ? "current-password" : "off"} required
                className={`${inputCls} mt-1 block`} value={leave} onChange={(e) => setLeave(e.target.value)} />
            </label>
            <Button type="submit" variant="danger" disabled={busy}>탈퇴</Button>
          </form>
          <p className="mt-2 text-xs text-faint">혼자 소유한 조직은 연결 계정·작업 이력까지 모두 지워집니다. 다른 조직에서는 빠지기만 합니다.</p>
        </details>
      )}
    </Card>
    </>
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
