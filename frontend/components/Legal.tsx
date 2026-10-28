import Link from "next/link";
import { ReactNode } from "react";
import { OPERATOR } from "@/lib/legal";

/** 로그인 없이 보는 약관·방침 화면의 틀 */
export function LegalPage({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <Link href="/login" className="text-sm text-faint hover:text-ink">← {OPERATOR.service}</Link>
      <h1 className="mt-3 text-2xl font-bold">{title}</h1>
      <p className="mt-1 text-sm text-faint">시행일 {OPERATOR.effective}</p>
      <div className="mt-6 flex flex-col gap-6 rounded-panel border border-line bg-surface p-6 text-sm leading-6 [&_li]:ml-5 [&_li]:list-disc [&_table]:w-full [&_td]:border [&_td]:border-line [&_td]:p-2 [&_td]:align-top [&_th]:border [&_th]:border-line [&_th]:bg-subtle [&_th]:p-2 [&_th]:text-left">
        {children}
      </div>
      <p className="mt-6 text-xs text-faint">
        <Link href="/terms" className="underline">이용약관</Link> · <Link href="/privacy" className="font-semibold underline">개인정보처리방침</Link>
      </p>
    </main>
  );
}

export function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h2 className="mb-2 text-[15px] font-semibold">{title}</h2>
      <div className="flex flex-col gap-2 text-muted">{children}</div>
    </section>
  );
}

/** 운영자 정보(상호·대표·사업자번호·연락처) 한 줄 */
export function OperatorLine() {
  return (
    <p>
      운영자 {OPERATOR.name}{OPERATOR.ceo && ` (대표 ${OPERATOR.ceo})`}{OPERATOR.bizNo && ` · 사업자등록번호 ${OPERATOR.bizNo}`} · 문의 {OPERATOR.email}
    </p>
  );
}
