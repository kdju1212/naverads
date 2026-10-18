"use client";

import Link from "next/link"; // 정적 내보내기의 세그먼트 미리 불러오기 경로가 404가 나서 prefetch={false}
import { usePathname } from "next/navigation";
import { useState } from "react";
import { api, logout, Product } from "@/lib/api";
import { useApp } from "@/lib/store";
import { Button, Card, ErrorText, inputCls } from "./ui";

const NAV = [
  ["/", "대시보드"], ["/campaigns", "캠페인"], ["/adgroups", "광고그룹"], ["/keywords", "키워드"],
  ["/ads", "소재·상품소재"], ["/extensions", "확장소재"], ["/bulk", "엑셀 대량 작업"], ["/jobs", "작업 결과"],
  ["/history", "변경 이력"], ["/settings", "설정"],
] as const;

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const app = useApp();
  if (pathname === "/login") return <>{children}</>;
  if (!app.ready) return <div className="p-10 text-center text-gray-400">불러오는 중…</div>;
  if (!app.ws) return <CreateWorkspace />;

  return (
    <div className="flex min-h-screen">
      <aside className="w-48 shrink-0 border-r border-gray-200 bg-white">
        <div className="px-4 py-4 text-base font-bold text-emerald-700">네이버 광고 관리</div>
        <nav className="flex flex-col px-2 text-sm">
          {NAV.map(([href, label]) => {
            const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link prefetch={false} key={href} href={href} className={`rounded-md px-3 py-2 ${active ? "bg-emerald-50 font-semibold text-emerald-800" : "text-gray-700 hover:bg-gray-50"}`}>
                {label}
              </Link>
            );
          })}
        </nav>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main className="flex-1 p-5">{children}</main>
      </div>
    </div>
  );
}

function TopBar() {
  const { ws, workspaces, setWsId, accounts, selected, setSelected, product, setProduct } = useApp();
  const failed = accounts.filter((a) => a.last_sync?.status === "FAILED").length;
  const neverSynced = accounts.filter((a) => !a.last_sync).length;

  return (
    <header className="flex flex-wrap items-center gap-3 border-b border-gray-200 bg-white px-5 py-2.5 text-sm">
      {workspaces.length > 1 ? (
        <select className={inputCls} value={ws!.id} onChange={(e) => setWsId(Number(e.target.value))} aria-label="조직 선택">
          {workspaces.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
        </select>
      ) : (
        <span className="font-semibold">{ws!.name}</span>
      )}

      <details className="relative">
        <summary className="cursor-pointer list-none rounded-md border border-gray-300 px-2.5 py-1.5">
          광고 계정: {selected.length === 0 ? `전체 (${accounts.length})` : `${selected.length}개 선택`} ▾
        </summary>
        <div className="absolute z-20 mt-1 max-h-80 w-72 overflow-auto rounded-md border border-gray-200 bg-white p-2 shadow-lg">
          <label className="flex items-center gap-2 rounded px-2 py-1.5 hover:bg-gray-50">
            <input type="checkbox" checked={selected.length === 0} onChange={() => setSelected([])} /> 전체 계정
          </label>
          {accounts.map((a) => (
            <label key={a.id} className="flex items-center gap-2 rounded px-2 py-1.5 hover:bg-gray-50">
              <input type="checkbox" checked={selected.includes(a.id)}
                onChange={() => setSelected(selected.includes(a.id) ? selected.filter((x) => x !== a.id) : [...selected, a.id])} />
              <span className="truncate">{a.name}</span>
              <span className="ml-auto text-xs text-gray-400">{a.customer_id}</span>
            </label>
          ))}
          {accounts.length === 0 && <p className="px-2 py-1.5 text-gray-400">연결된 계정이 없습니다. 설정에서 연결하세요.</p>}
        </div>
      </details>

      <div className="flex overflow-hidden rounded-md border border-gray-300" role="group" aria-label="광고 유형">
        {([["", "전체"], ["WEB_SITE", "파워링크"], ["SHOPPING", "쇼핑검색"]] as [Product, string][]).map(([v, label]) => (
          <button key={v} onClick={() => setProduct(v)} className={`px-2.5 py-1.5 ${product === v ? "bg-emerald-600 text-white" : "bg-white hover:bg-gray-50"}`}>{label}</button>
        ))}
      </div>

      {(failed > 0 || neverSynced > 0) && (
        <Link prefetch={false} href="/settings" className="rounded-md bg-amber-50 px-2.5 py-1.5 text-amber-800">
          {failed > 0 ? `동기화 실패 ${failed}개` : `동기화 필요 ${neverSynced}개`}
        </Link>
      )}

      <div className="ml-auto flex items-center gap-2">
        {accounts.some((a) => a.is_mock) && <span className="rounded bg-violet-50 px-2 py-1 text-xs text-violet-700">Mock 데이터</span>}
        <button className="text-gray-500 hover:text-gray-800" onClick={logout}>로그아웃</button>
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
          <p className="text-sm text-gray-600">소속된 조직이 없습니다. 대행사 이름으로 조직을 만들면 14일 무료 체험이 시작됩니다.</p>
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
