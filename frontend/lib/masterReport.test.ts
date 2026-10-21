// 실행: node --test --experimental-strip-types lib/masterReport.test.ts
import assert from "node:assert/strict";
import { test } from "node:test";
import { idsFrom, keywordsFrom, parseTsv } from "./masterReport.ts";

// 실계정 파일 형식 그대로(헤더 없음, 끝 빈 줄)
const kw = [
  "4285993\tgrp-1\tnkw-1\t담배탈취제\t1860\thttps://a\thttps://a\t0\t10\t0\t2026-07-02T01:28:52Z\t\t",
  "4285993\tgrp-1\tnkw-2\t자하라밤탈취제\t500\t\t\t1\t10\t0\t2026-07-02T05:33:18Z\t\t",
  "4285993\tgrp-2\tnkw-3\t피톤치드방향제\t10000\t\t\t0\t10\t1\t2026-10-20T12:28:29Z\t\t",
  "4285993\tgrp-2\tnkw-4\t삭제됨\t70\t\t\t0\t10\t0\t2026-07-02T01:28:52Z\t2026-10-20T00:00:00Z\t",
  "",
].join("\r\n");

test("키워드 보고서", () => {
  const rows = keywordsFrom(parseTsv(kw), 7);
  assert.equal(rows.length, 3); // 삭제 시각이 있는 줄은 뺀다
  assert.deepEqual(rows[0], { id: "nkw-1", ad_account_id: 7, naver_id: "nkw-1", adgroup_naver_id: "grp-1", keyword: "담배탈취제",
    bid_amt: 1860, status: "ON", use_group_bid: false });
  assert.equal(rows[1].status, "OFF");
  assert.equal(rows[2].use_group_bid, true);
});

test("ID 칸", () => {
  assert.deepEqual(idsFrom(parseTsv("4285993\tgrp-a001\tcmp-1\t이름"), "Adgroup"), ["grp-a001"]);
  assert.deepEqual(idsFrom(parseTsv("4285993\tgrp-1\tnad-9\t10"), "RsaAd"), ["nad-9"]);
  assert.deepEqual(idsFrom(parseTsv("4285993\text-1\t8\tgrp-1"), "AdExtension"), ["ext-1"]);
});
