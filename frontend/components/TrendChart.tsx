"use client";

import { useEffect, useRef, useState } from "react";

const H = 140, PAD = { top: 8, right: 8, bottom: 20, left: 52 };
const LINE = "#1f3a63"; // 단일 계열 — 제목이 계열 이름이라 범례 없음

function niceMax(v: number) {
  if (v <= 0) return 1;
  const p = 10 ** Math.floor(Math.log10(v)), n = v / p;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p;
}

/** 일별 단일 지표 선 그래프. null은 끊어서 그린다(미제공). 마우스를 올리면 그날 값. */
export function TrendChart({ title, dates, values, unit = "" }: { title: string; dates: string[]; values: (number | null)[]; unit?: string }) {
  const box = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(0);
  const [hover, setHover] = useState<number | null>(null);

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(e.contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const has = values.some((v) => v != null);
  const max = niceMax(Math.max(0, ...values.map((v) => v ?? 0)));
  const iw = Math.max(0, w - PAD.left - PAD.right), ih = H - PAD.top - PAD.bottom;
  const x = (i: number) => PAD.left + (dates.length > 1 ? (i / (dates.length - 1)) * iw : iw / 2);
  const y = (v: number) => PAD.top + ih - (v / max) * ih;
  const fmt = (v: number | null) => (v == null ? "-" : v.toLocaleString("ko-KR") + unit);

  // null에서 끊긴 구간마다 path 하나
  let d = "";
  values.forEach((v, i) => {
    if (v == null) return;
    d += `${i === 0 || values[i - 1] == null ? "M" : "L"}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
  });
  const ticks = [0, max / 2, max];
  const labelIdx = dates.length > 2 ? [0, Math.floor((dates.length - 1) / 2), dates.length - 1] : dates.map((_, i) => i);

  const onMove = (e: React.MouseEvent<SVGRectElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const i = Math.round(((e.clientX - r.left) / r.width) * (dates.length - 1));
    setHover(Math.min(dates.length - 1, Math.max(0, i)));
  };

  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between text-sm">
        <span className="font-medium">{title}</span>
        <span className="text-xs text-faint tabular-nums">{hover != null ? `${dates[hover]} · ${fmt(values[hover])}` : ""}</span>
      </div>
      <div ref={box} className="relative" style={{ height: H }}>
        {!has ? (
          <div className="flex h-full items-center justify-center text-xs text-faint">데이터 없음</div>
        ) : w > 0 && (
          <svg width={w} height={H} role="img" aria-label={`${title} 일별 추이`}>
            {ticks.map((t) => (
              <g key={t}>
                <line x1={PAD.left} x2={w - PAD.right} y1={y(t)} y2={y(t)} stroke="#e3e8ef" strokeWidth={1} />
                <text x={PAD.left - 6} y={y(t)} dy="0.32em" textAnchor="end" fontSize={11} fill="#667085">{t.toLocaleString("ko-KR", { notation: "compact" })}</text>
              </g>
            ))}
            {labelIdx.map((i) => (
              <text key={i} x={x(i)} y={H - 4} fontSize={11} fill="#667085"
                textAnchor={i === 0 ? "start" : i === dates.length - 1 ? "end" : "middle"}>{dates[i].slice(5)}</text>
            ))}
            <path d={d} fill="none" stroke={LINE} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
            {values.length === 1 && values[0] != null && <circle cx={x(0)} cy={y(values[0])} r={4} fill={LINE} />}
            {hover != null && (
              <g pointerEvents="none">
                <line x1={x(hover)} x2={x(hover)} y1={PAD.top} y2={PAD.top + ih} stroke="#cbd3de" strokeWidth={1} />
                {values[hover] != null && <circle cx={x(hover)} cy={y(values[hover]!)} r={4} fill={LINE} stroke="#fff" strokeWidth={2} />}
              </g>
            )}
            <rect x={PAD.left} y={PAD.top} width={iw} height={ih} fill="transparent" onMouseMove={onMove} onMouseLeave={() => setHover(null)} />
          </svg>
        )}
      </div>
    </div>
  );
}
