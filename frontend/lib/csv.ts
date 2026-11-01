// 엑셀이 수식으로 실행하지 않게 =+-@ 등으로 시작하는 글자 칸은 ' 를 붙인다(숫자 칸은 그대로)
export const csvCell = (v: string | number | null) =>
  `"${(typeof v === "string" && /^[=+\-@\t\r]/.test(v) ? "'" + v : String(v ?? "")).replace(/"/g, '""')}"`;
