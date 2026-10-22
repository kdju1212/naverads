"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { BulkBar } from "@/components/BulkBar";
import { Col, DataTable } from "@/components/DataTable";
import { DataStatus } from "@/components/DataStatus";
import { Badge, Button, Card, ErrorText, inputCls, PageTitle } from "@/components/ui";
import { api, fmt, Job } from "@/lib/api";
import { changeFor } from "@/lib/changes";
import { ascending, combine, patterns, words } from "@/lib/combine";
import { Keyword, NAdGroup, useNaverData } from "@/lib/naverData";
import { useApp } from "@/lib/store";

const PATTERNS = patterns(4);
const patternLabel = (p: number[]) => p.map((i) => i + 1).join("+");

/** 단어 목록 4개를 고른 조합식대로 띄어쓰기 없이 이어 붙여 등록 목록에 넣는다. */
function KeywordCombiner({ onAdd }: { onAdd: (keywords: string[]) => void }) {
  const [lists, setLists] = useState(["", "", "", ""]);
  const [on, setOn] = useState<Set<string>>(new Set(PATTERNS.filter(ascending).map(patternLabel)));
  const result = combine(lists.map(words), PATTERNS.filter((p) => on.has(patternLabel(p))));
  return (
    <details className="rounded border border-gray-200 p-2">
      <summary className="cursor-pointer text-sm font-medium">키워드 조합기</summary>
      <div className="mt-2 flex flex-col gap-2">
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          {lists.map((v, i) => (
            <textarea key={i} className={`${inputCls} h-24`} aria-label={`단어 목록 ${i + 1}`} placeholder={`${i + 1}번 목록 (한 줄에 하나 또는 쉼표)`}
              value={v} onChange={(e) => setLists((l) => l.map((x, j) => (j === i ? e.target.value : x)))} />
          ))}
        </div>
        {[1, 2, 3, 4].map((len) => {
          const row = PATTERNS.filter((p) => p.length === len).map(patternLabel);
          const all = row.every((k) => on.has(k));
          return (
            <div key={len} className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
              <Button variant="secondary" className="w-24 px-2 py-0.5 text-xs" title={all ? "이 줄 전체 해제" : "이 줄 전체 선택"}
                onClick={() => setOn((o) => { const n = new Set(o); row.forEach((k) => (all ? n.delete(k) : n.add(k))); return n; })}>
                {len}개 조합 {all ? "해제" : "전체"}
              </Button>
              {row.map((k) => (
                <label key={k} className="flex items-center gap-1">
                  <input type="checkbox" checked={on.has(k)}
                    onChange={() => setOn((o) => { const n = new Set(o); if (n.has(k)) n.delete(k); else n.add(k); return n; })} />{k}
                </label>
              ))}
            </div>
          );
        })}
        <div className="flex items-center gap-2">
          <Button variant="secondary" disabled={!result.length} onClick={() => onAdd(result)}>조합 {fmt(result.length)}개 아래 목록에 추가</Button>
          {result.length > 0 && <span className="truncate text-xs text-gray-500">{result.slice(0, 5).join(", ")}{result.length > 5 ? " …" : ""}</span>}
        </div>
      </div>
    </details>
  );
}

interface RelKeyword { keyword: string; pc: number; mobile: number; comp: string }
const qc = (n: number) => (n ? fmt(n) : "10 미만");

/** 광고그룹 하나에 여러 키워드를 붙여넣어 등록 작업을 만든다. 미리보기 화면에서 확인 후 실행.
 * 광고그룹 이름은 캠페인마다 겹칠 수 있어 ID로 지정한다. */
