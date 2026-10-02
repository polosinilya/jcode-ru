#!/usr/bin/env python3
"""Extract user-visible English string literals from jcode TUI source.

Specifically:
  - String literal arguments to set_status_notice(...) calls
  - Strings from info_widget_tips.rs (tips)
  - Onboarding welcome strings from ui_onboarding.rs
  - Startup/loading/empty-state messages

Writes /tmp/opencode/inv_status.tsv (file<TAB>line<TAB>string).
"""
import os, re, sys, json
from collections import Counter

TUI_DIR = "/home/ilya/Program/jcode/crates/jcode-tui/src/tui"
OUTPUT = "/tmp/opencode/inv_status.tsv"

# ---- Helpers ----

def collapse_whitespace(s: str) -> str:
    return re.sub(r'\s+', ' ', s).strip()


def extract_literal(arg_text: str) -> str | None:
    """Extract a user-visible string literal from a set_status_notice argument.
       Handles:
         "plain string"
         format!("template", ...)
         "prefix" + "suffix" (concatenation)
         format!("{x}", ...) with placeholders
    """
    arg = arg_text.strip()

    # Case 1: Simple "string literal"
    if arg.startswith('"'):
        m = re.match(r'"((?:[^"\\]|\\.)*)"', arg)
        if m:
            val = m.group(1)
            if val:
                return collapse_whitespace(val)
            return None
        return None

    # Case 2: format!("template", ...)
    if arg.startswith('format!(') or arg.startswith('format ('):
        inner = arg[arg.index('(')+1:]
        m = re.match(r'\s*"((?:[^"\\]|\\.)*)"', inner)
        if m:
            template = m.group(1)
            if template:
                return collapse_whitespace(template)
            return None
        return None

    # Case 3: String concatenation with +
    if '+' in arg:
        parts = re.split(r'\s*\+\s*', arg)
        extracted = []
        for part in parts:
            part = part.strip()
            if part.startswith('"') and part.endswith('"'):
                inner = part[1:-1]
                if inner:
                    extracted.append(collapse_whitespace(inner))
            elif part.startswith('format!(') or part.startswith('format ('):
                m = re.search(r'format!?\(\s*"((?:[^"\\]|\\.)*)"', part)
                if m:
                    t = m.group(1)
                    if t:
                        extracted.append(collapse_whitespace(t))
        if extracted:
            return ' '.join(extracted)
        return None

    return None


