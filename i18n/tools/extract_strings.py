#!/usr/bin/env python3
"""Extract user-visible English string literals from jcode TUI Rust source files."""
import re, sys, os, csv, io

ROOT = "/home/ilya/Program/jcode/crates/jcode-tui/src/tui"

# Files to scan, in priority order
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
    "ui.rs",
]
# Also check picker subdirectory
PICKER_DIR = os.path.join(ROOT, "session_picker")

# Patterns: which functions/call-sites to exclude
EXCLUDE_PATTERNS = [
    r'title_bottom\(Line::from\(Span::styled\("',  # help overlay bottom bars (captured separately)
]

def should_exclude_line(line: str) -> bool:
    for pat in EXCLUDE_PATTERNS:
        if re.search(pat, line):
            return True
    return False

def extract_strings_from_file(filepath: str) -> list[tuple[str, int, str]]:
    """Extract user-visible string literals from a Rust file.
    
    Returns list of (abs_path, line_number, literal_text).
    """
    results = []
    
    if not os.path.isfile(filepath):
        return results
    
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()
    
    abs_path = os.path.abspath(filepath)
    
    # State tracking
    in_test_block = False
    in_comment = False
    in_debug_cfg = False
    
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        line_num = i + 1
        
        # Track test blocks
        if re.match(r'^\s*#\[cfg\(test\)\]', stripped):
            # Look ahead for the next non-comment, non-blank line
            j = i + 1
            while j < len(lines) and (lines[j].strip() == '' or lines[j].strip().startswith('//')):
                j += 1
            if j < len(lines) and re.match(r'^\s*mod\s+tests', lines[j]):
                in_test_block = True
            elif j < len(lines) and re.match(r'^\s*(pub\s+)?(fn|struct|enum|impl|const|use)', lines[j]):
                pass  # attribute on non-test function
            else:
                in_test_block = True
        
        if re.match(r'^\s*mod\s+tests', stripped) and not in_test_block:
            in_test_block = True
        
        if in_test_block and stripped == '}':
            # Could be end of test module — conservative: assume test blocks end with a close brace at col 0
            # But that's too aggressive. Let's use proper tracking.
            pass
        
        # Skip lines inside #[cfg(test)] blocks - check for this more carefully
        if '#[cfg(test)]' in line:
            in_test_block = True
        
        # End test block detection
        if in_test_block:
            # Check if we've reached a non-test function / non-impl block
            # This is heuristic; for safety we'll just skip all string extraction
            # inside known test modules
            pass
        
        # Reset test block detection at module boundaries
        if re.match(r'^\s*use\s+', stripped):
            pass  # imports are fine
        
        if re.match(r'^\s*fn\s+', stripped) and 'test' in stripped.split('fn')[1].split('(')[0]:
            in_test_block = True
            
        # Simple: if we've seen a test attribute or test fn, skip until we see a non-test fn
        # Actually let's just track it properly
        
        i += 1
    
    # Reset and do a simpler pass
    results = []
    in_test_block_lines = set()
    
    # First pass: mark test blocks
    i = 0
    depth = 0
    in_test = False
    test_mod_start = -1
    
    while i < len(lines):
        stripped = lines[i].strip()
        if '#[cfg(test)]' in stripped or stripped == '#[test]':
            in_test = True
            # Mark until the next fn without #[test] or until end of impl block
            # Just mark this line and a few ahead
            for j in range(i, min(i + 5, len(lines))):
                in_test_block_lines.add(j)
        if re.match(r'^\s*fn\s+.+_test', stripped) or re.match(r'^\s*fn\s+test_', stripped):
            in_test_block_lines.add(i)
        if re.match(r'^\s*mod\s+tests', stripped):
            in_test = True
            test_mod_start = i
        if in_test and stripped == '}':
            depth -= 1 if depth > 0 else 0
            if depth == 0 and test_mod_start >= 0 and i > test_mod_start + 2:
                # End of test module (approximate)
                in_test = False
                test_mod_start = -1
        if in_test:
            in_test_block_lines.add(i)
        if '{' in stripped and in_test:
            depth += stripped.count('{')
        i += 1
    
    # Second pass: extract strings
    i = 0
    while i < len(lines):
        line = lines[i]
        line_num = i + 1
        
        # Skip test blocks
        if i in in_test_block_lines:
            i += 1
            continue
        
        # Skip comment-only lines
        if stripped.strip().startswith('//') and not any(c in stripped for c in ['"']):
            i += 1
            continue
        
        # Find all string literals on this line that look user-visible
        # Match "...some text..." patterns in Span::styled, format!, "literal" in format args, etc.
        
        # Strategy: find string literals that contain spaces (multi-word) or are 
        # clearly user-facing labels
        strings_on_line = []
        
        # Match double-quoted strings that are at least 3 chars of printable text
        for match in re.finditer(r'"((?:[^"\\]|\\.)*)"', line):
            s = match.group(1)
            if not s:
                continue
            # Skip if it's clearly a test assertion, path, identifier, config key
            if s.startswith('/') and len(s) < 50:
                continue  # paths and single tokens
            if s in ['_', ' ', '', '  ', '   ']:
                continue
            if s.startswith('\\') or s.startswith('\x1b') or s.startswith('\u'):
                continue
            # Skip pure ASCII art / single chars used as glyphs
            if all(c in ' █▄▀▐▌│╭╮╰╯─═╴╵├┤┬┴└┘┌┐▸▹◖◗●○◐◑◆◇☐☑✓✗✕⚠↻↗⏳⚡➕🗑📋📌📁📦🔍🧠🧪🔄💥✂💾🔬🔌🌐🐏🦊🐧⭐🔷🔶🔴🟢🟡🟣🟦⬤' for c in s):
                continue
            # Skip if it's only numbers/symbols
            if re.match(r'^[\d\s\.\,\:\;\(\)\[\]\{\}/\\\|\-\+\*\#\@\!\%\^\&\=\~\`\'\<\>]+$', s):
                continue
            # Must have at least one alphabetic character
            if not re.search(r'[a-zA-Z]', s):
                continue
            
            # Check if this is a user-visible string in context
            # Look at the surrounding context to determine
            context_before = line[:match.start()]
            
            # Skip strings used in assertions (==, !=, assert_eq, etc.)
            if re.search(r'assert|expect|bail|panic|error!', context_before):
                continue
            
            # Skip error! / bail! messages
            if 'bail!' in context_before or 'error!' in context_before:
                continue
            
            # Skip if inside a test attribute
            if '#[test]' in context_before or '#[cfg(test)]' in context_before:
                continue
            
            # Skip strict matching (== / != / .contains()) strings
            if re.search(r'\.contains\(|==\s*"|!=\s*"|starts_with\("', context_before):
                continue
            
            # Skip if used as format string template for non-user-visible content
            # like env vars, file paths, config keys
            if any(kw in context_before for kw in ['env::var', 'set_var', 'remove_var', 
                                                      'config().', 'format!("{}', 'config::']):
                if len(s) < 20 and not s.startswith(' ') and ' ' not in s[1:]:
                    continue
            
            strings_on_line.append((match.start(), s))
        
        if strings_on_line:
            for (col, text) in strings_on_line:
                results.append((abs_path, line_num, text))
        
        i += 1
    
    return results

