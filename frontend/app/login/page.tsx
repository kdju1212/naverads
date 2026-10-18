"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, ErrorText, inputCls } from "@/components/ui";
import { api, setToken } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [form, setForm] = useState({ email: "", password: "", name: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const body = mode === "login" ? { email: form.email, password: form.password } : form;
      const r = await api<{ token: string }>(`/auth/${mode}`, { body });
      setToken(r.token);
      router.replace("/");
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });
  return (
    <div className="flex min-h-screen items-center justify-center">
      <form onSubmit={submit} className="w-full max-w-sm rounded-lg border border-gray-200 bg-white p-6">
        <h1 className="text-lg font-bold text-emerald-700">네이버 광고 통합 관리</h1>
        <p className="mb-5 mt-1 text-sm text-gray-500">파워링크 · 쇼핑검색광고를 여러 광고주 계정에서 한 번에</p>
        <div className="flex flex-col gap-3">
          {mode === "signup" && (
            <label className="flex flex-col gap-1 text-sm">이름<input className={inputCls} value={form.name} onChange={set("name")} required autoComplete="name" /></label>
          )}
          <label className="flex flex-col gap-1 text-sm">이메일<input className={inputCls} type="email" value={form.email} onChange={set("email")} required autoComplete="email" /></label>
          <label className="flex flex-col gap-1 text-sm">비밀번호
            <input className={inputCls} type="password" value={form.password} onChange={set("password")} required minLength={mode === "signup" ? 8 : undefined}
              autoComplete={mode === "login" ? "current-password" : "new-password"} />
          </label>
          <ErrorText error={error} />
          <Button type="submit" disabled={busy}>{busy ? "처리 중…" : mode === "login" ? "로그인" : "회원가입"}</Button>
          <button type="button" className="text-sm text-gray-500 hover:text-gray-800" onClick={() => { setMode(mode === "login" ? "signup" : "login"); setError(null); }}>
            {mode === "login" ? "계정이 없나요? 회원가입" : "이미 계정이 있나요? 로그인"}
          </button>
        </div>
      </form>
    </div>
  );
}