def collect_set_status_notice_strings(filepath: str) -> list[tuple[int, str]]:
    """Collect all set_status_notice(string) calls in a Rust file.
       Returns list of (line_number_1based, string_content).
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    results = []
    i = 0
    while i < len(lines):
        line = lines[i]
        idx = line.find('set_status_notice(')
        if idx == -1:
            i += 1
            continue

        # Find opening paren after set_status_notice
        paren_start = line.index('(', idx + len('set_status_notice'))
        depth = 1
        buf = []
        j = paren_start + 1

        while i < len(lines):
            while j < len(lines[i]):
                ch = lines[i][j]
                if ch == '(':
                    depth += 1
                    buf.append(ch)
                elif ch == ')':
                    depth -= 1
                    if depth == 0:
                        arg_text = ''.join(buf).strip()
                        extracted = extract_literal(arg_text)
                        if extracted:
                            results.append((i + 1, extracted))
                        j += 1
                        break
                    else:
                        buf.append(ch)
                else:
                    buf.append(ch)
                j += 1
            else:
                buf.append('\n')
                i += 1
                j = 0
                continue
            break
        i += 1
    return results


def collect_string_literals_in_file(filepath: str, min_len: int = 3) -> list[tuple[int, str]]:
    """Collect all double-quoted string literals from a Rust file.
       Filters out code identifiers, paths, env vars.
       Returns list of (line_number_1based, string_content).
    """
    results = []
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('//') or stripped.startswith('#'):
            continue
        if 'cfg!(test)' in stripped:
            continue
        for m in re.finditer(r'"((?:[^"\\]|\\.)*)"', stripped):
            val = m.group(1)
            if not val or len(val) < min_len:
                continue
            # Filter out non-user-visible strings
            if val.startswith(('/', '$', '%', '@', '\\')):  # paths, env vars, escapes
                continue
            if val == ' ' or val.isdigit():
                continue
            # Keep strings that look user-visible
            if val[0].isupper() or ' ' in val or any(c in val for c in '.,!?;:-'):
                results.append((i, collapse_whitespace(val)))
    return results


# ---- Main ----

def main():
    all_rows = []  # (file_path, line_num, string_content)

    # 1. All set_status_notice files (50)
    with open("/tmp/opencode/set_status_notice_files.txt", 'r') as f:
        files = [l.strip() for l in f if l.strip()]

    for path in files:
        if os.path.exists(path):
            rows = collect_set_status_notice_strings(path)
            for line_num, text in rows:
                all_rows.append((path, line_num, text))
        else:
            print(f"Warning: file not found: {path}", file=sys.stderr)

    # 2. Info_widget_tips.rs - the tip strings
    tips_path = os.path.join(TUI_DIR, "info_widget_tips.rs")
    if os.path.exists(tips_path):
        with open(tips_path, 'r') as f:
            content = f.read()
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            for m in re.finditer(r'"((?:[^"\\]|\\.)*)"', line):
                val = m.group(1)
                if not val or len(val) < 5:
                    continue
                if val == '💡 ':
                    continue
                all_rows.append((tips_path, i, collapse_whitespace(val)))

    # 3. ui_onboarding.rs - onboarding welcome strings
    onboarding_path = os.path.join(TUI_DIR, "ui_onboarding.rs")
    if os.path.exists(onboarding_path):
        with open(onboarding_path, 'r') as f:
            content = f.read()
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('//') or 'cfg!(test)' in stripped:
                continue
            # Collect user-facing string literals
            for m in re.finditer(r'"((?:[^"\\]|\\.)*)"', stripped):
                val = m.group(1)
                if not val or len(val) < 3:
                    continue
                if val.startswith(('/', '$', '%', '\\')):
                    continue
                if val in (' ', '', 'Yes', 'No', 'Continue'):
                    all_rows.append((onboarding_path, i, val))
                    continue
                if val[0].isupper() or ' ' in val or any(c in val for c in '.,!?;:-'):
                    all_rows.append((onboarding_path, i, collapse_whitespace(val)))

    # 4. Session picker - loading/empty state string "Untitled"
    loading_path = os.path.join(TUI_DIR, "session_picker", "loading.rs")
    if os.path.exists(loading_path):
        with open(loading_path, 'r') as f:
            lines = f.readlines()
        for i, line in enumerate(lines, 1):
            if '"Untitled"' in line:
                all_rows.append((loading_path, i, "Untitled"))

    # 5. Additional startup/loading/empty-state files that may have non-set_status_notice strings
    extra_files = [
        "session_picker/render.rs",
        "session_picker.rs",
        "ui_prepare.rs",
        "app/local.rs",
        "app/state_ui.rs",
        "app/conversation_state.rs",
        "app/state_ui_runtime.rs",
        "app/tui_lifecycle.rs",
        "app/state_ui_maintenance.rs",
        "app/misc_ui.rs",
    ]
    for relpath in extra_files:
        path = os.path.join(TUI_DIR, relpath)
        if os.path.exists(path):
            rows = collect_set_status_notice_strings(path)
            for line_num, text in rows:
                all_rows.append((path, line_num, text))

    # Deduplicate by (file, line, text)
    seen = set()
    deduped = []
    for path, line_num, text in all_rows:
        key = (path, line_num, text)
        if key not in seen:
            seen.add(key)
            deduped.append((path, line_num, text))

    deduped.sort(key=lambda x: (x[0], x[1]))

    # Write TSV
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        for path, line_num, text in deduped:
            escaped = text.replace('\t', '\\t').replace('\n', '\\n')
            f.write(f"{path}\t{line_num}\t{escaped}\n")

    # Print summary
    print(f"TSV written to: {OUTPUT}")
    print(f"Total rows: {len(deduped)}")

    file_counts = Counter(p for p, _, _ in deduped)
    print(f"\nPer-file counts (top 15):")
    for path, count in file_counts.most_common(15):
        short = path.replace(TUI_DIR, '')
        print(f"  {count:4d}  ...{short}")

    print(f"\n10 representative examples:")
    count = 0
    for path, line_num, text in deduped:
        if count >= 10:
            break
        short = path.replace(TUI_DIR, '')
        preview = text[:90] + ('...' if len(text) > 90 else '')
        print(f"  ...{short}:{line_num}  \"{preview}\"")
        count += 1

if __name__ == '__main__':
    main()