# Actually, the regex approach is too fragile. Let me do a more targeted extraction
# by reading specific files and looking at specific patterns.

def extract_visible_strings_expert(filepath: str) -> list[tuple[str, int, str]]:
    """Expert extraction of user-visible strings using known patterns."""
    results = []
    if not os.path.isfile(filepath):
        return results
    
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
        lines = content.split('\n')
    
    abs_path = os.path.abspath(filepath)
    
    # Track test blocks
    in_test_or_attribute = False
    
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        
        # Skip test blocks
        if '#[cfg(test)]' in stripped or '#[test]' in stripped:
            in_test_or_attribute = True
            continue
        
        if in_test_or_attribute:
            # Stay in test mode until we see a non-test fn or struct definition
            if re.match(r'^\s*(pub\s+)?(fn|struct|enum|impl|const)\s+', stripped):
                in_test_or_attribute = False
            continue
        
        # Skip lines inside cfg! blocks
        if 'cfg!(' in stripped:
            continue
        
        # Find Span::styled("...") patterns - these are ALWAYS user-visible
        for match in re.finditer(r'Span::styled\(("[^"]*")\s*,', line):
            s = match.group(1)
            text = s[1:-1]  # strip quotes
            # Skip empty, whitespace-only, or single chars
            if not text or all(c in ' ' for c in text):
                continue
            results.append((abs_path, i, text))
        
        # Find Line::from(Span::styled("..."))  
        for match in re.finditer(r'Span::styled\("([^"]*)"', line):
            pass  # Already captured above
        
        # Find format!("...") where the content looks user-visible
        for match in re.finditer(r'format!\(("[^"]*")', line):
            s = match.group(1)
            text = s[1:-1]
            if not text or all(c in ' ' for c in text):
                continue
            # Skip template-only strings (just placeholders)
            if re.match(r'^[\{\}%a-zA-Z0-9_\s\.\,\;\:\(\)\[\]\-\+\/]+$', text):
                # Only include if it has actual English words, not just format specifiers
                # Check for meaningful text content
                pass
            # Include anything with actual words
            if re.search(r'[A-Za-z]{3,}', text):
                results.append((abs_path, i, text))
        
        # Find direct "...string..." used in UI contexts like:
        # - Paragraph::new("...")
        # - title("...")
        # - Line::from(vec![...])
        # - "Esc to", "Enter to", etc.
        for match in re.finditer(r'(?<!Span::styled\()"((?:[^"\\]|\\.)*)"(?!\s*\))', line):
            # Check context: is this a user-visible string?
            context_before = line[:match.start()]
            text = match.group(1)
            
            if not text:
                continue
            if all(c in ' █▄▀▐▌│╭╮╰╯─═╴╵├┤┬┴└┘┌┐▸▹◖◗●○◐◑◆◇☐☑✓✗✕⚠↻↗⏳⚡➕🗑📋📌📁📦🔍🧠🧪🔄💥✂💾🔬🔌🌐🐏🦊🐧⭐🔷🔶🔴🟢🟡🟣🟦⬤' for c in text):
                continue
            if re.match(r'^[\d\s\.\,\:\;\(\)\[\]\{\}/\\\|\-\+\*\#\@\!\%\^\&\=\~\`\'\<\>]+$', text):
                continue
            if not re.search(r'[a-zA-Z]', text):
                continue
            
            # Context-based filtering
            # Skip assertions
            if re.search(r'(assert|expect|bail|eprintln|debug!|panic)', context_before):
                continue
            # Skip strict comparisons
            if re.search(r'(==\s*"|!=\s*"|\.contains\(")', context_before):
                continue
            # Skip env vars, config keys
            if re.search(r'(env::var|config\(\)\.|std::env\.)', context_before):
                continue
            # Skip format strings used as simple templates
            if re.match(r'^[\{\}]*(\(|\))', text) and not re.search(r'[A-Za-z]{3}', text):
                continue
            
            # Include interesting strings
            results.append((abs_path, i, text))
    
    return results

