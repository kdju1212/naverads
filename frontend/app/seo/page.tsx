"use client";

import { useState } from "react";
import { Badge, Button, Card, ErrorText, inputCls, PageTitle } from "@/components/ui";
import { api } from "@/lib/api";
import { type Check, extractFacts, type Fetched, runChecks } from "@/lib/seo";
import { useApp } from "@/lib/store";

const ORDER = { FAIL: 0, WARN: 1, PASS: 2 } as const;

/** 광고주 페이지 하나의 SEO·GEO 기본기를 점검한다. 서버는 페이지만 가져오고 판정은 브라우저에서 한다. */
export default function SeoPage() {
  const { ws } = useApp();
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ url: string; checks: Check[] } | null>(null);

  async function run() {
    setBusy(true); setError(null); setResult(null);
    try {
      const f = await api<Fetched>(`/workspaces/${ws!.id}/seo-fetch?url=${encodeURIComponent(url.trim())}`);
      // 차단 페이지를 점검하면 엉뚱한 결과가 나오므로 여기서 멈춘다
      if (f.status >= 400) throw new Error(`페이지가 HTTP ${f.status}로 응답했습니다. 자동 수집을 막는 사이트라 점검할 수 없습니다 (검색엔진·AI 봇도 막혔을 수 있으니 방화벽 설정 확인)`);
      setResult({ url: f.url, checks: runChecks(f, extractFacts(f.html)) });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageTitle desc="광고주 페이지 주소를 넣으면 검색엔진(SEO)과 AI 검색(GEO)이 페이지를 잘 읽을 수 있는지 점검합니다. 콘텐츠 품질·외부 언급은 점검하지 않습니다.">SEO·GEO 점검</PageTitle>
      <Card title="페이지 점검">
        <form className="flex flex-col gap-2" onSubmit={(e) => { e.preventDefault(); void run(); }}>
          <div className="flex gap-2">
            <input className={`${inputCls} flex-1`} aria-label="점검할 페이지 주소" placeholder="https://로 시작하는 자사몰 페이지 주소" value={url} onChange={(e) => setUrl(e.target.value)} />
            <Button type="submit" disabled={busy || !url.trim()}>{busy ? "점검 중…" : "점검하기"}</Button>
          </div>
          <p className="text-xs text-muted">
            스마트스토어·브랜드스토어 주소는 점검할 수 없습니다 (네이버가 외부 수집을 막아 결과가 정확하지 않음). 자사몰 페이지를 넣어 주세요.
            <br />서버가 받은 HTML만 봅니다. 자바스크립트로 나중에 그리는 내용은 없는 것으로 나오며, AI 크롤러도 대부분 이렇게 봅니다.
          </p>
          <ErrorText error={error} />
        </form>
      </Card>
      {result && (["SEO", "GEO"] as const).map((g) => {
        const rows = result.checks.filter((c) => c.group === g).sort((a, b) => ORDER[a.level] - ORDER[b.level]);
        const fails = rows.filter((c) => c.level !== "PASS").length;
        return (
          <Card key={g} className="mt-4" title={`${g === "SEO" ? "SEO (검색엔진)" : "GEO (AI 검색)"} · 고칠 것 ${fails}개`}>
            <ul className="divide-y divide-line">
              {rows.map((c) => (
                <li key={c.label} className="flex items-start gap-3 py-2.5 text-[13px]">
                  <span className="w-14 shrink-0"><Badge value={c.level} /></span>
                  <div className="min-w-0 flex-1">
                    <div className="font-medium">{c.label}</div>
                    <div className="break-all text-muted">{c.detail}</div>
                    {c.fix && <div className="mt-0.5 text-ink">→ {c.fix}</div>}
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        );
      })}
    </>
  );
}
