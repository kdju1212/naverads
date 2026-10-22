// 실행: node --test --experimental-strip-types lib/utm.test.ts
import assert from "node:assert/strict";
import { test } from "node:test";
import { utmUrl } from "./utm.ts";

test("UTM", () => {
  assert.equal(utmUrl("https://a.com/p?x=1#top", { utm_source: "naver", utm_medium: "cpc", utm_term: "여름 원피스", utm_content: " " }),
    "https://a.com/p?x=1&utm_source=naver&utm_medium=cpc&utm_term=%EC%97%AC%EB%A6%84+%EC%9B%90%ED%94%BC%EC%8A%A4#top");
  assert.equal(utmUrl("https://a.com?utm_source=old", { utm_source: "naver" }), "https://a.com/?utm_source=naver");
  assert.equal(utmUrl("a.com", { utm_source: "naver" }), null);
  assert.equal(utmUrl("javascript:alert(1)", {}), null);
});
