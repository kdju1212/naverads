"use client";

import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { Account, api, getToken, Product, Workspace } from "./api";

interface AppState {
  ready: boolean;
  workspaces: Workspace[];
  ws: Workspace | null;
  setWsId: (id: number) => void;
  reloadWorkspaces: () => Promise<void>;
  accounts: Account[];
  reloadAccounts: () => Promise<void>;
  selected: number[]; // 비어 있으면 접근 가능한 전체 계정
  setSelected: (ids: number[]) => void;
  product: Product;
  setProduct: (p: Product) => void;
  accountName: (id: number | null) => string;
  /** 선택 계정·광고 유형을 API 쿼리로 */
  query: (extra?: Record<string, string | number | undefined>) => string;
}

const Ctx = createContext<AppState | null>(null);
/** 로그인 없이 보는 화면(약관·방침은 가입 전에 읽을 수 있어야 한다) */
export const PUBLIC_PATHS = ["/login", "/terms", "/privacy"];

function stored(key: string) {
  try { return localStorage.getItem(key); } catch { return null; }
}
function store(key: string, v: string) {
  try { localStorage.setItem(key, v); } catch { /* 저장 불가 환경 */ }
}

export function AppProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [loaded, setLoaded] = useState(false);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [wsId, setWsIdState] = useState<number | null>(null);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [selected, setSelectedState] = useState<number[]>([]);
  // 상단 바는 로딩이 끝난 뒤에만 그려지므로 서버 렌더와 어긋나지 않는다
  const [product, setProductState] = useState<Product>(() => (stored("product") as Product) ?? "");
  const authed = !PUBLIC_PATHS.includes(pathname);
  const ready = !authed || loaded;

  const applyWorkspaces = useCallback((list: Workspace[]) => {
    setWorkspaces(list);
    const saved = Number(stored("wsId"));
    setWsIdState(list.find((w) => w.id === saved)?.id ?? list[0]?.id ?? null);
  }, []);
  const reloadWorkspaces = useCallback(async () => applyWorkspaces(await api<Workspace[]>("/workspaces")), [applyWorkspaces]);

  useEffect(() => {
    if (authed && !getToken()) router.replace("/login");
  }, [authed, router]);

  // 로그인 상태가 될 때 한 번만 조직 목록을 불러온다(페이지 이동마다 다시 부르지 않음)
  useEffect(() => {
    if (!authed || !getToken()) return;
    let alive = true;
    api<Workspace[]>("/workspaces").then((list) => alive && applyWorkspaces(list), () => {}).finally(() => alive && setLoaded(true));
    return () => { alive = false; };
  }, [authed, applyWorkspaces]);

  const applyAccounts = useCallback((list: Account[]) => {
    setAccounts(list);
    // 해제·권한 회수된 계정은 선택에서 뺀다
    setSelectedState((sel) => sel.filter((id) => list.some((a) => a.id === id)));
  }, []);
  const reloadAccounts = useCallback(async () => {
    if (wsId) applyAccounts(await api<Account[]>(`/workspaces/${wsId}/ad-accounts`));
  }, [wsId, applyAccounts]);

  useEffect(() => {
    if (!wsId) return;
    let alive = true;
    api<Account[]>(`/workspaces/${wsId}/ad-accounts`).then((list) => alive && applyAccounts(list), () => {});
    return () => { alive = false; };
  }, [wsId, applyAccounts]);

  const value = useMemo<AppState>(() => ({
    ready, workspaces, reloadWorkspaces, accounts, reloadAccounts, selected, product,
    ws: workspaces.find((w) => w.id === wsId) ?? null,
    setWsId: (id) => { store("wsId", String(id)); setWsIdState(id); setSelectedState([]); },
    setSelected: setSelectedState,
    setProduct: (p) => { store("product", p); setProductState(p); },
    accountName: (id) => accounts.find((a) => a.id === id)?.name ?? (id == null ? "-" : `#${id}`),
    query: (extra = {}) => {
      const q = new URLSearchParams();
      if (selected.length) q.set("account_ids", selected.join(","));
      for (const [k, v] of Object.entries(extra)) if (v !== undefined && v !== "") q.set(k, String(v));
      const s = q.toString();
      return s ? `?${s}` : "";
    },
  }), [ready, workspaces, wsId, reloadWorkspaces, accounts, reloadAccounts, selected, product]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useApp outside AppProvider");
  return c;
}
