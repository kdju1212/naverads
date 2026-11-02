"use client";

import { useEffect, useState } from "react";
import { Button, Card, ErrorText, inputCls, PageTitle } from "@/components/ui";
import { api, fmt, inspectLabel } from "@/lib/api";
import { useApp } from "@/lib/store";
import { useFetch } from "@/lib/useFetch";

// 서버: backend/src/app/place.py (계획 → 승인 → 적용). 유지보수: docs/PLACE_ADS_MAINTENANCE.md
type Change = { ad_account_id: number; action: string; params: Record<string, unknown> };
type Summary = { label: string; target: string; before: string; after: string; spend_text: string; notes: string[];
  safety?: { total_after?: number; daily_budget_limit?: number | null; max_bid?: number | null } };
type Plan = { approval_id: number; expires_in_minutes: number; summary: Summary & { web_required?: boolean } };
type Result = { status: "SUCCESS" | "PARTIAL" | "FAILED"; steps: { step: string; ok: boolean; error?: string }[]; error: string | null; notice: string | null };
type Ad = { id: string; type: string; linked: boolean; on: boolean; review: string; text: string };
type Group = { id: string; name: string; on: boolean; advoost: boolean; bid: number | null; serving: string | null; ads: Ad[] | null;
  negative_keywords: { id: string; keyword: string }[] | null };
type Campaign = { id: string; name: string; on: boolean; daily_budget: number | null; groups: Group[];
  last_7_days: { impressions: number; clicks: number; cost: number } };
type Overview = { businesses: { id: string; name: string; place_id: string; review: string }[]; campaigns: Campaign[];
  limits: { daily_budget: [number, number]; bid: [number, number] }; stats_until: string; notice: string; partial: string | false };

const digits = (v: string) => v.replace(/[^0-9]/g, "");

const TERMS: [string, string, string][] = [
  ["업체 (비즈채널)", "광고할 가게. 네이버 스마트플레이스에 등록된 가게를 광고 계정에 연결해 둔 것이에요.", "예: '행복 분식 강남점'"],
  ["광고 내용 (소재)", "검색 결과에 실제로 보이는 광고 문구·사진이에요.", "예: '떡볶이 포장 10% 할인'"],
  ["ADVoost 플레이스", "네이버가 가게 정보로 광고를 자동으로 만들고 입찰가·검색어를 알아서 조절해요. 하루예산만 정하면 돼요. 스마트플레이스에 사진이 1장 이상 있어야 하고, 병원·의원은 쓸 수 없어요.", "예: '하루 1만 원 안에서 알아서'"],
  ["하루예산", "하루에 쓸 수 있는 최대 금액이에요. 이 금액을 넘지 않게 광고가 멈춰요.", "예: 10,000원 → 한 달(31일) 최대 310,000원"],
  ["입찰가", "누군가 광고를 한 번 누를 때 낼 수 있는 최대 금액이에요(ADVoost는 자동).", "예: 200원"],
  ["제외검색어", "이 말로 검색할 때는 광고를 보여 주지 않게 막는 단어예요(ADVoost는 사용 불가).", "예: 배달 안 하는 가게라면 '배달'"],
  ["검토", "네이버가 광고를 확인하는 단계예요. 통과해야 광고가 나가요.", "만든 직후에는 '검토 중'일 수 있어요"],
];

