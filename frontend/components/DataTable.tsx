"use client";

import { ReactNode, useMemo, useState } from "react";
import { inputCls } from "./ui";

export interface Col<T> {
  key: string;
  label: string;
  value: (r: T) => string | number | null; // 정렬·검색 기준
  render?: (r: T) => ReactNode;
  num?: boolean;
}

export function DataTable<T extends { id: string | number }>({ rows, cols, selected, onSelect, loading, empty = "데이터가 없습니다", toolbar }: {
  rows: T[];
  cols: Col<T>[];
  selected?: Set<T["id"]>;
  onSelect?: (ids: Set<T["id"]>) => void;
  loading?: boolean;
  empty?: string;
  toolbar?: ReactNode;
}) {
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<{ key: string; dir: 1 | -1 } | null>(null);

  const view = useMemo(() => {
    const needle = q.trim().toLowerCase();
    let out = needle ? rows.filter((r) => cols.some((c) => String(c.value(r) ?? "").toLowerCase().includes(needle))) : rows;
    if (sort) {
      const col = cols.find((c) => c.key === sort.key)!;
      out = [...out].sort((a, b) => {
        const x = col.value(a), y = col.value(b);
        if (x == null) return 1;
        if (y == null) return -1;
        return (x < y ? -1 : x > y ? 1 : 0) * sort.dir;
      });
    }
    return out;
  }, [rows, cols, q, sort]);

  const allChecked = !!selected && view.length > 0 && view.every((r) => selected.has(r.id));
  const toggleAll = () => {
    if (!selected || !onSelect) return;
    const next = new Set(selected);
    view.forEach((r) => (allChecked ? next.delete(r.id) : next.add(r.id)));
    onSelect(next);
  };
  const toggle = (id: T["id"]) => {
    if (!selected || !onSelect) return;
    const next = new Set(selected);
    if (next.has(id)) next.delete(id); else next.add(id);
    onSelect(next);
  };

  return (
    <div className="overflow-hidden rounded-panel border border-line bg-surface">
      <div className={`flex flex-wrap items-center gap-2 border-b border-line px-3 py-2 ${selected && selected.size > 0 ? "bg-primary-soft" : ""}`}>
        <input className={`${inputCls} w-64`} placeholder="검색 (이름, ID, 광고주…)" value={q} onChange={(e) => setQ(e.target.value)} aria-label="표 검색" />
        <span className="text-xs text-faint">
          {view.length.toLocaleString()}건{selected && selected.size > 0 && <> · <b className="font-semibold text-primary">{selected.size}건 선택</b></>}
        </span>
        <div className="ml-auto flex flex-wrap items-center gap-2">{toolbar}</div>
      </div>
      <div className="max-h-[calc(100vh-260px)] overflow-auto">
        <table className="w-full text-[13px]">
          <thead className="sticky top-0 z-10 bg-subtle text-left text-xs text-muted shadow-[inset_0_-1px_0_var(--color-line)]">
            <tr>
              {selected && (
                <th className="h-9 w-9 px-3"><input type="checkbox" aria-label="전체 선택" checked={allChecked} onChange={toggleAll} /></th>
              )}
              {cols.map((c) => (
                <th key={c.key} className={`h-9 whitespace-nowrap px-3 font-semibold ${c.num ? "text-right" : ""}`}>
                  <button className="cursor-pointer hover:text-ink" onClick={() => setSort((s) => (s?.key === c.key ? { key: c.key, dir: s.dir === 1 ? -1 : 1 } : { key: c.key, dir: 1 }))}>
                    {c.label}{sort?.key === c.key ? (sort.dir === 1 ? " ▲" : " ▼") : ""}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={cols.length + 1} className="px-3 py-8 text-center text-faint">불러오는 중…</td></tr>
            ) : view.length === 0 ? (
              <tr><td colSpan={cols.length + 1} className="px-3 py-8 text-center text-faint">{empty}</td></tr>
            ) : view.map((r) => (
              <tr key={r.id} className={`h-10 border-t border-line first:border-t-0 ${selected?.has(r.id) ? "bg-primary-soft" : "hover:bg-subtle"}`}>
                {selected && (
                  <td className="px-3 py-1.5"><input type="checkbox" aria-label="행 선택" checked={selected.has(r.id)} onChange={() => toggle(r.id)} /></td>
                )}
                {cols.map((c) => (
                  <td key={c.key} className={`px-3 py-1.5 ${c.num ? "text-right tabular-nums" : ""}`}>{c.render ? c.render(r) : (c.value(r) ?? "-")}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
