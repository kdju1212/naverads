"""사용법: python gen.py <출력 폴더> <gh-pages 폴더>. 공식 명세(gh-pages assets/json)에서 엔드포인트 상세·모델 문서를 만든다. 사람 손으로 쓴 이름·설명은 names.tsv."""
import json, re, sys
from pathlib import Path

SPEC = Path(sys.argv[2]) / "assets" / "json"  # searchad-apidoc gh-pages 브랜치를 받은 폴더
OUT = Path(sys.argv[1])
FILES = [  # app/config.js 순서 = 공식 문서 사이트가 읽는 순서
    ("ncc-heroes-ncc", "광고 관리(NCC)"), ("ncc-heroes-tool", "도구(Tool)"), ("ncc-heroes-billing", "비즈머니(Billing)"),
    ("atower", "광고 계정·관리 계정(AdAccounts·ManagerAccounts)"), ("ncc-report", "통계·대용량 보고서(Stat·StatReport)"),
    ("master-report", "마스터 보고서(MasterReport)"), ("ncc-keywordstool", "키워드 도구(RelKwdStat)"),
    ("estimate", "입찰가·성과 예측(Estimate)"), ("ncc-inspect-history", "검수 이력(InspectHistory)")]
METHODS = ("get", "post", "put", "delete")
DOC = "https://naver.github.io/searchad-apidoc/#/operations/"

names = {}
for line in (Path(__file__).parent / "names.tsv").read_text(encoding="utf-8").splitlines():
    if line.strip() and not line.startswith("#"):
        key, *rest = line.split("\t")
        names[key] = rest  # [작업명, 쉬운 설명, 구분, 광고비·노출 영향]


def public_path(p):  # 공식 문서 주소·호출 주소에는 /api 접두어가 없다(예: /ncc/campaigns)
    return re.sub(r"^/api(?=/)", "", p)


def doc_link(m, p):
    return DOC + m.upper() + "/" + public_path(p).replace("/", "~2F").replace("{", "%7B").replace("}", "%7D").replace("?", "%3F")


def ko(text):  # 명세 설명은 '한국어 줄 + 영어 줄 + #태그'가 섞여 있다: 태그를 떼고 한 줄로
    t = re.sub(r"#(required|hidden|optional)[-\w]*", "", text or "")
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t).strip().replace("|", "\\|")


def tags(text):
    return sorted(set(re.findall(r"#((?:required|hidden)-\w+)", text or "")))


def ref_name(s):
    if not isinstance(s, dict):
        return None
    if "$ref" in s:
        return s["$ref"].split("/")[-1]
    if s.get("type") == "array":
        r = ref_name(s.get("items"))
        return f"{r}[]" if r else None
    return None


def typ(s):
    if not isinstance(s, dict):
        return ""
    r = ref_name(s)
    if r:
        return f"[{r}](06-models.md#{anchor(r.rstrip('[]'))})" + ("" if not r.endswith("[]") else "")
    t = s.get("type", "")
    if t == "array":
        return f"{typ(s.get('items', {}))} 배열"
    return t + (f"({s['format']})" if s.get("format") else "")


def anchor(name):
    return "model-" + re.sub(r"[^0-9a-z]+", "-", name.lower()).strip("-")


def dummy(s, defs, tag="#required-create", depth=0, name="value"):
    """명세 필드 타입으로 만든 가상값(문자열은 <필드명>). 실제 ID·키는 쓰지 않는다. tag: 생성이면 #required-create, 수정이면 #required-update 필드만."""
    if depth > 3 or not isinstance(s, dict):
        return None
    if "$ref" in s:
        d = defs.get(s["$ref"].split("/")[-1], {})
        if "example" in d:
            return d["example"]
        req = [k for k, v in d.get("properties", {}).items() if tag in (v.get("description") or "")] or d.get("required") or []
        return {k: dummy(d["properties"][k], defs, tag, depth + 1, k) for k in req if k in d.get("properties", {})}
    if "enum" in s:
        return s["enum"][0]
    t = s.get("type")
    if t == "array":
        return [dummy(s.get("items", {}), defs, tag, depth + 1, name)]
    return {"integer": 0, "number": 0, "boolean": False, "object": {}}.get(t, f"<{name}>")


