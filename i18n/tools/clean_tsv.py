"""Clean up the TSV: remove known noise entries."""
import csv, sys

# Noise to remove: strings that are NOT user-visible but slipped through
NOISE = {
    "in + out",
    "not available",
    "window",
    "5-hour",
    "Weekly",
    "SSH {host}",
    "loading session…",
    "model -> loading session… -> model",
}

# Files to skip entirely (noise collectors)
SKIP_FILES = {}  # (path_substring,) set

rows = []
with open("/tmp/opencode/inv_input.tsv", 'r', encoding='utf-8') as f:
    reader = csv.reader(f, delimiter='\t')
    for row in reader:
        if len(row) != 3:
            continue
        path, line, text = row
        # Skip noise
        if text.strip() in NOISE:
            continue
        # Skip very short strings with no content
        if text.strip() == '' or text.strip() == ' ':
            continue
        rows.append(row)

writer = csv.writer(sys.stdout, delimiter='\t', quoting=csv.QUOTE_MINIMAL, escapechar='\\')
for row in rows:
    writer.writerow(row)

sys.stderr.write(f"Total: {len(rows)}\n")
from collections import Counter
cnt = Counter()
for r in rows:
    short = r[0].replace("/home/ilya/Program/jcode/crates/jcode-tui/src/tui", "…/tui")
    cnt[short] += 1
for fp, c in cnt.most_common():
    sys.stderr.write(f"  {fp}: {c}\n")
