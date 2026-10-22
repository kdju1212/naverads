"use client";

import { useState } from "react";
import { Button, Card, inputCls, PageTitle } from "@/components/ui";
import { utmUrl } from "@/lib/utm";

const FIELDS = [
  ["utm_source", "소스", "naver"], ["utm_medium", "매체", "cpc"], ["utm_campaign", "캠페인", "예: summer_sale"],
  ["utm_content", "콘텐츠", "예: 소재A"],
] as const;

/** 연결 URL에 UTM을 붙인다. 키워드(utm_term)를 여러 줄 넣으면 키워드마다 하나씩 만든다. */
export default function UtmPage() {
  const [base, setBase] = useState("");
  const [vals, setVals] = useState<Record<string, string>>({ utm_source: "naver", utm_medium: "cpc", utm_campaign: "", utm_content: "" });
  const [terms, setTerms] = useState("");
  const list = [...new Set(terms.split("\n").map((t) => t.trim()).filter(Boolean))];
  const rows = (list.length ? list : [""]).map((t) => [t, utmUrl(base, { ...vals, utm_term: t })] as const);
  const bad = base.trim() !== "" && rows[0][1] === null;
  const ok = base.trim() !== "" && !bad;

  return (
    <>
      <PageTitle desc="광고 연결 URL에 UTM을 붙여 GA 등에서 유입을 구분합니다. 키워드를 여러 줄 넣으면 utm_term만 바꿔 키워드마다 만듭니다.">UTM 빌더</PageTitle>
      <Card title="UTM 만들기">
        <div className="flex flex-col gap-2">
          <input className={inputCls} aria-label="연결 URL" placeholder="연결 URL (https://로 시작)" value={base} onChange={(e) => setBase(e.target.value)} />
          {bad && <p role="alert" className="text-xs text-red-600">https:// 또는 http://로 시작하는 주소를 넣어 주세요</p>}
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            {FIELDS.map(([k, label, ph]) => (
              <label key={k} className="flex flex-col gap-1 text-xs text-gray-600">
                {label} ({k})
                <input className={inputCls} placeholder={ph} value={vals[k]} onChange={(e) => setVals((v) => ({ ...v, [k]: e.target.value }))} />
              </label>
            ))}
          </div>
          <label className="flex flex-col gap-1 text-xs text-gray-600">
            키워드 (utm_term) · 한 줄에 하나, 비우면 키워드 없이 하나만
            <textarea className={`${inputCls} h-24`} value={terms} onChange={(e) => setTerms(e.target.value)} />
          </label>
          <textarea readOnly className={`${inputCls} h-40 bg-gray-50`} aria-label="UTM 결과" placeholder="결과 URL이 여기에 나옵니다"
            value={ok ? rows.map(([, u]) => u).join("\n") : ""} />
          <div>
            <Button variant="secondary" disabled={!ok} onClick={() => navigator.clipboard.writeText(rows.map(([, u]) => u).join("\n"))}>복사하기</Button>
          </div>
        </div>
      </Card>
    </>
  );
}
