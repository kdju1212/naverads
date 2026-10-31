"use client";

import { useState } from "react";
import { Button, Card, ErrorText, inputCls } from "@/components/ui";
import { api, inspectLabel } from "@/lib/api";
import { NAd, NAdGroup, patchAccount } from "@/lib/naverData";
import { useApp } from "@/lib/store";

const digits = (v: string) => v.replace(/[^0-9]/g, "");

/** 쇼핑검색 광고그룹에 상품소재 등록(OFF로 생성). 서버: backend/src/app/shopping_ads.py */
export function ShoppingAdCreate({ adgroups }: { adgroups: NAdGroup[] }) {
  const { ws, accountName } = useApp();
  const groups = adgroups.filter((g) => g.adgroup_type === "SHOPPING");
  const [form, setForm] = useState({ adgroup_id: "", product_id: "", bid_amt: "" });
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ws) return;
    setBusy(true);
    setError(null);
    setMsg(null);
    try {
      const g = groups.find((x) => x.naver_id === form.adgroup_id)!;
      const r = await api<NAd>(`/workspaces/${ws.id}/shopping-ads`, {
        body: { ad_account_id: g.ad_account_id, adgroup_naver_id: g.naver_id, product_id: form.product_id, bid_amt: form.bid_amt ? Number(form.bid_amt) : null },
      });
      setMsg(`만들었습니다 (검수 상태: ${r.inspect_status ? inspectLabel(r.inspect_status) : "확인 중"}). OFF로 만들어졌으니 검수 후 켜세요.`);
      setForm({ ...form, product_id: "", bid_amt: "" });
      await patchAccount(ws.id, r.ad_account_id, (d) => ({ ...d, ads: [...d.ads, { ...r, id: r.naver_id }] }));
    } catch (err) {
      setError((err as Error).message);
    }
    setBusy(false);
  };

  return (
    <Card title="새 상품소재" className="mb-4">
      <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
        <select className={inputCls} value={form.adgroup_id} onChange={(e) => setForm({ ...form, adgroup_id: e.target.value })} required aria-label="광고그룹">
          <option value="">쇼핑검색 광고그룹 선택</option>
          {groups.map((g) => <option key={g.id} value={g.naver_id}>{accountName(g.ad_account_id)} · {g.name}</option>)}
        </select>
        <input className={inputCls} placeholder="네이버쇼핑 상품 번호" inputMode="numeric" required aria-label="상품 번호"
          value={form.product_id} onChange={(e) => setForm({ ...form, product_id: digits(e.target.value) })} />
        <input className={`${inputCls} w-48`} placeholder="입찰가 (비우면 그룹 입찰가)" inputMode="numeric" aria-label="입찰가"
          value={form.bid_amt} onChange={(e) => setForm({ ...form, bid_amt: digits(e.target.value) })} />
        <Button type="submit" disabled={busy || !groups.length}>{busy ? "만드는 중…" : "네이버에 만들기"}</Button>
      </form>
      <ErrorText error={error} />
      {msg && <p className="mt-2 text-sm text-accent">{msg}</p>}
      <p className="mt-2 text-xs text-faint">입찰가는 50~100,000원, 10원 단위. 상품 정보(이름·가격)는 쇼핑몰에서 가져오며 여기서 바꾸지 않습니다.</p>
    </Card>
  );
}
