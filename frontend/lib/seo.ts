/** SEO·GEO 점검. 서버(/seo-fetch)가 가져온 HTML을 브라우저에서 읽어 판정한다. */

export interface Fetched { url: string; status: number; x_robots: string; html: string; robots: string | null; sitemaps: string[]; llms: boolean }

export interface Facts {
  title: string; description: string; canonical: string; robotsMeta: string; h1: number; imgs: number; imgsNoAlt: number;
  ogTitle: boolean; ogImage: boolean; viewport: boolean; naverVerify: boolean; lang: string; jsonLd: string[]; textLength: number;
}

export type Level = "PASS" | "WARN" | "FAIL";
export interface Check { group: "SEO" | "GEO"; label: string; level: Level; detail: string; fix?: string }

const meta = (d: Document, sel: string) => d.querySelector(sel)?.getAttribute("content")?.trim() ?? "";

export function extractFacts(html: string): Facts {
  const d = new DOMParser().parseFromString(html, "text/html");
  const imgs = [...d.querySelectorAll("img")];
  const jsonLd: string[] = [];
  d.querySelectorAll('script[type="application/ld+json"]').forEach((s) => {
    try {
      const walk = (o: unknown): void => {
        if (Array.isArray(o)) return o.forEach(walk);
        if (o && typeof o === "object") {
          const t = (o as Record<string, unknown>)["@type"];
          (Array.isArray(t) ? t : [t]).forEach((x) => typeof x === "string" && jsonLd.push(x));
          walk((o as Record<string, unknown>)["@graph"]);
        }
      };
      walk(JSON.parse(s.textContent ?? ""));
    } catch { /* 깨진 JSON-LD는 없는 것으로 본다 */ }
  });
  d.querySelectorAll("script, style, noscript, template").forEach((e) => e.remove());
  return {
    title: d.querySelector("title")?.textContent?.trim() ?? "",
    description: meta(d, 'meta[name="description" i]'),
    canonical: d.querySelector('link[rel="canonical" i]')?.getAttribute("href") ?? "",
    robotsMeta: [meta(d, 'meta[name="robots" i]'), meta(d, 'meta[name="yeti" i]'), meta(d, 'meta[name="googlebot" i]')].join(" ").toLowerCase(),
    h1: d.querySelectorAll("h1").length,
    imgs: imgs.length,
    imgsNoAlt: imgs.filter((i) => !i.getAttribute("alt")?.trim()).length,
    ogTitle: !!meta(d, 'meta[property="og:title"]'),
    ogImage: !!meta(d, 'meta[property="og:image"]'),
    viewport: !!d.querySelector('meta[name="viewport" i]'),
    naverVerify: !!d.querySelector('meta[name="naver-site-verification" i]'),
    lang: d.documentElement.getAttribute("lang") ?? "",
    jsonLd: [...new Set(jsonLd)],
    textLength: (d.body?.textContent ?? "").replace(/\s+/g, "").length,
  };
}