function KeywordAddBar({ groups, campaignName, keywords }: { groups: NAdGroup[]; campaignName: Map<string, string>; keywords: Keyword[] }) {
  const { ws, accountName } = useApp();
  const router = useRouter();
  const [grp, setGrp] = useState("");
  const [text, setText] = useState("");
  const [bid, setBid] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hint, setHint] = useState("");
  const [rel, setRel] = useState<RelKeyword[] | null>(null);
  const [pick, setPick] = useState<Set<string>>(new Set());
  const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);
  const group = groups.find((g) => g.naver_id === grp.trim());
  const label = (g: NAdGroup) => `${accountName(g.ad_account_id)} · ${campaignName.get(g.campaign_naver_id) ?? "-"} > ${g.name}`;

  const searchRel = async () => {
    if (!ws || !group) return;
    setBusy(true);
    setError(null);
    try {
      setRel(await api<RelKeyword[]>(`/workspaces/${ws.id}/keyword-tool?account_id=${group.ad_account_id}&hint=${encodeURIComponent(hint)}`));
      setPick(new Set());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const addLines = (ks: string[]) => {
    const have = new Set(lines.map((l) => l.split("|")[0].trim()));
    setText([...lines, ...ks.filter((k) => !have.has(k))].join("\n"));
  };
  const addPicked = () => {
    addLines([...pick]);
    setPick(new Set());
  };

  const submit = async () => {
    if (!ws || !group) return;
    setBusy(true);
    setError(null);
    try {
      // 줄에 "|입찰가"가 없으면 입찰가 칸 값을 쓴다(그것도 비면 서버가 70원). 이미 있는 키워드는 보관본으로 찾아 실행하지 않는 행으로
      const have = new Set(keywords.filter((k) => k.adgroup_naver_id === group.naver_id).map((k) => k.keyword));
      const changes = lines.map((l) => {
        const ch = changeFor("keyword", group, "create", l.includes("|") || !bid ? l : `${l}|${bid}`);
        return have.has(l.split("|")[0].trim()) ? { ...ch, invalid: "이미 등록된 키워드입니다" } : ch;
      });
      const job = await api<Job>(`/workspaces/${ws.id}/bulk-jobs`, { body: { changes } });
      router.push(`/jobs?id=${job.id}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  };

  return (
    <Card title="키워드 등록" className="mb-3">
      <div className="flex flex-col gap-2">
        <input className={inputCls} aria-label="광고그룹 ID" list="adgroup-ids" placeholder="광고그룹 ID (grp-...) 붙여넣기 또는 선택"
          value={grp} onChange={(e) => setGrp(e.target.value)} />
        <datalist id="adgroup-ids">
          {groups.map((g) => <option key={g.id} value={g.naver_id}>{label(g)}</option>)}
        </datalist>
        {grp.trim() && (
          <p className={`text-xs ${group ? "text-gray-600" : "text-red-600"}`}>
            {group ? label(group) : "목록에 없는 광고그룹 ID입니다 (파워링크 광고그룹 ID인지, 동기화했는지 확인)"}
          </p>
        )}
        <div className="flex flex-wrap items-center gap-2">
          <input className={`${inputCls} w-64`} aria-label="연관 키워드 검색어" placeholder="연관 키워드 찾기 (쉼표로 최대 5개)"
            value={hint} onChange={(e) => setHint(e.target.value)} onKeyDown={(e) => e.key === "Enter" && hint.trim() && searchRel()} />
          <Button variant="secondary" disabled={busy || !group || !hint.trim()} onClick={searchRel}>연관 키워드</Button>
          {!group && <span className="text-xs text-gray-500">광고그룹을 먼저 지정하세요</span>}
        </div>
        {rel && (
          <div className="max-h-72 overflow-auto rounded border border-gray-200">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-gray-50 text-left text-xs text-gray-500">
                <tr><th className="w-8 px-2 py-1.5" /><th>키워드</th><th className="text-right">PC 월 검색</th><th className="text-right">모바일 월 검색</th><th className="px-2 text-right">경쟁</th></tr>
              </thead>
              <tbody>
                {rel.slice(0, 100).map((r) => (
                  <tr key={r.keyword} className="border-t border-gray-100">
                    <td className="px-2 py-1"><input type="checkbox" aria-label={r.keyword} checked={pick.has(r.keyword)}
                      onChange={() => setPick((p) => { const n = new Set(p); if (n.has(r.keyword)) n.delete(r.keyword); else n.add(r.keyword); return n; })} /></td>
                    <td>{r.keyword}</td>
                    <td className="text-right tabular-nums">{qc(r.pc)}</td>
                    <td className="text-right tabular-nums">{qc(r.mobile)}</td>
                    <td className="px-2 text-right">{r.comp}</td>
                  </tr>
                ))}
                {rel.length === 0 && <tr><td colSpan={5} className="py-3 text-center text-gray-500">연관 키워드가 없습니다</td></tr>}
              </tbody>
            </table>
          </div>
        )}
        {rel && rel.length > 0 && (
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setPick(pick.size === Math.min(rel.length, 100) ? new Set() : new Set(rel.slice(0, 100).map((r) => r.keyword)))}>
              {pick.size === Math.min(rel.length, 100) ? "전체 해제" : "전체 선택"}
            </Button>
            <Button variant="secondary" disabled={pick.size === 0} onClick={addPicked}>선택한 {pick.size}개 아래 목록에 추가</Button>
          </div>
        )}
        <KeywordCombiner onAdd={addLines} />
        <textarea className={`${inputCls} h-28`} aria-label="키워드 목록" value={text} onChange={(e) => setText(e.target.value)}
          placeholder={"한 줄에 하나씩. 키워드마다 입찰가를 다르게 하려면 | 뒤에\n여름 원피스|500\n린넨 원피스"} />
        <div className="flex flex-wrap items-center gap-2">
          <input className={`${inputCls} w-56`} inputMode="numeric" aria-label="입찰가" placeholder="입찰가(원) · 비우면 70원"
            value={bid} onChange={(e) => setBid(e.target.value.replace(/[^0-9]/g, ""))} />
          <Button disabled={busy || !group || lines.length === 0} onClick={submit}>{lines.length}개 등록 미리보기</Button>
          <ErrorText error={error} />
        </div>
      </div>
    </Card>
  );
}

export default function KeywordsPage() {
  const { product, accountName } = useApp();
  const shoppingOnly = product === "SHOPPING";
  const data = useNaverData();
  const campaignName = useMemo(() => new Map(data.campaigns.map((c) => [c.naver_id, c.name])), [data.campaigns]);
  const groups = useMemo(() => data.adgroups.filter((g) => g.adgroup_type === "WEB_SITE"), [data.adgroups]);
  const [sel, setSel] = useState<Set<string>>(new Set());
  const rows = data.keywords;
  const groupName = useMemo(() => new Map(data.adgroups.map((g) => [g.naver_id, g.name])), [data.adgroups]);

  if (shoppingOnly) {
    return (
      <>
        <PageTitle>키워드</PageTitle>
        <Card><p className="text-sm text-gray-600">키워드는 파워링크 전용입니다. 쇼핑검색광고는 <b>소재·상품소재</b> 메뉴에서 상품소재 단위로 관리합니다.</p></Card>
      </>
    );
  }

  const cols: Col<Keyword>[] = [
    { key: "acc", label: "광고주", value: (r) => accountName(r.ad_account_id) },
    { key: "grp", label: "광고그룹", value: (r) => groupName.get(r.adgroup_naver_id) ?? null },
    { key: "kw", label: "키워드", value: (r) => r.keyword },
    { key: "status", label: "상태", value: (r) => r.status, render: (r) => <Badge value={r.status} /> },
    { key: "bid", label: "입찰가", num: true, value: (r) => r.bid_amt, render: (r) => (r.use_group_bid ? "그룹 입찰가" : fmt(r.bid_amt, "원")) },
  ];
  const selected = rows.filter((r) => sel.has(r.id));
  return (
    <>
      <PageTitle desc="파워링크 키워드를 대량 등록·삭제하고 ON/OFF·입찰가를 대량 변경합니다. 자동입찰은 왼쪽 메뉴 '자동입찰'에서 설정합니다.">키워드 (파워링크)</PageTitle>
      <DataStatus data={data} />
      <KeywordAddBar groups={groups} campaignName={campaignName} keywords={rows} />
      <DataTable rows={rows} cols={cols} selected={sel} onSelect={setSel} loading={data.loading && !rows.length}
        toolbar={<BulkBar entityType="keyword" rows={selected} numberField={{ field: "bid_amt", label: "입찰가" }} deletable />} />
    </>
  );
}
