"use client";

import { ButtonHTMLAttributes, ReactNode } from "react";

export function Button({ variant = "primary", className = "", ...p }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "danger" }) {
  const v = {
    primary: "bg-emerald-600 text-white hover:bg-emerald-700",
    secondary: "bg-white border border-gray-300 text-gray-800 hover:bg-gray-50",
    danger: "bg-white border border-red-300 text-red-700 hover:bg-red-50",
  }[variant];
  return <button {...p} className={`rounded-md px-3 py-1.5 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed ${v} ${className}`} />;
}

export function Card({ title, actions, children, className = "" }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-lg border border-gray-200 bg-white ${className}`}>
      {(title || actions) && (
        <div className="flex items-center justify-between gap-2 border-b border-gray-100 px-4 py-2.5">
          <h2 className="text-sm font-semibold">{title}</h2>
          <div className="flex items-center gap-2">{actions}</div>
        </div>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

const BADGE: Record<string, string> = {
  ON: "bg-emerald-50 text-emerald-700", OFF: "bg-gray-100 text-gray-600",
  SUCCESS: "bg-emerald-50 text-emerald-700", DONE: "bg-emerald-50 text-emerald-700", VALID: "bg-sky-50 text-sky-700",
  FAILED: "bg-red-50 text-red-700", INVALID: "bg-red-50 text-red-700", PARTIAL: "bg-amber-50 text-amber-800",
  PREVIEW: "bg-sky-50 text-sky-700", RUNNING: "bg-amber-50 text-amber-800",
  WEB_SITE: "bg-indigo-50 text-indigo-700", SHOPPING: "bg-orange-50 text-orange-700",
};
const BADGE_LABEL: Record<string, string> = {
  SUCCESS: "성공", DONE: "완료", VALID: "실행 가능", FAILED: "실패", INVALID: "오류", PARTIAL: "부분 실패",
  PREVIEW: "미리보기", RUNNING: "실행 중", WEB_SITE: "파워링크", SHOPPING: "쇼핑검색",
};

export function Badge({ value }: { value: string }) {
  return <span className={`inline-block whitespace-nowrap rounded px-1.5 py-0.5 text-xs font-medium ${BADGE[value] ?? "bg-gray-100 text-gray-700"}`}>{BADGE_LABEL[value] ?? value}</span>;
}

export function ErrorText({ error }: { error: string | null }) {
  return error ? <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null;
}

export function PageTitle({ children, desc }: { children: ReactNode; desc?: ReactNode }) {
  return (
    <div className="mb-4">
      <h1 className="text-lg font-bold">{children}</h1>
      {desc && <p className="mt-0.5 text-sm text-gray-500">{desc}</p>}
    </div>
  );
}

export const inputCls = "rounded-md border border-gray-300 bg-white px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500";