/** robots.txt에서 이 봇이 path를 수집할 수 없으면 true. 가장 긴 규칙이 이기고 같으면 Allow(구글 방식), * · $ 지원 */
export function robotsBlocked(robots: string | null, bot: string, path: string): boolean {
  if (!robots) return false;
  const groups: { agents: string[]; rules: [boolean, string][] }[] = [];
  let cur: (typeof groups)[number] | null = null;
  for (const raw of robots.split(/\r?\n/)) {
    const [k, ...rest] = raw.replace(/#.*/, "").split(":");
    const key = k.trim().toLowerCase(), val = rest.join(":").trim();
    if (key === "user-agent") {
      if (!cur || cur.rules.length) groups.push((cur = { agents: [], rules: [] }));
      cur.agents.push(val.toLowerCase());
    } else if (cur && (key === "allow" || key === "disallow")) {
      cur.rules.push([key === "allow", val]);
    }
  }
  const b = bot.toLowerCase();
  const mine = groups.filter((g) => g.agents.includes(b));
  const rules = (mine.length ? mine : groups.filter((g) => g.agents.includes("*"))).flatMap((g) => g.rules);
  let best: [boolean, string] | null = null;
  for (const r of rules) {
    if (r[1] === "" && !r[0]) continue; // "Disallow:" 빈 값은 전부 허용
    const re = new RegExp("^" + r[1].replace(/[.+?^{}()|[\]\\$]/g, "\\$&").replace(/\*/g, ".*").replace(/\\\$$/, "$"));
    if (re.test(path) && (!best || r[1].length > best[1].length || (r[1].length === best[1].length && r[0]))) best = r;
  }
  return !!best && !best[0];
}

const SEARCH_BOTS = [["Yeti", "네이버"], ["Googlebot", "구글"]] as const;
const AI_BOTS = [["GPTBot", "ChatGPT 학습"], ["OAI-SearchBot", "ChatGPT 검색"], ["ClaudeBot", "Claude"], ["PerplexityBot", "Perplexity"], ["Google-Extended", "Gemini"]] as const;

export function runChecks(f: Fetched, x: Facts): Check[] {
  const out: Check[] = [];
  const add = (group: Check["group"], label: string, level: Level, detail: string, fix?: string) => out.push({ group, label, level, detail, fix });
  const { pathname, search } = new URL(f.url);
  const path = pathname + search; // robots 규칙에 ?sort= 같은 쿼리 조건이 있어서

  // ----- SEO -----
  add("SEO", "페이지 응답", f.status < 300 ? "PASS" : "FAIL", `HTTP ${f.status}`,
    f.status >= 400 ? "검색엔진·AI도 이 페이지를 받지 못할 수 있습니다. 봇 차단(방화벽) 설정을 확인하세요" : undefined);
  const noindex = /noindex/.test(x.robotsMeta) || /noindex/i.test(f.x_robots);
  add("SEO", "검색 노출 허용(noindex)", noindex ? "FAIL" : "PASS", noindex ? "noindex가 설정되어 검색 결과에 나오지 않습니다" : "noindex 없음",
    noindex ? "meta robots 또는 X-Robots-Tag에서 noindex를 지우세요" : undefined);
  const blocked = SEARCH_BOTS.filter(([b]) => robotsBlocked(f.robots, b, path)).map(([, n]) => n);
  add("SEO", "robots.txt 수집 허용", blocked.length ? "FAIL" : f.robots === null ? "WARN" : "PASS",
    blocked.length ? `${blocked.join("·")} 검색 봇이 이 페이지를 수집할 수 없습니다` : f.robots === null ? "robots.txt가 없습니다 (수집은 허용됨)" : "네이버·구글 수집 허용",
    blocked.length ? "robots.txt의 Disallow 규칙을 확인하세요" : f.robots === null ? "robots.txt를 만들고 Sitemap 주소를 적어 두세요" : undefined);
  add("SEO", "사이트맵(sitemap)", f.sitemaps.length ? "PASS" : "WARN", f.sitemaps.length ? f.sitemaps.slice(0, 3).join(", ") : "찾지 못했습니다",
    f.sitemaps.length ? undefined : "sitemap.xml을 만들고 네이버 서치어드바이저·구글 서치 콘솔에 제출하세요");
  const tl = [...x.title].length;
  add("SEO", "제목(title)", !tl ? "FAIL" : tl < 10 || tl > 60 ? "WARN" : "PASS", tl ? `${x.title} (${tl}자)` : "없음",
    !tl ? "페이지마다 다른 제목을 넣으세요" : tl < 10 || tl > 60 ? "핵심 키워드를 앞에 두고 10~60자로 맞추세요" : undefined);
  const dl = [...x.description].length;
  add("SEO", "설명(description)", !dl ? "FAIL" : dl < 40 || dl > 160 ? "WARN" : "PASS", dl ? `${x.description} (${dl}자)` : "없음",
    !dl ? "검색 결과에 보일 설명을 넣으세요" : dl < 40 || dl > 160 ? "40~160자로 맞추세요" : undefined);
  add("SEO", "대표 주소(canonical)", x.canonical ? "PASS" : "WARN", x.canonical || "없음",
    x.canonical ? undefined : "같은 내용이 여러 주소로 열리면 대표 주소를 지정하세요");
  add("SEO", "큰 제목(H1)", x.h1 === 1 ? "PASS" : "WARN", `${x.h1}개`, x.h1 === 1 ? undefined : "페이지 주제를 담은 H1을 1개만 두세요");
  const ratio = x.imgs ? x.imgsNoAlt / x.imgs : 0;
  add("SEO", "이미지 설명(alt)", ratio > 0.5 ? "FAIL" : ratio > 0.2 ? "WARN" : "PASS", `이미지 ${x.imgs}개 중 ${x.imgsNoAlt}개 없음`,
    ratio > 0.2 ? "상품·내용 이미지에 무엇인지 설명하는 alt를 넣으세요" : undefined);
  add("SEO", "모바일 화면 설정", x.viewport ? "PASS" : "FAIL", x.viewport ? "viewport 있음" : "viewport 없음",
    x.viewport ? undefined : '<meta name="viewport" content="width=device-width, initial-scale=1">을 넣으세요');
  add("SEO", "공유 미리보기(OG)", x.ogTitle && x.ogImage ? "PASS" : "WARN", `og:title ${x.ogTitle ? "있음" : "없음"}, og:image ${x.ogImage ? "있음" : "없음"}`,
    x.ogTitle && x.ogImage ? undefined : "카톡·SNS 공유용 og:title·og:image를 넣으세요");
  add("SEO", "네이버 서치어드바이저 인증", x.naverVerify ? "PASS" : "WARN", x.naverVerify ? "인증 태그 있음" : "인증 태그 없음 (파일 방식으로 했을 수도 있음)",
    x.naverVerify ? undefined : "네이버 서치어드바이저에 사이트를 등록하세요");

  // ----- GEO -----
  const aiBlocked = AI_BOTS.filter(([b]) => robotsBlocked(f.robots, b, path)).map(([, n]) => n);
  add("GEO", "AI 크롤러 허용", aiBlocked.length ? "FAIL" : "PASS", aiBlocked.length ? `막힘: ${aiBlocked.join(", ")}` : "주요 AI 크롤러 모두 허용",
    aiBlocked.length ? "AI 답변에 인용되려면 robots.txt에서 해당 봇 차단을 푸세요 (학습 차단만 원하면 GPTBot·Google-Extended만 막기)" : undefined);
  const thin = x.textLength < 500;
  add("GEO", "본문이 글자로 있는지", thin ? "FAIL" : "PASS", `HTML 안 글자 ${x.textLength.toLocaleString()}자`,
    thin ? "내용이 이미지이거나 자바스크립트로 그려져 AI·검색엔진이 읽기 어렵습니다. 핵심 설명·스펙·FAQ를 글자로 넣으세요" : undefined);
  const want = ["Product", "Organization", "FAQPage", "BreadcrumbList", "Article", "LocalBusiness"].filter((t) => x.jsonLd.includes(t));
  add("GEO", "구조화 데이터(schema.org)", !x.jsonLd.length ? "FAIL" : want.length ? "PASS" : "WARN", x.jsonLd.length ? x.jsonLd.join(", ") : "없음",
    want.length ? undefined : "상품 페이지는 Product(가격·재고·리뷰), 회사 정보는 Organization, 자주 묻는 질문은 FAQPage를 JSON-LD로 넣으세요");
  add("GEO", "FAQ 구조화", x.jsonLd.includes("FAQPage") ? "PASS" : "WARN", x.jsonLd.includes("FAQPage") ? "FAQPage 있음" : "없음",
    x.jsonLd.includes("FAQPage") ? undefined : "질문-답 형태 내용은 AI가 인용하기 좋습니다. FAQ 섹션과 FAQPage를 추가하세요");
  add("GEO", "언어 표시(lang)", x.lang ? "PASS" : "WARN", x.lang || "없음", x.lang ? undefined : '<html lang="ko">로 언어를 표시하세요');
  add("GEO", "llms.txt", f.llms ? "PASS" : "WARN", f.llms ? "있음" : "없음 (효과는 아직 검증 전)",
    f.llms ? undefined : "사이트 소개·주요 페이지 목록을 /llms.txt로 두면 AI가 사이트를 이해하기 쉽습니다");
  return out;
}