ops, used_defs, rows = [], {}, []
for f, label in FILES:
    d = json.loads((SPEC / f"{f}.json").read_text(encoding="utf-8"))
    defs = d.get("definitions", {})
    for p, items in d["paths"].items():
        for m, o in items.items():
            if m not in METHODS:
                continue
            ops.append((f, label, m, p, o, defs))

out = ["# 엔드포인트별 상세 명세", "",
       "> 이 파일은 공식 명세 JSON에서 자동으로 만들었다(작업명·쉬운 설명·구분·영향은 사람이 붙임). 다시 만드는 방법은 [README](README.md#다시-만들기).",
       "> 경로는 공식 문서·실제 호출 기준(`/api` 접두어 없음). 모든 요청에 [공통 인증 헤더](02-auth-common.md)가 필요하다.",
       "> 필수: ✔ = 명세 required, 생성/수정 = 모델 설명의 `#required-create`/`#required-update` 태그(조건부 필수).", ""]
toc = ["## 목차", ""]
body = []
n = 0
cur = None
for f, label, m, p, o, defs in ops:
    n += 1
    pp = public_path(p)
    key = f"{m.upper()} {pp}"
    nm = names.get(key, ["(이름 없음)", "", "", ""])
    if label != cur:
        cur = label
        toc.append(f"- **{label}** (`{f}.json`)")
        body += ["", f"## {label}", f"원본: `assets/json/{f}.json`", ""]
    aid = f"ep-{n:03d}"
    toc.append(f"  - [{n}. {nm[0]} — `{m.upper()} {pp}`](#{aid})")
    rows.append((n, f, m.upper(), pp, nm))
    body += [f'<a id="{aid}"></a>', f"### {n}. {nm[0]}", "", f"`{m.upper()} {pp}`", ""]
    body += [f"- **쉬운 설명**: {nm[1]}", f"- **구분**: {nm[2]} · **광고비·노출 영향**: {nm[3]}",
             f"- **공식 설명**: {ko(o.get('description')) or '공식 자료에서 확인되지 않음'}",
             f"- **공식 요약(summary)**: {o.get('summary', '')} · 태그: {', '.join(o.get('tags', []))}",
             f"- **공식 문서**: <{doc_link(m, p)}>"]
    if o.get("deprecated"):
        body.append("- **폐기 표시(deprecated)**: 예")
    params = o.get("parameters", [])
    body += ["", "**파라미터**", ""]
    bodyref = None
    if params:
        body += ["| 이름 | 위치 | 필수 | 타입 | 허용값 | 설명 |", "|---|---|---|---|---|---|"]
        for x in params:
            loc = {"path": "경로", "query": "쿼리", "body": "본문", "formData": "폼", "header": "헤더"}.get(x["in"], x["in"])
            t = typ(x.get("schema")) if x["in"] == "body" else typ(x)
            if x["in"] == "body":
                bodyref = x.get("schema")
                r = ref_name(bodyref)
                if r:
                    used_defs.setdefault(r.rstrip("[]"), defs)
            enum = ", ".join(map(str, x.get("enum") or x.get("items", {}).get("enum") or []))
            body.append(f"| `{x['name']}` | {loc} | {'✔' if x.get('required') else ''} | {t} | {enum} | {ko(x.get('description'))} |")
    else:
        body.append("없음(공통 인증 헤더만)")
    # 본문 모델의 생성·수정 필수 필드
    if bodyref:
        r = (ref_name(bodyref) or "").rstrip("[]")
        dd = defs.get(r, {})
        need_c = [k for k, v in dd.get("properties", {}).items() if "#required-create" in (v.get("description") or "")]
        need_u = [k for k, v in dd.get("properties", {}).items() if "#required-update" in (v.get("description") or "")]
        req = dd.get("required") or []
        if need_c or need_u or req:
            body += ["", f"본문 모델 `{r}`의 필수 필드: " + "; ".join(x for x in [
                f"명세 required = {', '.join(req)}" if req else "",
                f"생성 시 = {', '.join(need_c)}" if need_c else "",
                f"수정 시 = {', '.join(need_u)}" if need_u else ""] if x)]
    # 응답
    ok = o.get("responses", {}).get("200") or o.get("responses", {}).get("201") or o.get("responses", {}).get("204") or {}
    rs = ok.get("schema")
    rn = ref_name(rs)
    if rn:
        used_defs.setdefault(rn.rstrip("[]"), defs)
    codes = ", ".join(o.get("responses", {}).keys())
    body += ["", f"**응답**: {typ(rs) if rs else ok.get('description', '공식 자료에서 확인되지 않음')} (명세 응답 코드: {codes})"]
    # 요청 예시: 명세 필드로 만든 가상값
    q = [x for x in params if x["in"] == "query"]
    ex_path = pp.split("{?")[0].split("?")[0]
    for x in params:
        if x["in"] == "path":
            ex_path = ex_path.replace("{" + x["name"] + "}", f"<{x['name']}>")
    qs = "&".join(f"{x['name']}=<{x['name']}>" if not x.get("enum") else f"{x['name']}={x['enum'][0]}"
                  for x in q if x.get("required") or (x["name"] == "fields" and x.get("enum")))
    fixed = re.search(r"\?(type=\w+)", pp)
    if fixed:
        qs = fixed.group(1)
    body += ["", "요청 예시(가상값, 공통 인증 헤더 생략):", "```http", f"{m.upper()} {ex_path}{'?' + qs if qs else ''}",
             "X-Timestamp / X-API-KEY / X-Customer / X-Signature  ← 공통 인증 헤더"]
    if bodyref:
        r = (ref_name(bodyref) or "").rstrip("[]")
        tag = "#required-update" if m == "put" else "#required-create"
        src = "명세 모델의 example" if "example" in defs.get(r, {}) else             f"명세 필드로 만든 가상값({'수정' if m == 'put' else '생성'} 필수 태그 필드만 — fields 값에 따라 실제로 필요한 필드는 공식 설명 참고)"
        val = dummy(bodyref, defs, tag)
        body += ["", json.dumps(val, ensure_ascii=False, indent=2)[:1500], "```", f"(본문 출처: {src})"]
    else:
        body.append("```")
    if rn and "example" in defs.get(rn.rstrip("[]"), {}):
        body += ["", "응답 예시(명세 모델의 example):", "```json", json.dumps(defs[rn.rstrip('[]')]["example"], ensure_ascii=False, indent=2)[:1500], "```"]
    else:
        body += ["", "응답 예시: 공식 자료에서 확인되지 않음 — 필드는 응답 모델 표 참고"]
    body.append("")