export default function PlacePage() {
  const { ws, accounts, selected } = useApp();
  const [picked, setPicked] = useState<number | null>(null);
  const acc = picked ?? selected[0] ?? accounts[0]?.id ?? null;
  const { data, error, reload: load } = useFetch<Overview>(ws && acc != null ? `/workspaces/${ws.id}/place?ad_account_id=${acc}` : null);
  const [pending, setPending] = useState<Change | null>(null); // 승인 패널에 띄울 변경

  const ask = (action: string, params: Record<string, unknown>) => acc != null && setPending({ ad_account_id: acc, action, params });
  // 끄기는 승인 없이 바로(긴급 중지). 서버: POST /workspaces/{ws}/stop, 기록이 남는다
  const stop = async (entity_type: string, naver_id: string, name: string) => {
    if (!ws || acc == null || !confirm(`'${name}' 광고를 지금 끌까요? 검색 결과에서 빠지기까지 조금 걸릴 수 있어요.`)) return;
    try { await api(`/workspaces/${ws.id}/stop`, { body: { ad_account_id: acc, entity_type, naver_id } }); await load(); }
    catch (e) { alert((e as Error).message); }
  };

  return (
    <>
      <PageTitle desc="네이버 지도·플레이스 검색 결과에 우리 가게를 광고로 보여 줘요. 바꾸기 전에 항상 내용을 보여 드리고 승인을 받아요.">플레이스광고</PageTitle>
      <div className="mb-4 flex items-center gap-2">
        <select className={inputCls} value={acc ?? ""} onChange={(e) => { setPicked(Number(e.target.value)); setPending(null); }} aria-label="광고 계정">
          {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
        <Button variant="secondary" onClick={load}>새로 읽기</Button>
      </div>
      <ErrorText error={error} />

      <details className="mb-4 rounded-card border border-line bg-surface p-3 text-[13px]">
        <summary className="cursor-pointer font-semibold">처음이신가요? 용어 쉽게 보기</summary>
        <dl className="mt-2 grid gap-2">
          {TERMS.map(([t, d, ex]) => <div key={t}><dt className="font-semibold">{t}</dt><dd className="text-muted">{d} <span className="text-faint">{ex}</span></dd></div>)}
        </dl>
      </details>

      {pending && <Approve change={pending} onClose={() => setPending(null)} onDone={load} />}
      {/* 승인 카드가 떠 있어도 만들기 단계는 유지해 '수정'을 누르면 그대로 고칠 수 있게 */}
      {data && <div hidden={!!pending}><CreateFlow data={data} onAsk={ask} /></div>}
      {data && <Status data={data} onAsk={ask} onStop={stop} busy={!!pending} />}
    </>
  );
}

/** 새로 만들기: 업체 선택 → 예산 → 광고 내용 확인 → 최종 승인(승인 패널) */
function CreateFlow({ data, onAsk }: { data: Overview; onAsk: (a: string, p: Record<string, unknown>) => void }) {
  const [step, setStep] = useState(0);
  const [f, setF] = useState({ business_id: "", daily_budget: "10000", advoost: true, bid: "200", ad_text: "" });
  const [lo, hi] = data.limits.daily_budget;
  const [blo, bhi] = data.limits.bid;
  const budget = Number(f.daily_budget || 0);
  const biz = data.businesses.find((b) => b.id === f.business_id);
  const budgetOk = budget >= lo && budget <= hi && budget % 10 === 0;
  const bidOk = f.advoost || (Number(f.bid) >= blo && Number(f.bid) <= bhi && Number(f.bid) % 10 === 0);
  const next = [!!biz, budgetOk && bidOk, true][step];
  const finish = () => onAsk("create", f.advoost
    ? { business_id: f.business_id, daily_budget: budget, use_advoost: true }
    : { business_id: f.business_id, daily_budget: budget, use_advoost: false, bid: Number(f.bid), ...(f.ad_text ? { ad_text: f.ad_text } : {}) });

  if (!data.businesses.length) return (
    <Card title="새 플레이스광고 만들기" className="mb-4">
      <p className="text-sm text-muted">이 광고 계정에 연결된 가게(플레이스 비즈채널)가 없어요. 네이버 광고관리 &gt; 비즈채널에서 스마트플레이스 가게를 먼저 연결해 주세요.</p>
    </Card>
  );
  return (
    <Card title="새 플레이스광고 만들기" className="mb-4">
      <ol className="mb-3 flex gap-3 text-xs text-faint">
        {["1 업체 선택", "2 예산", "3 광고 내용 확인", "4 최종 승인"].map((s, i) => <li key={s} className={i === step ? "font-semibold text-primary" : ""}>{s}</li>)}
      </ol>
      {step === 0 && (
        <fieldset className="grid gap-1 text-sm"><legend className="mb-1 text-muted">어느 가게를 광고할까요?</legend>
          {data.businesses.map((b) => (
            <label key={b.id} className="flex items-center gap-2">
              <input type="radio" name="biz" checked={f.business_id === b.id} onChange={() => setF({ ...f, business_id: b.id })} />
              {b.name} <span className="text-xs text-faint">검토: {inspectLabel(b.review)}</span>
            </label>
          ))}
        </fieldset>
      )}
      {step === 1 && (
        <div className="grid gap-3 text-sm">
          <label className="grid gap-1">하루예산 (하루에 쓸 최대 금액, {fmt(lo)}~{fmt(hi)}원)
            <input className={`${inputCls} w-48`} inputMode="numeric" value={f.daily_budget} onChange={(e) => setF({ ...f, daily_budget: digits(e.target.value) })} />
            <span className="text-xs text-faint">한 달(31일) 최대 {fmt(budget * 31)}원</span>
          </label>
          <fieldset className="grid gap-1"><legend className="text-muted">광고 방식</legend>
            <label className="flex items-start gap-2"><input type="radio" checked={f.advoost} onChange={() => setF({ ...f, advoost: true })} />
              <span><b>ADVoost (추천)</b> — 광고 문구·입찰가·검색어를 네이버가 알아서. 가게 사진이 1장 이상 있어야 하고 병원·의원은 안 돼요.</span></label>
            <label className="flex items-start gap-2"><input type="radio" checked={!f.advoost} onChange={() => setF({ ...f, advoost: false })} />
              <span><b>직접 정하기</b> — 입찰가와 광고 문구를 직접 정해요.</span></label>
          </fieldset>
          {!f.advoost && (
            <label className="grid gap-1">입찰가 (광고를 한 번 누를 때 낼 최대 금액, {fmt(blo)}~{fmt(bhi)}원)
              <input className={`${inputCls} w-48`} inputMode="numeric" value={f.bid} onChange={(e) => setF({ ...f, bid: digits(e.target.value) })} />
            </label>
          )}
          {!budgetOk && <p className="text-xs text-danger">하루예산은 {fmt(lo)}~{fmt(hi)}원, 10원 단위예요.</p>}
          {!bidOk && <p className="text-xs text-danger">입찰가는 {fmt(blo)}~{fmt(bhi)}원, 10원 단위예요.</p>}
        </div>
      )}
      {step === 2 && (
        <div className="grid gap-2 text-sm">
          {f.advoost
            ? <p>광고 내용은 <b>{biz?.name}</b>의 스마트플레이스 정보(이름·사진·주소·영업시간)로 네이버가 자동으로 만들어요. 따로 쓸 필요가 없어요.</p>
            : <label className="grid gap-1">광고 문구 (비우면 가게 이름)
                <input className={`${inputCls} w-full`} maxLength={100} placeholder="예: 떡볶이 포장 10% 할인" value={f.ad_text} onChange={(e) => setF({ ...f, ad_text: e.target.value })} />
              </label>}
          <p className="text-xs text-faint">다음 단계에서 바뀔 내용과 최대 지출을 확인하고 승인해요. 승인 전에는 네이버에 아무것도 만들어지지 않아요.</p>
        </div>
      )}
      <div className="mt-3 flex gap-2">
        {step > 0 && <Button variant="secondary" onClick={() => setStep(step - 1)}>이전</Button>}
        {step < 2 ? <Button disabled={!next} onClick={() => setStep(step + 1)}>다음</Button> : <Button onClick={finish}>4 최종 승인으로</Button>}
      </div>
    </Card>
  );
}

/** 계획을 만들어 보여 주고, 사장님이 승인하면 같은 내용으로 적용한다 */
function Approve({ change, onClose, onDone }: { change: Change; onClose: () => void; onDone: () => void }) {
  const { ws } = useApp();
  const [plan, setPlan] = useState<Plan | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!ws) return;
    api<Plan>(`/workspaces/${ws.id}/place/plan`, { body: change }).then(setPlan, (e) => setError((e as Error).message));
  }, [ws, change]);

  const approve = async () => {
    if (!ws || !plan) return;
    setBusy(true);
    try {
      // 계정 하루예산 합계가 늘 수 있는 변경은 웹 승인으로만 실행된다(이 카드가 승인 화면: 대상·전후·지출·안내를 보여 줌)
      setResult(plan.summary.web_required
        ? (await api<{ place: Result }>(`/workspaces/${ws.id}/approvals/${plan.approval_id}/approve`, { method: "POST" })).place
        : await api<Result>(`/workspaces/${ws.id}/place/apply`, { body: { approval_id: plan.approval_id, change } }));
      onDone();
    } catch (e) { setError((e as Error).message); }
    setBusy(false);
  };

  // 수정·취소 모두 이 승인 요청은 거절로 기록하고 닫는다(수정은 만들기 단계 내용이 남아 있어 고친 뒤 다시 승인)
  const cancel = async (close: boolean) => {
    if (ws && plan) await api(`/workspaces/${ws.id}/place/cancel`, { body: { approval_id: plan.approval_id } }).catch(() => {});
    onClose();
    if (!close) window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const s = plan?.summary;
  const tone = { SUCCESS: "text-accent", PARTIAL: "text-warning", FAILED: "text-danger" };
  const label = { SUCCESS: "완료했어요", PARTIAL: "일부만 됐어요", FAILED: "하지 못했어요" };
  return (
    <Card title={s ? `확인해 주세요: ${s.label}` : "내용 확인 중…"} className="mb-4">
      <ErrorText error={error} />
      {s && !result && (
        <>
          <table className="mb-2 text-sm"><tbody>
            {([["대상", s.target], ["지금", s.before], ["바뀐 뒤", s.after], ["최대 지출", s.spend_text]] as const).map(([k, v]) => (
              <tr key={k}><th className="pr-4 text-left font-medium text-muted">{k}</th><td>{v}</td></tr>))}
          </tbody></table>
          {s.notes.map((n) => <p key={n} className="text-xs text-faint">· {n}</p>)}
          <p className="mt-1 text-xs text-faint">이 승인은 {plan!.expires_in_minutes}분 동안, 한 번만 쓸 수 있어요.</p>
          {s.safety?.max_bid != null && <p className="text-xs text-muted">이 계정의 클릭당 최대 입찰가 {s.safety.max_bid.toLocaleString("ko-KR")}원</p>}
          <div className="mt-3 flex gap-2">
            <Button disabled={busy} onClick={approve}>{busy ? "적용 중…" : "승인하고 적용"}</Button>
            <Button variant="secondary" disabled={busy} onClick={() => cancel(false)}>수정하기</Button>
            <Button variant="ghost" disabled={busy} onClick={() => cancel(true)}>취소</Button>
          </div>
        </>
      )}
      {result && (
        <>
          <p className={`font-semibold ${tone[result.status]}`}>{label[result.status]}</p>
          <ul className="my-2 text-sm">{result.steps.map((x) => <li key={x.step}>{x.ok ? "✓" : "✗"} {x.step}{x.error && <span className="text-danger"> — {x.error}</span>}</li>)}</ul>
          {result.error && <p className="text-sm text-danger">{result.error}</p>}
          {result.notice && <p className="text-xs text-muted">{result.notice}</p>}
          <Button className="mt-2" variant="secondary" onClick={onClose}>닫기</Button>
        </>
      )}
    </Card>
  );
}

