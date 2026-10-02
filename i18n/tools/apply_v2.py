#!/usr/bin/env python3
"""Apply TSV-protocol translations (idx -> ru|SKIP) to jcode Rust sources.

Input : /tmp/opencode/nb/b*.tsv   (idx, file, line, raw_en, source_line)
Output: /tmp/opencode/ntr/b*.tsv  (idx \t ru | idx \t SKIP)

Validation per row:
- output file must have exactly N lines, indices 1..N in order
- ru must not contain real tab/newline/double-quote
- placeholder multiset must match
- backslash-escape multiset must match (only \n and \t allowed in ru)

Writes a report to /tmp/opencode/apply_v2_report.json
"""
import os, re, glob, json
from collections import Counter

ROOT = "/home/ilya/Program/jcode"
NB = "/tmp/opencode/nb"
NTR = "/tmp/opencode/ntr"
REPORT = "/tmp/opencode/apply_v2_report.json"

LIT = re.compile(r'"((?:\\.|[^"\\])*)"')
PH = re.compile(r"\{[^{}]*\}")
ESC = re.compile(r"\\[nrt\"\\]")

def apply():
    applied = skipped = invalid = 0
    problems = []
    file_cache = {}
    for nb in sorted(glob.glob(os.path.join(NB, "b*.tsv"))):
        name = os.path.basename(nb)[:-4]
        ntr = os.path.join(NTR, name + ".tsv")
        if not os.path.exists(ntr):
            problems.append({"batch": name, "error": "no output"})
            continue
        rows = []
        for line in open(nb, encoding="utf-8"):
            p = line.rstrip("\n").split("\t")
            if len(p) >= 4:
                rows.append((p[0], p[1], int(p[2]), p[3]))
        N = len(rows)
        parsed = {}
        for l in open(ntr, encoding="utf-8").read().splitlines():
            l = l.strip()
            if not l:
                continue
            m = re.match(r"^(\d+)\s*:\s*\d+\s*\t(.*)$", l)
            if m:
                parsed[int(m.group(1))] = m.group(2)
                continue
            m = re.match(r"^(\d+)\t(.*)$", l)
            if m:
                parsed[int(m.group(1))] = m.group(2)
        missing_idx = [i for i in range(1, N + 1) if i not in parsed]
        if missing_idx:
            problems.append({"batch": name, "error": f"missing idx {missing_idx[:20]}"})
        per_line = {}
        for (idx0, fn, ln, en) in rows:
            idx = int(idx0)
            ru = parsed.get(idx)
            if ru is None or ru == "SKIP" or ru.strip() == "":
                skipped += 1
                continue
            if any(c in ru for c in "\t\n\r\"") or "\\" in ru.replace("\\n", "").replace("\\t", ""):
                invalid += 1
                problems.append({"batch": name, "idx": idx, "reason": "bad chars", "ru": ru})
                continue
            if Counter(PH.findall(en)) != Counter(PH.findall(ru)):
                invalid += 1
                problems.append({"batch": name, "idx": idx, "reason": "placeholder",
                                 "en": en, "ru": ru})
                continue
            if Counter(ESC.findall(en)) != Counter(ESC.findall(ru)):
                invalid += 1
                problems.append({"batch": name, "idx": idx, "reason": "escape",
                                 "en": en, "ru": ru})
                continue
            per_line.setdefault((fn, ln, en), ru)

        for (fn, ln, en), ru in per_line.items():
            path = os.path.join(ROOT, fn)
            if path not in file_cache:
                try:
                    file_cache[path] = open(path, encoding="utf-8").read().splitlines()
                except Exception as e:
                    problems.append({"batch": name, "file": fn, "error": str(e)})
                    file_cache[path] = None
            lines = file_cache[path]
            if lines is None or ln - 1 >= len(lines):
                invalid += 1
                continue
            src = lines[ln - 1]
            done = False
            for m in LIT.finditer(src):
                if m.group(1) == en:
                    src = src[:m.start()] + '"' + ru + '"' + src[m.end():]
                    done = True
                    break
            if done:
                applied += 1
            else:
                invalid += 1
                problems.append({"batch": name, "file": fn, "line": ln,
                                 "reason": "literal not found", "en": en})
            lines[ln - 1] = src

    for path, lines in file_cache.items():
        if lines is not None:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")
    rep = {"applied": applied, "skipped": skipped, "invalid": invalid,
           "problems": problems}
    json.dump(rep, open(REPORT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"applied={applied} skipped={skipped} invalid={invalid} problems={len(problems)}")
    from collections import Counter as C
    print("problem reasons:", C(p.get("reason") or p.get("error") for p in problems))

if __name__ == "__main__":
    apply()