(OUT / "03-endpoints.md").write_text("\n".join(out + toc + body) + "\n", encoding="utf-8")

# 모델: 엔드포인트에서 쓰는 정의 + 그 안에서 참조하는 정의
models = ["# 요청·응답 모델(필드 표)", "",
          "> 공식 명세 JSON의 definitions에서 자동으로 만들었다. 필수 열: ✔ = 명세 required, 생성/수정 = 설명의 `#required-create`/`#required-update`, "
          "숨김 = `#hidden-*`(요청에 넣지 않는 값 등).", ""]
seen, queue = set(), list(used_defs.items())
while queue:
    name, defs = queue.pop(0)
    if name in seen or name not in defs:
        continue
    seen.add(name)
    d = defs[name]
    models += [f'<a id="{anchor(name)}"></a>', f"## {name}", ""]
    if d.get("description"):
        models += [ko(d["description"]), ""]
    props = d.get("properties", {})
    if not props:
        models += [f"필드 정의 없음(타입: {d.get('type', '')})", ""]
    else:
        models += ["| 필드 | 타입 | 필수 | 허용값 | 설명 |", "|---|---|---|---|---|"]
        for k, v in props.items():
            r = ref_name(v)
            if r:
                queue.append((r.rstrip("[]"), defs))
            flags = [x.replace("required-", "").replace("hidden-", "숨김:") for x in tags(v.get("description"))]
            flags = ["생성" if x == "create" else "수정" if x == "update" else x for x in flags]
            if k in (d.get("required") or []):
                flags.insert(0, "✔")
            enum = ", ".join(map(str, v.get("enum") or v.get("items", {}).get("enum") or []))
            models.append(f"| `{k}` | {typ(v)} | {' '.join(flags)} | {enum} | {ko(v.get('description'))[:400]} |")
        models.append("")
    if "example" in d:
        models += ["명세 example:", "```json", json.dumps(d["example"], ensure_ascii=False, indent=2)[:2000], "```", ""]
(OUT / "06-models.md").write_text("\n".join(models) + "\n", encoding="utf-8")

missing = [f"{m.upper()} {public_path(p)}" for f, _, m, p, _, _ in ops if f"{m.upper()} {public_path(p)}" not in names]
print("ops", n, "models", len(seen), "missing names", len(missing))
for x in missing:
    print("  ", x)
