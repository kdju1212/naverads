/** 키워드 조합기: 단어 목록 4개로 조합식(1, 1+2, 2+1, …, 4+3+2+1)마다 띄어쓰기 없이 이어 붙인다. */

/** 1~n번 목록의 순서 있는 조합식 전부(n=4면 64개). 개수 → 번호 순 (1, …, 1+2, 1+3, …, 2+1, …). 0부터 센 번호. */
export function patterns(n: number): number[][] {
  const all: number[][] = [];
  const grow = (p: number[]) => {
    if (p.length) all.push(p);
    for (let i = 0; i < n; i++) if (!p.includes(i)) grow([...p, i]);
  };
  grow([]);
  return all.sort((a, b) => a.length - b.length || a.join().localeCompare(b.join()));
}

/** 번호가 커지는 순서인 조합식(1+2, 1+3 …). 처음엔 이것만 고른다. */
export const ascending = (p: number[]) => p.every((v, i) => i === 0 || p[i - 1] < v);

export const words = (text: string) => [...new Set(text.split(/[\n,]/).map((w) => w.replace(/\s+/g, "")).filter(Boolean))];

/** 고른 조합식마다 목록끼리 곱해 이어 붙인다. 빈 목록이 들어간 조합식은 건너뛰고, 겹치는 키워드는 하나만. */
export function combine(lists: string[][], picked: number[][]): string[] {
  const out = new Set<string>();
  for (const p of picked) {
    if (p.some((i) => !lists[i]?.length)) continue;
    let acc = [""];
    for (const i of p) acc = acc.flatMap((a) => lists[i].map((w) => a + w));
    acc.forEach((k) => out.add(k));
  }
  return [...out];
}
