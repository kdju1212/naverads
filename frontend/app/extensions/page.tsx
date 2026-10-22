"use client";

import { useState } from "react";
import { BulkBar } from "@/components/BulkBar";
import { Col, DataTable } from "@/components/DataTable";
import { DataStatus } from "@/components/DataStatus";
import { Badge, Button, Card, ErrorText, inputCls, PageTitle } from "@/components/ui";
import { api, inspectLabel } from "@/lib/api";
import { NAdGroup, NExtension as Extension, patchAccount, useNaverData } from "@/lib/naverData";
import { useApp } from "@/lib/store";

const TYPE_LABEL: Record<string, string> = {
  HEADLINE: "추가제목", DESCRIPTION: "홍보문구", DESCRIPTION_EXTRA: "추가설명", SUB_LINKS: "서브링크", PRICE_LINKS: "가격링크",
  PROMOTION: "홍보문구", POWER_LINK_IMAGE: "파워링크 이미지", IMAGE_SUB_LINKS: "이미지 서브링크", PHONE: "전화번호",
  LOCATION: "위치정보", BOOKING: "예약", TALK: "톡톡", CALCULATION: "계산", PLACE: "플레이스", WEBSITE_INFO: "웹사이트 정보",
  NAVER_BLOG_REVIEW: "블로그 리뷰", NAVER_TV_VIDEO: "동영상", TALKTALK_CONSULTATION: "톡톡 상담",
};

const PROMO_HEADINGS = ["할인", "사은품", "추가선물증정", "이벤트", "신상품"];

// 확장소재 유형마다 구조가 달라 문자열 값만 모아 보여 준다
const strings = (v: unknown): string[] =>
  typeof v === "string" ? [v] : Array.isArray(v) ? v.flatMap(strings) : v && typeof v === "object" ? Object.values(v).flatMap(strings) : [];

