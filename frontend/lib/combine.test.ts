// 실행: node --test --experimental-strip-types lib/combine.test.ts
import assert from "node:assert/strict";
import { test } from "node:test";
import { ascending, combine, patterns, words } from "./combine.ts";

const label = (p: number[]) => p.map((i) => i + 1).join("+");

test("조합식", () => {
  const p = patterns(4);
  assert.equal(p.length, 64);
  assert.deepEqual(p.slice(0, 8).map(label), ["1", "2", "3", "4", "1+2", "1+3", "1+4", "2+1"]);
  assert.equal(label(p[63]), "4+3+2+1");
  assert.deepEqual(p.filter(ascending).map(label),
    ["1", "2", "3", "4", "1+2", "1+3", "1+4", "2+3", "2+4", "3+4", "1+2+3", "1+2+4", "1+3+4", "2+3+4", "1+2+3+4"]);
});

test("조합", () => {
  const lists = [words("여름, 린넨"), words("원피스\n셔츠"), [], words(" 추천 ")];
  assert.deepEqual(combine(lists, [[0, 1]]), ["여름원피스", "여름셔츠", "린넨원피스", "린넨셔츠"]);
  assert.deepEqual(combine(lists, [[1, 0]]), ["원피스여름", "원피스린넨", "셔츠여름", "셔츠린넨"]);
  assert.deepEqual(combine(lists, [[0, 2], [3], [0, 1, 3]]), ["추천", "여름원피스추천", "여름셔츠추천", "린넨원피스추천", "린넨셔츠추천"]);
  assert.deepEqual(words("여름 원피스, 여름원피스"), ["여름원피스"]);
});
