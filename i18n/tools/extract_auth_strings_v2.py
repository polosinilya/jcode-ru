#!/usr/bin/env python3
"""
Extract user-visible English string literals for AUTH / LOGIN / ACCOUNT surfaces.
Second pass: stricter filtering to exclude log messages, error types, config keys, etc.
"""
import re, os, csv
from collections import Counter

TSV_PATH = "/tmp/opencode/inv_auth.tsv"
ROOT = "/home/ilya/Program/jcode"

# Primary files to scan (focused on user-facing UI)
SCAN_FILES = [
    "crates/jcode-tui/src/tui/login_picker.rs",
    "crates/jcode-tui/src/tui/account_picker.rs",
    "crates/jcode-tui/src/tui/app/auth_account_picker.rs",
    "crates/jcode-tui/src/tui/app/auth_account_commands.rs",
    "crates/jcode-tui/src/tui/app/auth_account_picker_saved_accounts.rs",
    "crates/jcode-tui/src/tui/app/auth_remote.rs",
    "crates/jcode-tui/src/tui/app/auth_remote/picker.rs",
    "crates/jcode-tui/src/tui/app/auth_remote/onboarding.rs",
    "crates/jcode-tui/src/tui/app/auth_remote/command.rs",
    "crates/jcode-tui/src/tui/app/auth_types.rs",
    "crates/jcode-tui/src/tui/app/auth.rs",
    "crates/jcode-tui/src/tui/app/onboarding_flow.rs",
    "crates/jcode-tui/src/tui/app/onboarding_flow_control.rs",
    "crates/jcode-tui/src/tui/app/onboarding_graph.rs",
    "crates/jcode-tui/src/tui/app/onboarding_repair.rs",
    "crates/jcode-tui/src/tui/app/onboarding_sim.rs",
    "crates/jcode-tui/src/tui/app/subscribe_nudge.rs",
    "crates/jcode-tui/src/tui/app/model_context.rs",
    "crates/jcode-tui/src/tui/app/commands.rs",
    "crates/jcode-tui/src/tui/app/commands_remote.rs",
    "crates/jcode-tui/src/tui/app/commands_dispatch.rs",
    "crates/jcode-tui/src/tui/app/state_ui_input_helpers.rs",
    "crates/jcode-tui/src/tui/app/input_help.rs",
    "crates/jcode-tui/src/tui/app/input.rs",
    "crates/jcode-tui/src/tui/app/helpers.rs",
    "crates/jcode-tui/src/tui/app/misc_ui.rs",
    "crates/jcode-tui/src/tui/ui_onboarding.rs",
    "crates/jcode-tui/src/tui/ui_overlays.rs",
    "crates/jcode-tui/src/tui/ui_header.rs",
    "crates/jcode-tui/src/tui/ui_status.rs",
    "crates/jcode-tui/src/tui/ui_input.rs",
    "crates/jcode-tui/src/tui/ui.rs",
    "crates/jcode-tui-account-picker/src/overlay_render.rs",
    "crates/jcode-tui-account-picker/src/overlay.rs",
    "crates/jcode-tui-account-picker/src/lib.rs",
    "crates/jcode-tui/src/tui/app/auth_tests.rs",
    "crates/jcode-tui/src/tui/app/inline_interactive.rs",
    "crates/jcode-tui/src/tui/app/inline_interactive/helpers.rs",
    "crates/jcode-tui/src/tui/app/inline_interactive/openers.rs",
    "crates/jcode-tui/src/tui/app/inline_interactive/preview.rs",
    "crates/jcode-tui/src/tui/app/local.rs",
    "crates/jcode-tui/src/tui/app/remote.rs",
    "crates/jcode-tui/src/tui/app/onboarding_flow.rs",
    # Input help appears twice in the list but that's fine
]

EXCLUDE_STRINGS = set()

