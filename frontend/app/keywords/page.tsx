"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { BulkBar } from "@/components/BulkBar";
import { Col, DataTable } from "@/components/DataTable";
import { Badge, Button, Card, ErrorText, inputCls, PageTitle } from "@/components/ui";
import { AdGroup, api, Campaign, Change, fmt, Job } from "@/lib/api";
import { useApp } from "@/lib/store";
import { useFetch } from "@/lib/useFetch";

interface Keyword { id: number; ad_account_id: number; adgroup_id: number; naver_id: string; keyword: string; status: string; bid_amt: number; use_group_bid: boolean }
interface AutoBid { id: number; keyword_id: number; device: "PC" | "MOBILE"; target_rank: number; max_bid: number; enabled: boolean; last_run_at: string | null; last_result: string | null }

const DEVICE_LABEL = { PC: "PC", MOBILE: "모바일" };

/** 선택한 키워드에 목표 순위 자동입찰을 설정·해제하고, 지금 실행한다. 매시 정각에도 자동 실행된다. */
function AutoBidBar({ ids, onDone }: { ids: number[]; onDone: () => void }) {
  const { ws } = useApp();
  const router = useRouter();
  const [device, setDevice] = useState<"PC" | "MOBILE">("PC");
  const [rank, setRank] = useState("3");
  const [maxBid, setMaxBid] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const call = async (path: string, body: unknown, method = "POST") => {
    if (!ws) return;
    setBusy(true);
    setError(null);
    try {
      const r = await api<{ job_ids?: number[] }>(`/workspaces/${ws.id}/auto-bids${path}`, { method, body });
      onDone();
      if (r.job_ids?.length) router.push(`/jobs?id=${r.job_ids[0]}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const none = busy || ids.length === 0;
  const ranks = device === "PC" ? 10 : 5;
  return (
    <div className="flex flex-wrap items-center gap-2">
      {error && <span role="alert" className="text-xs text-red-600">{error}</span>}
      <select className={inputCls} aria-label="기기" value={device}
        onChange={(e) => { const d = e.target.value as "PC" | "MOBILE"; setDevice(d); if (d === "MOBILE" && Number(rank) > 5) setRank("5"); }}>
        <option value="PC">PC</option>
        <option value="MOBILE">모바일</option>
      </select>
      <select className={inputCls} aria-label="목표 순위" value={rank} onChange={(e) => setRank(e.target.value)}>
        {Array.from({ length: ranks }, (_, i) => <option key={i + 1} value={i + 1}>{i + 1}위</option>)}
      </select>
      <input className={`${inputCls} w-32`} inputMode="numeric" placeholder="최대 입찰가(원)" aria-label="최대 입찰가"
        value={maxBid} onChange={(e) => setMaxBid(e.target.value.replace(/[^0-9]/g, ""))} />
      <Button disabled={none || !maxBid}
        onClick={() => call("", { keyword_ids: ids, device, target_rank: Number(rank), max_bid: Number(maxBid) }, "PUT")}>자동입찰 설정</Button>
      <Button variant="secondary" disabled={none} onClick={() => call("/run", { keyword_ids: ids })}>지금 실행</Button>
      <Button variant="danger" disabled={none} onClick={() => confirm(`${ids.length}개 키워드의 자동입찰을 해제할까요?`) && call("/delete", { keyword_ids: ids })}>해제</Button>
    </div>
  );
}

interface RelKeyword { keyword: string; pc: number; mobile: number; comp: string }
const qc = (n: number) => (n ? fmt(n) : "10 미만");

/** 광고그룹 하나에 여러 키워드를 붙여넣어 등록 작업을 만든다. 미리보기 화면에서 확인 후 실행.
 * 광고그룹 이름은 캠페인마다 겹칠 수 있어 ID로 지정한다. */
function KeywordAddBar({ groups, campaignName }: { groups: AdGroup[]; campaignName: Map<number, string> }) {
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
  const label = (g: AdGroup) => `${accountName(g.ad_account_id)} · ${campaignName.get(g.campaign_id) ?? "-"} > ${g.name}`;

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

  const addPicked = () => {
    const have = new Set(lines.map((l) => l.split("|")[0].trim()));
    setText([...lines, ...[...pick].filter((k) => !have.has(k))].join("\n"));
    setPick(new Set());
  };

  const submit = async () => {
    if (!ws) return;
    setBusy(true);
    setError(null);
    try {
      // 줄에 "|입찰가"가 없으면 입찰가 칸 값을 쓴다(그것도 비면 광고그룹 입찰가)
      const changes: Change[] = lines.map((l) => ({ entity_type: "keyword", naver_id: grp.trim(), field: "create",
        value: l.includes("|") || !bid ? l : `${l}|${bid}` }));
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
        <textarea className={`${inputCls} h-28`} aria-label="키워드 목록" value={text} onChange={(e) => setText(e.target.value)}
          placeholder={"한 줄에 하나씩. 키워드마다 입찰가를 다르게 하려면 | 뒤에\n여름 원피스|500\n린넨 원피스"} />
        <div className="flex flex-wrap items-center gap-2">
          <input className={`${inputCls} w-56`} inputMode="numeric" aria-label="입찰가" placeholder={`입찰가(원) · 비우면 광고그룹 ${group ? fmt(group.bid_amt, "원") : "입찰가"}`}
            value={bid} onChange={(e) => setBid(e.target.value.replace(/[^0-9]/g, ""))} />
          <Button disabled={busy || !group || lines.length === 0} onClick={submit}>{lines.length}개 등록 미리보기</Button>
          <ErrorText error={error} />
        </div>
      </div>
    </Card>
  );
}

export default function KeywordsPage() {
  const { ws, query, product, accountName } = useApp();
  const shoppingOnly = product === "SHOPPING";
  const kws = useFetch<Keyword[]>(ws && !shoppingOnly ? `/workspaces/${ws.id}/keywords${query()}` : null);
  const groups = useFetch<AdGroup[]>(ws && !shoppingOnly ? `/workspaces/${ws.id}/adgroups${query({ product: "WEB_SITE" })}` : null);
  const autoBids = useFetch<AutoBid[]>(ws && !shoppingOnly ? `/workspaces/${ws.id}/auto-bids` : null);
  const camps = useFetch<Campaign[]>(ws && !shoppingOnly ? `/workspaces/${ws.id}/campaigns${query({ product: "WEB_SITE" })}` : null);
  const campaignName = useMemo(() => new Map((camps.data ?? []).map((c) => [c.id, c.name])), [camps.data]);
  const [sel, setSel] = useState<Set<number>>(new Set());
  const rows = useMemo(() => kws.data ?? [], [kws.data]);
  const groupName = useMemo(() => new Map((groups.data ?? []).map((g) => [g.id, g.name])), [groups.data]);
  const rule = useMemo(() => new Map((autoBids.data ?? []).map((r) => [r.keyword_id, r])), [autoBids.data]);

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
    { key: "grp", label: "광고그룹", value: (r) => groupName.get(r.adgroup_id) ?? null },
    { key: "kw", label: "키워드", value: (r) => r.keyword },
    { key: "status", label: "상태", value: (r) => r.status, render: (r) => <Badge value={r.status} /> },
    { key: "bid", label: "입찰가", num: true, value: (r) => r.bid_amt, render: (r) => (r.use_group_bid ? "그룹 입찰가" : fmt(r.bid_amt, "원")) },
    {
      key: "auto", label: "자동입찰", value: (r) => rule.get(r.id)?.target_rank ?? null,
      render: (r) => {
        const a = rule.get(r.id);
        if (!a) return <span className="text-gray-400">-</span>;
        return (
          <div className="text-xs">
            <div>{DEVICE_LABEL[a.device]} {a.target_rank}위 · 최대 {fmt(a.max_bid, "원")}</div>
            {a.last_result && <div className="text-gray-500" title={a.last_run_at ?? undefined}>{a.last_result}</div>}
          </div>
        );
      },
    },
  ];
  const selected = rows.filter((r) => sel.has(r.id));
  return (
    <>
      <PageTitle desc="파워링크 키워드를 대량 등록·삭제하고 ON/OFF·입찰가를 대량 변경합니다. 자동입찰은 네이버 '순위별 예상 입찰가'로 매시 정각에 입찰가를 맞추며 최대 입찰가를 넘지 않습니다.">키워드 (파워링크)</PageTitle>
      <ErrorText error={kws.error ?? autoBids.error} />
      <KeywordAddBar groups={groups.data ?? []} campaignName={campaignName} />
      <DataTable rows={rows} cols={cols} selected={sel} onSelect={setSel} loading={kws.loading}
        toolbar={
          <div className="flex flex-col gap-2">
            <BulkBar entityType="keyword" rows={selected} numberField={{ field: "bid_amt", label: "입찰가" }} deletable />
            <AutoBidBar ids={selected.map((r) => r.id)} onDone={() => { autoBids.reload(); kws.reload(); }} />
          </div>
        } />
    </>
  );
}
