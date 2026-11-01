// 실행: node --test --experimental-strip-types lib/csv.test.ts
import assert from "node:assert/strict";
import { test } from "node:test";
import { csvCell } from "./csv.ts";

test("수식으로 시작하는 글자는 ' 를 붙이고 따옴표는 두 번", () => {
  assert.equal(csvCell('=HYPERLINK("x")'), `"'=HYPERLINK(""x"")"`);
  for (const v of ["+1", "-1", "@SUM(A1)", "\tx", "\rx"]) assert.equal(csvCell(v), `"'${v}"`);
  assert.equal(csvCell("캠페인 A"), '"캠페인 A"');
  assert.equal(csvCell(-100), '"-100"');
  assert.equal(csvCell(null), '""');
});
