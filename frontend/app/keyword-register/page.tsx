"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { DataStatus } from "@/components/DataStatus";
import { Button, Card, ErrorText, inputCls, PageTitle } from "@/components/ui";
import { api, downloadCsv, fmt, Job } from "@/lib/api";
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
    <details open className="rounded border border-line p-2">
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
              <Button variant="secondary" className="w-28" title={all ? "이 줄 전체 해제" : "이 줄 전체 선택"}
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
        <textarea readOnly className={`${inputCls} h-40 bg-subtle`} aria-label="조합 결과" placeholder="조합 결과가 여기에 나옵니다"
          value={result.join("\n")} />
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" disabled={!result.length} onClick={() => onAdd(result)}>조합 {fmt(result.length)}개 아래 목록에 추가</Button>
          <Button variant="secondary" disabled={!result.length} onClick={() => downloadCsv([["키워드"], ...result.map((k) => [k])], "keyword_combinations.csv")}>엑셀 다운로드</Button>
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
    <Card title="키워드 등록">
      <div className="flex flex-col gap-2">
        <input className={inputCls} aria-label="광고그룹 ID" list="adgroup-ids" placeholder="광고그룹 ID (grp-...) 붙여넣기 또는 선택"
          value={grp} onChange={(e) => setGrp(e.target.value)} />
        <datalist id="adgroup-ids">
          {groups.map((g) => <option key={g.id} value={g.naver_id}>{label(g)}</option>)}
        </datalist>
        {grp.trim() && (
          <p className={`text-xs ${group ? "text-muted" : "text-danger"}`}>
            {group ? label(group) : "목록에 없는 광고그룹 ID입니다 (파워링크 광고그룹 ID인지, 동기화했는지 확인)"}
          </p>
        )}
        <div className="flex flex-wrap items-center gap-2">
          <input className={`${inputCls} w-64`} aria-label="연관 키워드 검색어" placeholder="연관 키워드 찾기 (쉼표로 최대 5개)"
            value={hint} onChange={(e) => setHint(e.target.value)} onKeyDown={(e) => e.key === "Enter" && hint.trim() && searchRel()} />
          <Button variant="secondary" disabled={busy || !group || !hint.trim()} onClick={searchRel}>연관 키워드</Button>
          {!group && <span className="text-xs text-faint">광고그룹을 먼저 지정하세요</span>}
        </div>
        {rel && (
          <div className="max-h-72 overflow-auto rounded border border-line">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-subtle text-left text-xs text-faint">
                <tr><th className="w-8 px-2 py-1.5" /><th>키워드</th><th className="text-right">PC 월 검색</th><th className="text-right">모바일 월 검색</th><th className="px-2 text-right">경쟁</th></tr>
              </thead>
              <tbody>
                {rel.slice(0, 100).map((r) => (
                  <tr key={r.keyword} className="border-t border-line">
                    <td className="px-2 py-1"><input type="checkbox" aria-label={r.keyword} checked={pick.has(r.keyword)}
                      onChange={() => setPick((p) => { const n = new Set(p); if (n.has(r.keyword)) n.delete(r.keyword); else n.add(r.keyword); return n; })} /></td>
                    <td>{r.keyword}</td>
                    <td className="text-right tabular-nums">{qc(r.pc)}</td>
                    <td className="text-right tabular-nums">{qc(r.mobile)}</td>
                    <td className="px-2 text-right">{r.comp}</td>
                  </tr>
                ))}
                {rel.length === 0 && <tr><td colSpan={5} className="py-3 text-center text-faint">연관 키워드가 없습니다</td></tr>}
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

export default function KeywordRegisterPage() {
  const { product } = useApp();
  const data = useNaverData();
  const campaignName = useMemo(() => new Map(data.campaigns.map((c) => [c.naver_id, c.name])), [data.campaigns]);
  const groups = useMemo(() => data.adgroups.filter((g) => g.adgroup_type === "WEB_SITE"), [data.adgroups]);

  if (product === "SHOPPING") {
    return (
      <>
        <PageTitle>키워드 등록</PageTitle>
        <Card><p className="text-sm text-muted">키워드는 파워링크 전용입니다.</p></Card>
      </>
    );
  }
  return (
    <>
      <PageTitle desc="광고그룹 하나를 지정해 키워드를 여러 개 등록합니다. 연관 키워드 찾기와 키워드 조합기로 목록을 만들 수 있고, 미리보기에서 확인 후 실행합니다.">키워드 등록 (파워링크)</PageTitle>
      <DataStatus data={data} />
      <KeywordAddBar groups={groups} campaignName={campaignName} keywords={data.keywords} />
    </>
  );
}
