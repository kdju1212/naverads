"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { Keyword } from "@/lib/naverData";
import { useApp } from "@/lib/store";
import { Col } from "./DataTable";
import { Button } from "./ui";

interface Rank { naver_id: string; PC?: number | null; MOBILE?: number | null; error?: string }

const RANK_LIMIT = 10; // 서버 main.RANK_LIMIT와 같게

const label = (n: number | null | undefined) => (n ? `${n}위` : "노출 안 됨");

/** 선택한 키워드의 지금 순위(네이버 검색 화면 기준)를 확인하는 버튼과 표 칸. */
export function useRanks() {
  const { ws } = useApp();
  const [ranks, setRanks] = useState<Map<string, Rank>>(new Map());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const check = async (picked: Keyword[]) => {
    if (!ws) return;
    setBusy(true);
    setError(null);
    try {
      const keywords = picked.map((k) => ({ ad_account_id: k.ad_account_id, naver_id: k.naver_id, keyword: k.keyword }));
      const r = await api<Rank[]>(`/workspaces/${ws.id}/ranks`, { body: { keywords } });
      setRanks((m) => new Map([...m, ...r.map((x) => [x.naver_id, x] as const)]));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const col: Col<Keyword> = {
    key: "rank", label: "지금 순위", num: true, value: (r) => ranks.get(r.naver_id)?.PC ?? null,
    render: (r) => {
      const x = ranks.get(r.naver_id);
      if (!x) return <span className="text-faint">-</span>;
      if (x.error) return <span className="text-xs text-danger">{x.error}</span>;
      return <span className="text-xs">PC {label(x.PC)} · 모바일 {label(x.MOBILE)}</span>;
    },
  };

  const button = (picked: Keyword[]) => (
    <>
      {error && <span role="alert" className="text-xs text-danger">{error}</span>}
      <Button variant="secondary" disabled={busy || picked.length === 0 || picked.length > RANK_LIMIT} onClick={() => check(picked)}
        title={`네이버 검색 화면에서 지금 몇 위인지 확인합니다 (한 번에 ${RANK_LIMIT}개까지)`}>
        {busy ? "확인 중…" : picked.length > RANK_LIMIT ? `순위 확인은 ${RANK_LIMIT}개까지` : "지금 순위"}
      </Button>
    </>
  );

  return { col, button };
}
