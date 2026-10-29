"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, ErrorText, inputCls } from "@/components/ui";
import { api, Change, Job, PRODUCT_LABEL } from "@/lib/api";
import { NCampaign } from "@/lib/naverData";
import { useApp } from "@/lib/store";
import { useFetch } from "@/lib/useFetch";

const digits = (v: string) => v.replace(/[^0-9]/g, "");
const CHANNEL_TP: Record<string, string> = { WEB_SITE: "SITE", SHOPPING: "MALL" }; // 쇼핑몰 채널은 MALL(실계정 10/29)

/** 등록 작업 미리보기를 만들고 작업 화면으로 넘긴다(실행·예약은 거기서). */
function usePreview() {
  const { ws } = useApp();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submit = async (change: Change) => {
    if (!ws) return;
    setBusy(true);
    setError(null);
    try {
      const job = await api<Job>(`/workspaces/${ws.id}/bulk-jobs`, { body: { changes: [change] } });
      router.push(`/jobs?id=${job.id}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  };
  return { busy, error, submit };
}

export function CampaignCreate() {
  const { accounts, product } = useApp();
  const [acc, setAcc] = useState("");
  const [tp, setTp] = useState(product || "WEB_SITE");
  const [name, setName] = useState("");
  const [budget, setBudget] = useState("");
  const { busy, error, submit } = usePreview();
  const accountId = Number(acc || accounts[0]?.id);
  return (
    <details className="mt-3 rounded-panel border border-line bg-surface p-3">
      <summary className="cursor-pointer text-sm font-medium">새 캠페인 만들기</summary>
      <form className="mt-3 flex flex-wrap items-end gap-2" onSubmit={(e) => {
        e.preventDefault();
        submit({ entity_type: "campaign", naver_id: tp, field: "create", value: `${name.trim()}|${budget}`, ad_account_id: accountId, product: tp });
      }}>
        <label className="text-sm">광고 계정
          <select className={`${inputCls} mt-1 block`} value={acc || accounts[0]?.id || ""} onChange={(e) => setAcc(e.target.value)}>
            {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
        </label>
        <label className="text-sm">유형
          <select className={`${inputCls} mt-1 block`} value={tp} onChange={(e) => setTp(e.target.value as typeof tp)}>
            {Object.entries(PRODUCT_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label className="text-sm">캠페인 이름 (30자)
          <input className={`${inputCls} mt-1 block`} required maxLength={30} value={name} onChange={(e) => setName(e.target.value.replace("|", ""))} />
        </label>
        <label className="text-sm">일예산 (원, 10원 단위)
          <input className={`${inputCls} mt-1 block w-40`} required inputMode="numeric" value={budget} onChange={(e) => setBudget(digits(e.target.value))} />
        </label>
        <Button type="submit" disabled={busy || !accounts.length}>만들기 미리보기</Button>
      </form>
      <ErrorText error={error} />
      <p className="mt-2 text-xs text-faint">새 캠페인은 OFF로 만들어집니다. 광고그룹·키워드·소재를 넣은 뒤 켜세요.</p>
    </details>
  );
}

interface Channel { naver_id: string; name: string; channel_tp: string; key: string; inspect_status: string }

export function AdGroupCreate({ campaigns }: { campaigns: NCampaign[] }) {
  const { ws, accountName } = useApp();
  const [cmp, setCmp] = useState("");
  const [channel, setChannel] = useState("");
  const [name, setName] = useState("");
  const [bid, setBid] = useState("");
  const [budget, setBudget] = useState("");
  const { busy, error, submit } = usePreview();
  const camp = campaigns.find((c) => c.naver_id === cmp);
  const chans = useFetch<Channel[]>(ws && camp ? `/workspaces/${ws.id}/ad-accounts/${camp.ad_account_id}/naver/channels` : null);
  const usable = (chans.data ?? []).filter((c) => camp && c.channel_tp === CHANNEL_TP[camp.campaign_tp]);
  const minBid = camp?.campaign_tp === "SHOPPING" ? 50 : 70;
  return (
    <details className="mt-3 rounded-panel border border-line bg-surface p-3">
      <summary className="cursor-pointer text-sm font-medium">새 광고그룹 만들기</summary>
      <form className="mt-3 flex flex-wrap items-end gap-2" onSubmit={(e) => {
        e.preventDefault();
        if (camp) submit({ entity_type: "adgroup", naver_id: camp.naver_id, field: "create", value: `${name.trim()}|${channel}|${bid}|${budget}`,
          ad_account_id: camp.ad_account_id, product: camp.campaign_tp });
      }}>
        <label className="text-sm">캠페인
          <select className={`${inputCls} mt-1 block`} required value={cmp} onChange={(e) => { setCmp(e.target.value); setChannel(""); }}>
            <option value="">선택</option>
            {campaigns.map((c) => <option key={c.id} value={c.naver_id}>{accountName(c.ad_account_id)} · {PRODUCT_LABEL[c.campaign_tp] ?? c.campaign_tp} · {c.name}</option>)}
          </select>
        </label>
        <label className="text-sm">비즈채널
          <select className={`${inputCls} mt-1 block`} required value={channel} onChange={(e) => setChannel(e.target.value)} disabled={!camp}>
            <option value="">{!camp ? "캠페인 먼저" : chans.loading ? "불러오는 중…" : usable.length ? "선택" : "맞는 채널 없음"}</option>
            {usable.map((c) => <option key={c.naver_id} value={c.naver_id}>{c.name || c.key}{c.inspect_status && c.inspect_status !== "APPROVED" ? ` (${c.inspect_status})` : ""}</option>)}
          </select>
        </label>
        <label className="text-sm">광고그룹 이름 (30자)
          <input className={`${inputCls} mt-1 block`} required maxLength={30} value={name} onChange={(e) => setName(e.target.value.replace("|", ""))} />
        </label>
        <label className="text-sm">기본 입찰가 (원)
          <input className={`${inputCls} mt-1 block w-32`} inputMode="numeric" placeholder={`비우면 ${minBid}원`} value={bid} onChange={(e) => setBid(digits(e.target.value))} />
        </label>
        <label className="text-sm">하루예산 (원)
          <input className={`${inputCls} mt-1 block w-36`} inputMode="numeric" placeholder="비우면 제한 없음" value={budget} onChange={(e) => setBudget(digits(e.target.value))} />
        </label>
        <Button type="submit" disabled={busy || !camp || !channel}>만들기 미리보기</Button>
      </form>
      <ErrorText error={error ?? chans.error} />
      <p className="mt-2 text-xs text-faint">새 광고그룹은 OFF로 만들어집니다. 비즈채널은 네이버 광고 화면에서 등록한 사이트(파워링크)·쇼핑몰(쇼핑검색)입니다.</p>
    </details>
  );
}