export default function ExtensionsPage() {
  const { ws, product, accountName } = useApp();
  const shoppingOnly = product === "SHOPPING";
  const data = useNaverData();
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [delError, setDelError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const rows = data.extensions;
  const groups = data.adgroups.filter((g) => g.adgroup_type === "WEB_SITE");
  const ownerName = new Map([...data.campaigns, ...data.adgroups].map((o) => [o.naver_id, o.name]));
  // 네이버에 반영한 생성·삭제를 보관본에도 바로 반영(계정 전체를 다시 받지 않는다)
  const patch = (accountId: number, fn: (list: Extension[]) => Extension[]) =>
    ws ? patchAccount(ws.id, accountId, (d) => ({ ...d, extensions: fn(d.extensions) })) : Promise.resolve();
  const picked = rows.filter((r) => sel.has(r.id));

  const remove = async () => {
    if (!ws || !picked.length || !confirm(`선택한 확장소재 ${picked.length}개를 네이버에서 삭제합니다. 되돌릴 수 없습니다. 계속할까요?`)) return;
    setDeleting(true);
    setDelError(null);
    const failed: string[] = [];
    for (const r of picked) {
      try {
        const q = new URLSearchParams({ account_id: String(r.ad_account_id), owner_naver_id: r.owner_naver_id, ext_type: r.ext_type });
        await api(`/workspaces/${ws.id}/ad-extensions/${r.naver_id}?${q}`, { method: "DELETE" });
        await patch(r.ad_account_id, (list) => list.filter((x) => x.naver_id !== r.naver_id));
      } catch (e) {
        failed.push(`${TYPE_LABEL[r.ext_type] ?? r.ext_type}: ${(e as Error).message}`);
      }
    }
    setDelError(failed.length ? failed.join(" / ") : null);
    setSel(new Set());
    setDeleting(false);
  };

  if (shoppingOnly) {
    return (
      <>
        <PageTitle>확장소재 (파워링크)</PageTitle>
        <Card><p className="text-sm text-gray-600">쇼핑검색광고에는 파워링크 전용 확장소재를 적용하지 않습니다.</p></Card>
      </>
    );
  }

  const cols: Col<Extension>[] = [
    { key: "acc", label: "광고주", value: (r) => accountName(r.ad_account_id) },
    { key: "owner", label: "연결 대상", value: (r) => ownerName.get(r.owner_naver_id) ?? r.owner_naver_id },
    { key: "type", label: "유형", value: (r) => TYPE_LABEL[r.ext_type] ?? r.ext_type },
    { key: "content", label: "내용", value: (r) => strings(r.payload).join(" · ").slice(0, 120) || null },
    { key: "status", label: "상태", value: (r) => r.status, render: (r) => <Badge value={r.status} /> },
    { key: "inspect", label: "검수", value: (r) => inspectLabel(r.inspect_status) },
  ];

  return (
    <>
      <PageTitle desc="파워링크 확장소재를 조회·생성·삭제하고 ON/OFF를 대량 변경합니다. 네이버 API는 내용 수정을 지원하지 않아, 내용을 바꾸려면 새로 만들고 기존 것을 삭제하세요.">확장소재 (파워링크)</PageTitle>
      {ws && <NewExtension wsId={ws.id} groups={groups} accountName={accountName} onCreated={(e) => patch(e.ad_account_id, (list) => [...list, { ...e, id: e.naver_id }])} />}
      <DataStatus data={data} />
      <ErrorText error={delError} />
      <DataTable rows={rows} cols={cols} selected={sel} onSelect={setSel} loading={data.loading && !rows.length}
        empty="확장소재가 없습니다."
        toolbar={<div className="flex flex-wrap items-center gap-2">
          <BulkBar entityType="ad_extension" rows={picked} />
          <Button variant="danger" disabled={!picked.length || deleting} onClick={remove}>{deleting ? "삭제 중…" : "선택 삭제"}</Button>
        </div>} />
    </>
  );
}

function NewExtension({ wsId, groups, accountName, onCreated }: {
  wsId: number; groups: NAdGroup[]; accountName: (id: number) => string; onCreated: (e: Extension) => Promise<unknown>;
}) {
  const [form, setForm] = useState({ adgroup_id: "", ext_type: "DESCRIPTION", heading: PROMO_HEADINGS[0], description: "", links: "" });
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setMsg(null);
    // 서브링크는 한 줄에 "이름 | URL"
    const links = form.links.split("\n").map((l) => l.trim()).filter(Boolean).map((l) => {
      const [name, ...rest] = l.split("|");
      return { name: name.trim(), final: rest.join("|").trim() };
    });
    try {
      const g = groups.find((x) => x.naver_id === form.adgroup_id)!;
      const r = await api<Extension>(`/workspaces/${wsId}/ad-extensions`, {
        body: { ad_account_id: g.ad_account_id, adgroup_naver_id: g.naver_id, ext_type: form.ext_type, heading: form.heading, description: form.description, links },
      });
      setMsg(`만들었습니다 (검수 상태: ${r.inspect_status ? inspectLabel(r.inspect_status) : "확인 중"}). 검수가 끝나야 노출됩니다.`);
      setForm({ ...form, heading: form.ext_type === "DESCRIPTION" ? form.heading : "", description: "", links: "" });
      await onCreated(r);
    } catch (err) {
      setError((err as Error).message);
    }
    setBusy(false);
  };

  return (
    <Card title="새 확장소재" className="mb-4">
      <form onSubmit={submit} className="flex flex-col gap-2 p-4">
        <div className="flex flex-wrap gap-2">
          <select className={inputCls} value={form.adgroup_id} onChange={set("adgroup_id")} required aria-label="광고그룹">
            <option value="">광고그룹 선택</option>
            {groups.map((g) => <option key={g.id} value={g.naver_id}>{accountName(g.ad_account_id)} · {g.name}</option>)}
          </select>
          <select className={inputCls} value={form.ext_type} aria-label="유형"
            onChange={(e) => setForm({ ...form, ext_type: e.target.value, heading: e.target.value === "DESCRIPTION" ? PROMO_HEADINGS[0] : "" })}>
            <option value="DESCRIPTION">홍보문구</option>
            <option value="HEADLINE">추가제목</option>
            <option value="DESCRIPTION_EXTRA">추가설명</option>
            <option value="SUB_LINKS">서브링크</option>
          </select>
        </div>
        {form.ext_type === "DESCRIPTION" ? (
          <div className="flex flex-wrap gap-2">
            <select className={inputCls} value={form.heading} onChange={set("heading")} aria-label="구분">
              {PROMO_HEADINGS.map((h) => <option key={h} value={h}>{h}</option>)}
            </select>
            <input className={`${inputCls} min-w-64 flex-1`} placeholder="홍보문구 (최대 14자, 예: 3만원 쿠폰팩 증정)" maxLength={14}
              value={form.description} onChange={set("description")} required aria-label="홍보문구" />
          </div>
        ) : form.ext_type === "HEADLINE" ? (
          <input className={inputCls} placeholder="추가제목 (최대 15자)" maxLength={15} value={form.heading} onChange={set("heading")} required aria-label="추가제목" />
        ) : form.ext_type === "DESCRIPTION_EXTRA" ? (
          <input className={inputCls} placeholder="추가설명 (최대 45자)" maxLength={45} value={form.description} onChange={set("description")} required aria-label="추가설명" />
        ) : (
          <textarea className={inputCls} rows={3} value={form.links} onChange={set("links")} required aria-label="서브링크"
            placeholder={"한 줄에 하나씩: 이름 | URL\n신제품 | https://example.com/new\n당일출고 | https://example.com/today"} />
        )}
        <ErrorText error={error} />
        {msg && <p className="text-sm text-emerald-700">{msg}</p>}
        <div><Button type="submit" disabled={busy}>{busy ? "만드는 중…" : "네이버에 만들기"}</Button></div>
      </form>
    </Card>
  );
}
