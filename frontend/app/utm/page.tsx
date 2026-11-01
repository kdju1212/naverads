"use client";

import { useState } from "react";
import { Button, Card, inputCls, PageTitle } from "@/components/ui";
import { utmUrl } from "@/lib/utm";

// UTM은 GA용, NT는 스마트스토어 통계용(nt_source는 영문만). 키워드 칸은 형식마다 term 키로 붙는다
const FORMATS = {
  utm: {
    label: "UTM (GA)", term: "utm_term",
    fields: [["utm_source", "소스", "naver"], ["utm_medium", "매체", "cpc"], ["utm_campaign", "캠페인", "예: summer_sale"], ["utm_content", "콘텐츠", "예: 소재A"]],
    defaults: { utm_source: "naver", utm_medium: "cpc", utm_campaign: "", utm_content: "" },
  },
  nt: {
    label: "NT (스마트스토어)", term: "nt_keyword",
    fields: [["nt_source", "채널 · 영문만", "예: meta"], ["nt_medium", "매체", "예: feed"], ["nt_detail", "소재", "예: abtest_a"]],
    defaults: { nt_source: "", nt_medium: "", nt_detail: "" },
  },
} as const;
type Fmt = keyof typeof FORMATS;

/** 연결 URL에 UTM 또는 NT 파라미터를 붙인다. 키워드를 여러 줄 넣으면 키워드마다 하나씩 만든다. */
export default function UtmPage() {
  const [fmt, setFmt] = useState<Fmt>("utm");
  const f = FORMATS[fmt];
  const [base, setBase] = useState("");
  const [vals, setVals] = useState<Record<string, string>>({ ...FORMATS.utm.defaults });
  const [terms, setTerms] = useState("");
  const list = [...new Set(terms.split("\n").map((t) => t.trim()).filter(Boolean))];
  const rows = (list.length ? list : [""]).map((t) => [t, utmUrl(base, { ...vals, [f.term]: t })] as const);
  const bad = base.trim() !== "" && rows[0][1] === null;
  const badSrc = fmt === "nt" && /[^\x00-\x7F]/.test(vals.nt_source ?? "");
  const ok = base.trim() !== "" && !bad && !badSrc;

  return (
    <>
      <PageTitle desc="광고 연결 URL에 파라미터를 붙여 유입을 구분합니다. GA는 UTM, 스마트스토어 통계는 NT 형식을 읽습니다. 키워드를 여러 줄 넣으면 키워드마다 만듭니다.">UTM 빌더</PageTitle>
      <div className="mb-4 flex gap-4 border-b border-line" role="tablist">
        {(Object.keys(FORMATS) as Fmt[]).map((v) => (
          <button key={v} role="tab" aria-selected={fmt === v} onClick={() => { setFmt(v); setVals({ ...FORMATS[v].defaults }); }}
            className={`-mb-px cursor-pointer border-b-2 px-1 pb-2 text-sm font-medium transition-colors duration-150 ${fmt === v ? "border-primary text-primary" : "border-transparent text-muted hover:text-ink"}`}>{FORMATS[v].label}</button>
        ))}
      </div>
      <Card title={`${f.label} 만들기`}>
        <div className="flex flex-col gap-2">
          <input className={inputCls} aria-label="연결 URL" placeholder="연결 URL (https://로 시작)" value={base} onChange={(e) => setBase(e.target.value)} />
          {bad && <p role="alert" className="text-xs text-danger">https:// 또는 http://로 시작하는 주소를 넣어 주세요</p>}
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            {f.fields.map(([k, label, ph]) => (
              <label key={k} className="flex flex-col gap-1 text-xs text-muted">
                {label} ({k})
                <input className={inputCls} placeholder={ph} value={vals[k] ?? ""} onChange={(e) => setVals((v) => ({ ...v, [k]: e.target.value }))} />
              </label>
            ))}
          </div>
          {badSrc && <p role="alert" className="text-xs text-danger">스마트스토어 통계는 채널(nt_source)에 영문·숫자만 받습니다</p>}
          <label className="flex flex-col gap-1 text-xs text-muted">
            키워드 ({f.term}) · 한 줄에 하나, 비우면 키워드 없이 하나만
            <textarea className={`${inputCls} h-24`} value={terms} onChange={(e) => setTerms(e.target.value)} />
          </label>
          <textarea readOnly className={`${inputCls} h-40 bg-subtle`} aria-label="결과 URL" placeholder="결과 URL이 여기에 나옵니다"
            value={ok ? rows.map(([, u]) => u).join("\n") : ""} />
          <div>
            <Button variant="secondary" disabled={!ok} onClick={() => navigator.clipboard.writeText(rows.map(([, u]) => u).join("\n"))}>복사하기</Button>
          </div>
        </div>
      </Card>
    </>
  );
}
