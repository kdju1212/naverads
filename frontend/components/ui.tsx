"use client";

import { ButtonHTMLAttributes, ReactNode, useEffect, useState } from "react";

/** 디자인 시스템: design-system/MASTER.md. 색은 globals.css @theme 토큰 */
export function Button({ variant = "primary", className = "", ...p }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" | "danger" }) {
  const v = {
    primary: "border-primary bg-primary text-white hover:bg-primary-hover",
    secondary: "border-line-strong bg-surface text-ink hover:bg-subtle",
    ghost: "border-transparent bg-transparent text-muted hover:bg-subtle hover:text-ink",
    danger: "border-danger/30 bg-surface text-danger hover:bg-danger-soft",
  }[variant];
  return <button {...p} className={`inline-flex h-8 cursor-pointer items-center justify-center gap-1.5 whitespace-nowrap rounded-control border px-3 text-[13px] font-medium transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50 ${v} ${className}`} />;
}

export function Card({ title, actions, children, className = "" }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-panel border border-line bg-surface ${className}`}>
      {(title || actions) && (
        <div className="flex min-h-12 items-center justify-between gap-2 border-b border-line px-4 py-2">
          <h2 className="text-[15px] font-semibold">{title}</h2>
          <div className="flex items-center gap-2">{actions}</div>
        </div>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

const OK = "bg-accent-soft text-accent", NEUTRAL = "bg-subtle text-muted ring-1 ring-inset ring-line";
const WARN = "bg-warning-soft text-warning", BAD = "bg-danger-soft text-danger", INFO = "bg-info-soft text-info";
const BADGE: Record<string, string> = {
  ON: OK, OFF: NEUTRAL, SUCCESS: OK, DONE: OK, VALID: INFO, FAILED: BAD, INVALID: BAD, PARTIAL: WARN, PREVIEW: INFO, RUNNING: WARN,
  PASS: OK, WARN: WARN, FAIL: BAD, PENDING: INFO, REJECTED: NEUTRAL, EXPIRED: NEUTRAL,
};
// 광고 유형은 상태가 아니라 점 없이 구분만
const KIND: Record<string, string> = { WEB_SITE: "bg-primary-soft text-primary", SHOPPING: NEUTRAL };
const BADGE_LABEL: Record<string, string> = {
  SUCCESS: "성공", DONE: "완료", VALID: "실행 가능", FAILED: "실패", INVALID: "오류", PARTIAL: "부분 실패",
  PREVIEW: "미리보기", RUNNING: "실행 중", WEB_SITE: "파워링크", SHOPPING: "쇼핑검색",
  PASS: "통과", WARN: "주의", FAIL: "실패", PENDING: "승인 대기", REJECTED: "거절", EXPIRED: "만료",
};

export function Badge({ value }: { value: string }) {
  const kind = KIND[value];
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded px-1.5 py-0.5 text-xs font-medium ${kind ?? BADGE[value] ?? NEUTRAL}`}>
      {!kind && <span aria-hidden="true" className="size-1.5 rounded-full bg-current" />}
      {BADGE_LABEL[value] ?? value}
    </span>
  );
}

export function ErrorText({ error }: { error: string | null }) {
  return error ? <p role="alert" className="rounded-control bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p> : null;
}

export function PageTitle({ children, desc }: { children: ReactNode; desc?: ReactNode }) {
  return (
    <div className="mb-5">
      <h1 className="text-xl font-bold text-balance">{children}</h1>
      {desc && <p className="mt-1 max-w-[72ch] text-sm text-faint">{desc}</p>}
    </div>
  );
}

export const inputCls = "rounded-control border border-line-strong bg-surface px-2.5 py-[5px] text-[13px] leading-5 text-ink placeholder:text-faint focus:outline-none focus-visible:ring-2 focus-visible:ring-focus";

/** toast("…")(lib/api)를 오른쪽 아래에 4초 보여준다(design-system/MASTER.md 알림) */
export function Toaster() {
  const [list, setList] = useState<{ id: number; msg: string }[]>([]);
  useEffect(() => {
    let seq = 0;
    const on = (e: Event) => {
      const msg = (e as CustomEvent<string>).detail, id = ++seq;
      setList((l) => (l.some((t) => t.msg === msg) ? l : [...l, { id, msg }])); // 계정 여러 개가 같은 알림을 띄워도 하나만
      setTimeout(() => setList((l) => l.filter((t) => t.id !== id)), 4000);
    };
    window.addEventListener("app-toast", on);
    return () => window.removeEventListener("app-toast", on);
  }, []);
  return (
    <div role="status" aria-live="polite" className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {list.map((t) => <div key={t.id} className="rounded-panel border border-line bg-surface px-4 py-2.5 text-sm shadow-pop">{t.msg}</div>)}
    </div>
  );
}
