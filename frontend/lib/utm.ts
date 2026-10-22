/** UTM 붙인 URL. 기존 쿼리·#은 그대로 두고 빈 값은 넣지 않는다. 주소가 http(s)가 아니면 null. */
export function utmUrl(base: string, params: Record<string, string>): string | null {
  let u: URL;
  try {
    u = new URL(base.trim());
  } catch {
    return null;
  }
  if (u.protocol !== "http:" && u.protocol !== "https:") return null;
  for (const [k, v] of Object.entries(params)) if (v.trim()) u.searchParams.set(k, v.trim());
  return u.toString();
}
