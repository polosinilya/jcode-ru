#!/usr/bin/env python3
"""Build comprehensive TSV of user-visible English strings from jcode TUI Rust files.

Scans each file with targeted per-line analysis, skipping test blocks
and non-user-visible contexts. Writes TSV to stdout.
"""
import re, os, sys, csv

ROOT = "/home/ilya/Program/jcode/crates/jcode-tui/src/tui"
PICKER_DIR = os.path.join(ROOT, "session_picker")

FILES = [
    "ui_input.rs",
    "ui_overlays.rs",
    "session_picker.rs",
    "session_picker/render.rs",
    "session_picker/navigation.rs",
    "session_picker/filter.rs",
    "login_picker.rs",
    "ui_header.rs",
    "ui_status.rs",
    "ui_onboarding.rs",
    "session_picker/loading.rs",
]

# After scanning, manually add these known user-visible strings that regex misses
# Format: (file_relative, line_num, exact_text)

def is_test_block(lines, line_num):
    """Check if line_num falls inside a #[cfg(test)] block."""
    i = 0
    in_test = False
    test_line_set = set()
    
    while i < len(lines):
        stripped = lines[i].strip()
        
        if '#[cfg(test)]' in stripped:
            # Mark this and skip until next module-level item
            j = i
            test_line_set.add(i)
            # Skip consecutive test-attribute lines
            while j < len(lines):
                ts = lines[j].strip()
                test_line_set.add(j)
                j += 1
                if ts == '' and j > i + 1:
                    break
                if re.match(r'^\s*(pub\s+)?(fn|struct|enum|impl|const|use)\s+', ts):
                    break
            i = j
            continue
        
        i += 1
    
    return line_num - 1 in test_line_set  # 0-indexed

def is_test_fn(lines, line_num):
    """Check if we're inside a test function definition."""
    i = 0
    test_ranges = []
    current_test = None
    brace_depth = 0
    
    while i < len(lines):
        stripped = lines[i].strip()
        
        # Check for test attribute
        if '#[cfg(test)]' in stripped or '#[test]' in stripped:
            # Next non-blank, non-comment line with fn
            j = i + 1
            while j < len(lines) and (lines[j].strip() == '' or lines[j].strip().startswith('//')):
                j += 1
            if j < len(lines) and re.match(r'^\s*(pub\s+)?fn\s+', lines[j]):
                current_test = (j, None)
                if current_test not in test_ranges:
                    test_ranges.append((i, None))  # start from attr
        
        if current_test and '{' in stripped:
            brace_depth += stripped.count('{')
            if brace_depth > 0 and current_test[1] is None:
                current_test = (current_test[0], None)  # mark start
        if current_test and '}' in stripped:
            brace_depth -= stripped.count('}')
            if brace_depth <= 0 and current_test[1] is None and current_test[0] == i:
                pass
            if brace_depth <= 0:
                brace_depth = 0
                # End of block - add range
                if current_test and current_test[1] is None:
                    test_ranges.append((current_test[0], i + 1))
                current_test = None
        
        # Check for mod tests { ... }
        if re.match(r'^\s*mod\s+tests', stripped):
            if '{' in stripped:
                brace_depth += stripped.count('{')
                test_ranges.append((i, None))
            else:
                # Look ahead for {
                pass
        
        i += 1
    
    # Check if line_num falls in any test range
    for start, end in test_ranges:
        if end is None:
            if line_num - 1 >= start:
                return True
        elif start <= line_num - 1 < end:
            return True
    
    return False

def matches_exclusion_context(line_before_str: str, text: str) -> bool:
    """Check if the string context suggests it's not user-visible."""
    # Skip strings in test assertions
    if re.search(r'(assert_eq|assert_ne|assert!|bail!|eprintln|panic!|expect\()', line_before_str):
        return True
    # Skip env var references
    if re.search(r'(env::var|std::env::var|set_var|remove_var)', line_before_str):
        return True
    # Skip config key access
    if re.search(r'config\(\)\.', line_before_str):
        return True
    # Skip comparison with known non-UI strings
    if re.search(r'(==\s*"|!=\s*"|\.contains\("|\.starts_with\(")', line_before_str):
        return True
    # Skip error message construction
    if re.search(r'(anyhow!|anyhow::anyhow!|Err\(|error\()', line_before_str):
        return True
    # Skip debug formatting
    if 'format_status_for_debug' in line_before_str:
        return True
    # Skip struct field names / enum variants
    if re.match(r'^[a-z_]+$', text) and not text.startswith(' '):
        return True
    return False