function Status({ data, onAsk, onStop, busy }: { data: Overview; onAsk: (a: string, p: Record<string, unknown>) => void;
  onStop: (type: string, id: string, name: string) => void; busy: boolean }) {
  const ask = (a: string, p: Record<string, unknown>) => !busy && onAsk(a, p);
  const askNumber = (msg: string, a: string, key: string, p: Record<string, unknown>) => {
    const v = window.prompt(msg);
    if (v && digits(v)) ask(a, { ...p, [key]: Number(digits(v)) });
  };
  return (
    <Card title="지금 상태">
      <p className="mb-2 text-xs text-faint">{data.notice} 성과는 {data.stats_until}까지.</p>
      {data.partial && <p className="mb-2 text-xs text-warning">{data.partial}</p>}
      {!data.campaigns.length && <p className="text-sm text-muted">아직 플레이스광고가 없어요. 위에서 새로 만들어 보세요.</p>}
      {data.campaigns.map((c) => (
        <section key={c.id} className="mb-4 border-t border-line pt-3">
          <div className="flex flex-wrap items-center gap-2">
            <b>{c.name}</b><span className="text-xs">{c.on ? "켜짐" : "꺼짐"}</span>
            <span className="text-xs text-muted">하루예산 {c.daily_budget == null ? "없음" : `${fmt(c.daily_budget)}원`}</span>
            <span className="text-xs text-faint">지난 7일 노출 {fmt(c.last_7_days.impressions)} · 클릭 {fmt(c.last_7_days.clicks)} · 비용 {fmt(c.last_7_days.cost)}원</span>
            <Button variant="secondary" onClick={() => askNumber("새 하루예산(원)", "set_budget", "daily_budget", { campaign_id: c.id })}>하루예산 바꾸기</Button>
            {c.on ? <Button variant="danger" onClick={() => onStop("campaign", c.id, c.name)}>바로 끄기</Button>
              : <Button variant="secondary" onClick={() => ask("turn_on", { target_type: "campaign", target_id: c.id })}>켜기</Button>}
          </div>
          {c.groups.map((g) => (
            <div key={g.id} className="ml-4 mt-2 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <span>{g.name}</span><span className="text-xs">{g.on ? "켜짐" : "꺼짐"}</span>
                <span className="text-xs text-muted">{g.advoost ? "ADVoost (입찰가·검색어 자동)" : `입찰가 ${fmt(g.bid)}원`}</span>
                {g.on ? <Button variant="ghost" onClick={() => onStop("adgroup", g.id, g.name)}>바로 끄기</Button>
                  : <Button variant="ghost" onClick={() => ask("turn_on", { target_type: "adgroup", target_id: g.id })}>켜기</Button>}
                <Button variant="ghost" onClick={() => ask("set_advoost", { adgroup_id: g.id, on: !g.advoost })}>ADVoost {g.advoost ? "끄기" : "켜기"}</Button>
                {!g.advoost && <Button variant="ghost" onClick={() => askNumber("새 입찰가(원)", "set_bid", "bid", { adgroup_id: g.id })}>입찰가 바꾸기</Button>}
              </div>
              {g.ads && <ul className="ml-4 text-xs text-muted">{g.ads.map((a) => (
                <li key={a.id}>{a.linked ? "ADVoost 자동 광고" : `광고: ${a.text || "(문구 없음)"}`} · {a.on ? "켜짐" : "꺼짐"} · 검토 {inspectLabel(a.review)}</li>))}</ul>}
              {g.advoost
                ? <p className="ml-4 text-xs text-faint">ADVoost가 켜져 있어 제외검색어·입찰가·광고 직접 추가는 쓸 수 없어요.</p>
                : <div className="ml-4 flex flex-wrap items-center gap-1 text-xs">
                    제외검색어: {(g.negative_keywords ?? []).map((k) => (
                      <button key={k.id} className="rounded border border-line px-1 hover:bg-subtle" title="삭제" onClick={() => ask("remove_negative_keyword", { adgroup_id: g.id, keyword_id: k.id })}>{k.keyword} ×</button>))}
                    <Button variant="ghost" onClick={() => { const v = window.prompt("광고를 보여 주지 않을 검색어 (예: 배달)"); if (v?.trim()) ask("add_negative_keyword", { adgroup_id: g.id, keyword: v.trim() }); }}>추가</Button>
                  </div>}
            </div>
          ))}
        </section>
      ))}
    </Card>
  );
}
