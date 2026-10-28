"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button, ErrorText, inputCls } from "@/components/ui";
import { API_URL, api, setToken } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Google 로그인 후 서버가 #token=… 또는 #error=…로 돌려보낸다
  useEffect(() => {
    const h = new URLSearchParams(location.hash.slice(1));
    if (!h.has("token") && !h.has("error")) return;
    history.replaceState(null, "", location.pathname);
    const token = h.get("token");
    if (token) void setToken(token).then(() => router.replace("/"));
    // eslint-disable-next-line react-hooks/set-state-in-effect -- 주소 조각은 브라우저에서만 읽을 수 있다(정적 내보내기)
    else setError(h.get("error"));
  }, [router]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await api<{ token: string }>("/auth/login", { body: form });
      await setToken(r.token);
      router.replace("/");
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };

  // eslint-disable-next-line @next/next/no-location-assign-relative-destination -- API 서버(다른 주소)로 이동
  const google = () => { location.href = `${API_URL}/auth/google/start?redirect=${encodeURIComponent(location.origin + "/login")}`; };
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });
  return (
    <div className="flex min-h-screen items-center justify-center">
      <form onSubmit={submit} className="w-full max-w-sm rounded-panel border border-line bg-surface p-6">
        <h1 className="text-xl font-bold text-primary">네이버 광고 통합 관리</h1>
        <p className="mb-5 mt-1 text-sm text-faint">파워링크 · 쇼핑검색광고를 여러 광고주 계정에서 한 번에</p>
        <div className="flex flex-col gap-3">
          <Button type="button" variant="secondary" onClick={google}>Google로 계속하기</Button>
          <p className="text-center text-xs text-faint">처음이면 Google로 계속하면 가입됩니다</p>
          <div className="my-1 border-t border-line" />
          <label className="flex flex-col gap-1 text-sm">이메일<input className={inputCls} type="email" value={form.email} onChange={set("email")} required autoComplete="email" /></label>
          <label className="flex flex-col gap-1 text-sm">비밀번호
            <input className={inputCls} type="password" value={form.password} onChange={set("password")} required autoComplete="current-password" />
          </label>
          <ErrorText error={error} />
          <Button type="submit" disabled={busy}>{busy ? "처리 중…" : "이메일로 로그인"}</Button>
        </div>
      </form>
    </div>
  );
}
