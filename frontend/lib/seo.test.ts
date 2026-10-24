// 실행: node --test --experimental-strip-types lib/seo.test.ts
import assert from "node:assert/strict";
import { test } from "node:test";
import { type Facts, robotsBlocked, runChecks } from "./seo.ts";

test("robots.txt", () => {
  const r = "User-agent: *\nDisallow: /admin\nAllow: /admin/public\n\nUser-agent: GPTBot\nUser-agent: ClaudeBot\nDisallow: /\n# 끝";
  assert.equal(robotsBlocked(r, "Yeti", "/"), false);
  assert.equal(robotsBlocked(r, "Yeti", "/admin/x"), true);
  assert.equal(robotsBlocked(r, "Yeti", "/admin/public/a"), false);
  assert.equal(robotsBlocked(r, "gptbot", "/p/1"), true);
  assert.equal(robotsBlocked(r, "ClaudeBot", "/"), true);
  assert.equal(robotsBlocked("User-agent: *\nDisallow:", "Yeti", "/"), false);
  assert.equal(robotsBlocked(null, "Yeti", "/"), false);
});

test("판정", () => {
  const facts: Facts = { title: "여름 원피스 | 브랜드몰", description: "", canonical: "", robotsMeta: " noindex", h1: 1, imgs: 10, imgsNoAlt: 8,
    ogTitle: true, ogImage: true, viewport: true, naverVerify: false, lang: "ko", jsonLd: ["Product"], textLength: 120 };
  const res = runChecks({ url: "https://a.com/p/1", status: 200, x_robots: "", html: "", robots: "User-agent: GPTBot\nDisallow: /", sitemaps: [], llms: false }, facts);
  const lv = (label: string) => res.find((c) => c.label === label)?.level;
  assert.equal(lv("검색 노출 허용(noindex)"), "FAIL");
  assert.equal(lv("설명(description)"), "FAIL");
  assert.equal(lv("이미지 설명(alt)"), "FAIL");
  assert.equal(lv("제목(title)"), "PASS");
  assert.equal(lv("robots.txt 수집 허용"), "PASS");
  assert.equal(lv("AI 크롤러 허용"), "FAIL");
  assert.equal(lv("본문이 글자로 있는지"), "FAIL");
  assert.equal(lv("구조화 데이터(schema.org)"), "PASS");
  assert.ok(res.every((c) => c.level === "PASS" || c.fix), "주의·실패에는 고칠 방법이 있어야 한다");
});