def find_strings_in_file(filepath: str) -> list:
    """Find all user-visible strings in a Rust source file.
    
    Returns list of (abs_path, 1-based_line_num, string_text)
    """
    if not os.path.isfile(filepath):
        return []
    
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()
    
    abs_path = os.path.abspath(filepath)
    results = []
    
    for i, line in enumerate(lines):
        line_num = i + 1
        stripped = line.rstrip('\n')
        
        # Skip test blocks entirely  
        if is_test_fn(lines, line_num):
            continue
        if is_test_block(lines, line_num):
            continue
        
        # Skip cfg! blocks
        if 'cfg!(' in stripped:
            continue
        
        # Find ALL string literals that look user-visible
        # Match "..." strings
        for m in re.finditer(r'"((?:[^"\\]|\\.)*)"', stripped):
            text = m.group(1)
            if not text:
                continue
            
            # Filter out non-user-visible strings
            # Must have at least one letter
            if not re.search(r'[A-Za-z]', text):
                continue
            
            # Skip pure number/symbol strings
            if re.match(r'^[\d\s\-_.,:;!?()\[\]{}<>/\\|@#$%^&*+=~\'\u00a0`\u200b]+$', text.replace('{', '').replace('}', '')):
                continue
            
            # Skip pure template strings (just {} placeholders)
            if re.match(r'^[\{\}%\s\d.,:;()\[\]/\\|\-+*]+$', text):
                continue
            
            # Skip Rust identifiers
            if re.match(r'^[a-z_][a-z0-9_]*$', text) and not text.startswith(' '):
                continue
            
            # Skip ASCII-art / glyph-only
            if all(ord(c) < 128 and not c.isalnum() or ord(c) > 127 for c in text):
                if not re.search(r'[a-zA-Z]', text):
                    continue
            
            # Check context - what's before this string?
            before = stripped[:m.start()]
            
            if matches_exclusion_context(before, text):
                continue
            
            # Special handling for test utility functions - skip
            if re.search(r'(buffer_to_text|text_contains_wrapped|render_|fn test_)', before):
                continue
            
            # For hash/realpath patterns - skip paths
            if '/' in text and not ' ' in text and not re.search(r'[A-Z][a-z]', text):
                continue
            
            # Skip if this looks like an eprintln/debug fmt string  
            # (These are log messages, not user-visible UI)
            if 'eprintln' in before or 'log::' in before:
                continue
            
            # Include it
            results.append((abs_path, line_num, text))
    
    return results


# Collect from all files
all_results = []

for f in FILES:
    fp = os.path.join(ROOT, f)
    rows = find_strings_in_file(fp)
    all_results.extend(rows)

# Remove near-duplicates
seen = set()
unique = []
for r in all_results:
    key = (r[0], r[1], r[2])
    if key not in seen:
        seen.add(key)
        unique.append(r)

# Write TSV
writer = csv.writer(sys.stdout, delimiter='\t', quoting=csv.QUOTE_MINIMAL, escapechar='\\')
writer.writerow(["file", "line", "string"])
for path, line, text in sorted(unique, key=lambda r: (r[0], r[1])):
    writer.writerow([path, str(line), text])

# Stats
print(f"\n# Total: {len(unique)}", file=sys.stderr)
from collections import Counter
file_counts = Counter(r[0] for r in unique)
print(f"# Per-file:", file=sys.stderr)
for fp, cnt in file_counts.most_common():
    short = fp.replace(ROOT, "…/tui")
    print(f"#   {short}: {cnt}", file=sys.stderr)