def is_user_facing(line, s):
    """
    Strict heuristic for user-visible strings.
    Must be in a context that renders to the user: Span::styled, Paragraph, Line,
    DisplayMessage, status_notice, title, prompt, etc.
    """
    line_lower = line.lower()
    s_clean = s.strip()
    if not s_clean or len(s_clean) < 2:
        return False
    
    # Exclude pure identifiers, hex colors, numbers
    if re.match(r'^[a-z_][a-z0-9_]*$', s_clean):
        return False
    if re.match(r'^[A-Z_][A-Z0-9_]*$', s_clean):
        return False
    if re.match(r'^#[0-9a-fA-F]{6}$', s_clean):
        return False
    if re.match(r'^\d+$', s_clean):
        return False
    if re.match(r'^[\d.]+%$', s_clean):
        return False
    
    # Exclude Rust paths, module identifiers
    if re.match(r'^[a-z][a-z0-9_]*(::[a-z][a-z0-9_]*)+$', s_clean):
        return False
    if re.match(r'^[a-z_]+\[', s_clean):
        return False
    
    # Exclude single-word error codes
    if re.match(r'^[a-z]+_[a-z]+_[a-z]+$', s_clean) and len(s_clean) < 30:
        return False
    
    # Must be in a user-facing rendering context
    render_contexts = [
        'span::styled', 'paragraph::new', 'line::from',
        'push_display_message', 'displaymessage::system',
        'displaymessage::error', 'set_status_notice',
        'frame.render_widget', '.title(', '.title_bottom(',
        'metric_span(', 'hotkey(', 'lozenge_pill_spans(',
        'yes_no_pill_line(', 'continue_pill_line(',
        'import_summary_pills_line(',
        'prompt_value', '.prompt = ', 'prompt:',
        'status_notice:', 'empty_value:',
        'app.set_status_notice',
        'status_prompt',
        'format!("', 'format!("',
        'subscribe_pitch_markdown',
        'RATE_LIMIT_NUDGE_LINE',
        'SUPPORT_NUDGE_NOTICE',
    ]
    
    is_rendered = False
    for ctx in render_contexts:
        if ctx in line_lower:
            is_rendered = True
            break
    
    if not is_rendered:
        # Check if this is in a function that clearly builds user-facing text
        # by looking at nearby context (imprecise but helps)
        pass
    
    return is_rendered

def extract_strings_from_file(filepath):
    results = []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except FileNotFoundError:
        return results
    
    for lineno, line in enumerate(lines, 1):
        line = line.rstrip('\n')
        for m in re.finditer(r'"((?:[^"\\]|\\.)*)"', line):
            s = m.group(1)
            if is_user_facing(line, s):
                s_escaped = s.replace('\\', '\\\\').replace('\t', '\\t').replace('\n', '\\n')
                results.append((filepath, lineno, s_escaped))
    return results

def main():
    all_results = []
    
    for rel_path in SCAN_FILES:
        full_path = os.path.join(ROOT, rel_path)
        if os.path.exists(full_path):
            results = extract_strings_from_file(full_path)
            all_results.extend(results)
            print(f"  {rel_path}: {len(results)} strings")
        else:
            print(f"  {rel_path}: NOT FOUND")
    
    # Write TSV
    with open(TSV_PATH, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, delimiter='\t', quoting=csv.QUOTE_NONE, escapechar='\\')
        writer.writerow(['file', 'line', 'string'])
        for filepath, lineno, s in all_results:
            rel = os.path.relpath(filepath, ROOT)
            writer.writerow([rel, str(lineno), s])
    
    print(f"\n=== Total user-visible strings: {len(all_results)} ===")
    
    file_counts = Counter(os.path.relpath(fp, ROOT) for fp, _, _ in all_results)
    print("\nPer-file counts (top 15):")
    for fname, count in file_counts.most_common(15):
        print(f"  {count:5d}  {fname}")
    
    print("\n10 representative examples:")
    seen = set()
    shown = 0
    for fp, ln, s in all_results:
        key = s[:50]
        if key not in seen:
            seen.add(key)
            rel = os.path.relpath(fp, ROOT)
            display = s[:100] + ('...' if len(s) > 100 else '')
            print(f"  {rel}:{ln}  \"{display}\"")
            shown += 1
            if shown >= 10:
                break
    
    print(f"\nTSV: {TSV_PATH}")

if __name__ == '__main__':
    main()
