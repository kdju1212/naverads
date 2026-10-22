"use client";

import Link from "next/link"; // 정적 내보내기의 세그먼트 미리 불러오기 경로가 404가 나서 prefetch={false}
import { usePathname } from "next/navigation";
import { useState } from "react";
import { api, logout, Product } from "@/lib/api";
import { useApp } from "@/lib/store";
import { Button, Card, ErrorText, inputCls } from "./ui";

const NAV: [string, [string, string][]][] = [
  ["성과", [["/", "대시보드"]]],
  ["광고 관리", [["/campaigns", "캠페인"], ["/adgroups", "광고그룹"], ["/keywords", "키워드"], ["/keyword-register", "키워드 등록"],
    ["/auto-bids", "자동입찰"], ["/ads", "소재·상품소재"], ["/extensions", "확장소재"]]],
  ["작업", [["/bulk", "엑셀 대량 작업"], ["/jobs", "작업 결과"]]],
  ["도구", [["/utm", "UTM 빌더"]]],
  ["관리", [["/history", "변경 이력"], ["/settings", "설정"]]],
];
// 쇼핑검색만 볼 때는 파워링크 전용 메뉴를 숨긴다
const POWERLINK_ONLY = ["/keywords", "/keyword-register", "/auto-bids", "/extensions"];

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const app = useApp();
  if (pathname === "/login") return <>{children}</>;
  if (!app.ready) return <div className="p-10 text-center text-faint">불러오는 중…</div>;
  if (!app.ws) return <CreateWorkspace />;

  return (
    <div className="flex min-h-screen">
      <aside className="w-56 shrink-0 border-r border-line bg-surface">
        <div className="flex h-14 items-center gap-2 border-b border-line px-4 font-bold text-primary">
          <span aria-hidden="true" className="size-[18px] rounded bg-accent" />네이버 광고 관리
        </div>
        <nav className="flex flex-col px-2 pb-4 text-[13px]" aria-label="메뉴">
          {NAV.map(([group, items]) => {
            const shown = items.filter(([href]) => app.product !== "SHOPPING" || !POWERLINK_ONLY.includes(href));
            if (!shown.length) return null;
            return (
              <div key={group} className="flex flex-col gap-0.5">
                <div className="px-3 pb-1 pt-4 text-xs font-medium text-faint">{group}</div>
                {shown.map(([href, label]) => {
                  const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
                  return (
                    <Link prefetch={false} key={href} href={href} aria-current={active ? "page" : undefined}
                      className={`rounded-control px-3 py-1.5 transition-colors duration-150 ${active ? "bg-primary-soft font-semibold text-primary" : "text-muted hover:bg-subtle hover:text-ink"}`}>
                      {label}
                    </Link>
                  );
                })}
              </div>
            );
          })}
        </nav>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}

function TopBar() {
  const { ws, workspaces, setWsId, accounts, selected, setSelected, product, setProduct } = useApp();
  const failed = accounts.filter((a) => a.last_sync?.status === "FAILED").length;
  const neverSynced = accounts.filter((a) => !a.last_sync).length;

  return (
    <header className="flex min-h-14 flex-wrap items-center gap-2 border-b border-line bg-surface px-6 py-2 text-[13px]">
      {workspaces.length > 1 ? (
        <select className={inputCls} value={ws!.id} onChange={(e) => setWsId(Number(e.target.value))} aria-label="조직 선택">
          {workspaces.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
        </select>
      ) : (
        <span className="px-1 font-semibold">{ws!.name}</span>
      )}

      <details className="relative">
        <summary className="flex h-8 cursor-pointer list-none items-center gap-1.5 rounded-control border border-line-strong bg-surface px-2.5 hover:bg-subtle">
          <span className="text-muted">광고 계정</span> <b className="font-semibold">{selected.length === 0 ? `전체 ${accounts.length}` : `${selected.length}개 선택`}</b> <span aria-hidden="true" className="text-faint">▾</span>
        </summary>
        <div className="absolute z-20 mt-1 max-h-80 w-72 overflow-auto rounded-panel border border-line bg-surface p-1.5 shadow-pop">
          <label className="flex items-center gap-2 rounded px-2 py-1.5 hover:bg-subtle">
            <input type="checkbox" checked={selected.length === 0} onChange={() => setSelected([])} /> 전체 계정
          </label>
          {accounts.map((a) => (
            <label key={a.id} className="flex items-center gap-2 rounded px-2 py-1.5 hover:bg-subtle">
              <input type="checkbox" checked={selected.includes(a.id)}
                onChange={() => setSelected(selected.includes(a.id) ? selected.filter((x) => x !== a.id) : [...selected, a.id])} />
              <span className="truncate">{a.name}</span>
              <span className="ml-auto text-xs text-faint">{a.customer_id}</span>
            </label>
          ))}
          {accounts.length === 0 && <p className="px-2 py-1.5 text-faint">연결된 계정이 없습니다. 설정에서 연결하세요.</p>}
        </div>
      </details>

      <div className="flex overflow-hidden rounded-control border border-line-strong" role="group" aria-label="광고 유형">
        {([["", "전체"], ["WEB_SITE", "파워링크"], ["SHOPPING", "쇼핑검색"]] as [Product, string][]).map(([v, label]) => (
          <button key={v} onClick={() => setProduct(v)} aria-pressed={product === v}
            className={`h-[30px] cursor-pointer px-3 font-medium transition-colors duration-150 [&+&]:border-l [&+&]:border-line-strong ${product === v ? "bg-primary text-white" : "bg-surface text-muted hover:bg-subtle"}`}>{label}</button>
        ))}
      </div>

      {(failed > 0 || neverSynced > 0) && (
        <Link prefetch={false} href="/settings" className="inline-flex h-7 items-center rounded-control bg-warning-soft px-2.5 text-xs font-medium text-warning">
          {failed > 0 ? `동기화 실패 ${failed}개` : `동기화 필요 ${neverSynced}개`}
        </Link>
      )}

      <div className="ml-auto flex items-center gap-2">
        {accounts.some((a) => a.is_mock) && <span className="rounded bg-info-soft px-2 py-1 text-xs text-info">Mock 데이터</span>}
        <Button variant="ghost" onClick={logout}>로그아웃</Button>
      </div>
    </header>
  );
}

function CreateWorkspace() {
  const { reloadWorkspaces } = useApp();
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  return (
    <div className="mx-auto mt-24 max-w-md">
      <Card title="대행사(조직) 만들기">
        <form className="flex flex-col gap-3" onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError(null);
          try {
            await api("/workspaces", { body: { name, type: "AGENCY" } });
            await reloadWorkspaces();
          } catch (err) { setError((err as Error).message); }
          setBusy(false);
        }}>
          <p className="text-sm text-muted">소속된 조직이 없습니다. 대행사 이름으로 조직을 만들면 14일 무료 체험이 시작됩니다.</p>
          <input className={inputCls} placeholder="대행사 이름" value={name} onChange={(e) => setName(e.target.value)} required aria-label="대행사 이름" />
          <ErrorText error={error} />
          <div className="flex gap-2">
            <Button type="submit" disabled={busy || !name}>만들기</Button>
            <Button type="button" variant="secondary" onClick={logout}>로그아웃</Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