# Merge results from both approaches, deduplicate by (file, line, text)
seen = set()

def collect(filepath: str):
    global seen
    rows = extract_visible_strings_expert(filepath)
    for row in rows:
        key = (row[0], row[1], row[2])
        if key not in seen:
            seen.add(key)

# Collect from primary files
for f in FILES:
    fp = os.path.join(ROOT, f)
    collect(fp)

# Collect from session_picker submodules
for fname in ["loading.rs", "memory.rs"]:
    fp = os.path.join(PICKER_DIR, fname)
    collect(fp)

# Write TSV
tsv_path = "/tmp/opencode/inv_input.tsv"
with open(tsv_path, 'w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f, delimiter='\t', quoting=csv.QUOTE_MINIMAL, escapechar='\\')
    # Sort by path then line
    rows = sorted(seen, key=lambda r: (r[0], r[1]))
    for path, line, text in rows:
        # TSV-escape
        writer.writerow([path, str(line), text])

print(f"Written to {tsv_path}")
print(f"Total rows: {len(rows)}")

# Per-file counts
from collections import Counter
file_counts = Counter(r[0] for r in rows)
print("\nPer-file counts (top 15):")
for fp, cnt in file_counts.most_common(15):
    short = fp.replace(ROOT + "/", "…/tui/")
    print(f"  {short}: {cnt}")

print("\n10 representative examples:")
for r in rows[:10]:
    short = r[0].replace(ROOT + "/", "…/tui/")
    text = r[2][:80]
    print(f"  {short}:{r[1]}: \"{text}\"")
