#!/usr/bin/env python3
"""Extract user-visible English string literals for the jcode TUI help/command surfaces. v2 refined."""
import re, os, csv
from collections import Counter

BASE = "/home/ilya/Program/jcode"

TARGET_FILES = [
    f"{BASE}/crates/jcode-tui/src/tui/app/input_help.rs",
    f"{BASE}/crates/jcode-tui/src/tui/app/state_ui_input_helpers.rs",
    f"{BASE}/crates/jcode-tui/src/tui/ui_overlays.rs",
    f"{BASE}/crates/jcode-tui/src/tui/app/shortcut_hints.rs",
    f"{BASE}/crates/jcode-tui/src/tui/ui_onboarding.rs",
    f"{BASE}/crates/jcode-tui/src/tui/info_widget_tips.rs",
    f"{BASE}/crates/jcode-tui/src/tui/ui_input.rs",
    f"{BASE}/crates/jcode-tui/src/tui/app/model_context.rs",
    f"{BASE}/crates/jcode-tui/src/tui/keybind.rs",
    f"{BASE}/crates/jcode-tui/src/tui/app/onboarding_sim.rs",
]

rows = []
STRING_PAT = re.compile(r'"((?:[^"\\]|\\.)*)"', re.DOTALL)

# Function names whose body contains only enum->label mapping (keep labels, skip the enum name match values)
LABEL_FUNCTIONS = {
    "connection_phase_label",
    "display_connection_type",
    "normalize_status_detail",
}

def is_format_only_fragment(s):
    """True if the string is only formatting placeholders/punctuation sans English words."""
    stripped = s.strip()
    if not stripped:
        return True
    # If it contains at least one English letter (a-z, A-Z) not inside a placeholder, keep it
    return not bool(re.search(r'(?<!\{)[A-Za-z]', stripped))

def is_user_visible(s, line_text):
    s_stripped = s.strip()
    if not s_stripped or len(s_stripped) < 2:
        return False
    # Must contain at least one ASCII letter (outside placeholders)
    if not re.search(r'(?<!\{)[A-Za-z]', s_stripped):
        return False
    # Skip pure-symbol/whitespace lines
    if re.match(r'^[\s\-_·•↑↓←→↖↗↘↙↻↩↪↔↕⏎✓✗⚠ℹ⚡⏳◖◗▐▌●○▸〉\+\-#\d\{\}\[\]\(\)\.\,\/\|\\\!\;\:\=\%\^]+$', s_stripped):
        return False
    return True

def extract_strings_from_rust(code, filepath):
    in_label_fn = False
    for match in STRING_PAT.finditer(code):
        lineno = 1 + code[:match.start()].count('\n')
        raw = match.group(1)
        s = raw.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"').replace("\\'", "'").replace('\\\\', '\\')
        
        if not s.strip():
            continue
        
        # Get context
        start = max(0, code.rfind('\n', 0, match.start()) + 1)
        end = code.find('\n', match.end())
        if end == -1:
            end = len(code)
        line_text = code[start:end].strip()
        
        # Skip obvious non-user-visible patterns
        if any(line_text.startswith(p) for p in ['use ', '//', 'fn ', 'pub(', 'pub ', 'mod ', 
                                                  'type ', 'const ', 'struct ', 'enum ', 'impl ',
                                                  '#[cfg', '#[test', '#[path', 'crate::logging',
                                                  'eprintln', 'serde_json::json',
                                                  'Self::', 'register_commands', 'allow(']):
            continue
        
        # Skip test assertion strings
        if 'assert_eq' in line_text or 'assert!' in line_text:
            continue
        
        if is_user_visible(s, line_text):
            rows.append((filepath, lineno, s))

# Process each file
for fp in TARGET_FILES:
    if not os.path.exists(fp):
        print(f"WARNING: file not found: {fp}")
        continue
    with open(fp, 'r', errors='replace') as f:
        code = f.read()
    extract_strings_from_rust(code, fp)

# Sort
rows.sort(key=lambda r: (r[0], r[1]))

# Write TSV
outpath = "/tmp/opencode/inv_help.tsv"
with open(outpath, 'w', newline='') as f:
    writer = csv.writer(f, delimiter='\t', quoting=csv.QUOTE_MINIMAL, escapechar='\\')
    for fp, lineno, s in rows:
        escaped = s.replace('\\', '\\\\').replace('\t', '\\t').replace('\n', '\\n')
        writer.writerow([fp, str(lineno), escaped])

print(f"TSV written: {outpath}")
print(f"Total rows: {len(rows)}")

# Per-file counts
file_counts = Counter(fp for fp, _, _ in rows)
print("\nPer-file counts (top 20):")
for fp, cnt in file_counts.most_common(20):
    short = fp.replace(BASE, '')
    print(f"  {cnt:4d}  {short}")

# Command descriptions
print("\n10 representative command/help descriptions:")
cnt = 0
for fp, lineno, s in rows:
    if re.match(r'^(Show|Toggle|Launch|List|Open|Alias|Use|Set|Pin|Create|Cycle|Diagnose|Render|Force|Clear|Rewind|Refre|Add|Remo)', s) and len(s) > 20:
        print(f"  [{os.path.relpath(fp, BASE)}:{lineno}] {repr(s[:130])}")
        cnt += 1
        if cnt >= 10:
            break

# Status hints
print("\n5 user-facing status/hint strings:")
cnt = 0
for fp, lineno, s in rows:
    if re.search(r'(session|keyboard|press|scroll|type to|no matches|help overlay|connected|queued|waiting|running)', s, re.I) and len(s) < 100 and len(s) > 5:
        if s not in [r[2] for r in rows[:rows.index((fp, lineno, s))] if r[2] == s]:
            print(f"  [{os.path.relpath(fp, BASE)}:{lineno}] {repr(s[:130])}")
            cnt += 1
            if cnt >= 5:
                break

print(f"\nFile: {outpath}")
