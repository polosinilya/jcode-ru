#!/usr/bin/env python3
"""
Extract user-visible English string literals for AUTH / LOGIN / ACCOUNT surfaces.
Writes TSV to /tmp/opencode/inv_auth.tsv
"""
import re, os, json, csv, io

TSV_PATH = "/tmp/opencode/inv_auth.tsv"
ROOT = "/home/ilya/Program/jcode"

# Files to scan (absolute paths)
SCAN_FILES = [
    # Primary TUI auth/login/account surfaces
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
    # Account picker crate
    "crates/jcode-tui-account-picker/src/overlay_render.rs",
    "crates/jcode-tui-account-picker/src/overlay.rs",
    "crates/jcode-tui-account-picker/src/lib.rs",
]

# Additional files to glob for auth-related strings
EXTRA_GLOB_PATTERNS = [
    "crates/jcode-tui/src/tui/app/inline_interactive*.rs",
    "crates/jcode-tui/src/tui/app/inline_interactive/**/*.rs",
    "crates/jcode-tui/src/tui/app/auth_tests.rs",
    "crates/jcode-tui/src/tui/app/remote.rs",
    "crates/jcode-tui/src/tui/app/local.rs",
    "crates/jcode-tui/src/tui/app/input_help.rs",
]

def is_user_facing_string(s, line_text, filepath):
    """Heuristic: is this string likely user-visible?"""
    s_clean = s.strip()
    if not s_clean or len(s_clean) < 2:
        return False
    
    # Exclude obvious non-user-facing patterns
    excluded_patterns = [
        # Log messages, test assertions, identifiers
        r'^Failed to ', r'^failed to ', r'^Error: ',
        r'^Unknown ', r'^Usage: ',
        r'^\d+$', r'^[a-z_]+$', r'^[a-z_]+[a-z_0-9]*$',
        # Debug/profile keys
        r'^provider_', r'^session_', r'^total_', r'^streaming_',
        r'^last_', r'^effective_', r'^client_observed_',
        r'^cache_', r'^- ',  # list item markers in debug output
        # SVG/HTML fragments
        r'^<svg', r'^</', r'^<path',
        # Pure color hex or codes
        r'^#[0-9a-fA-F]{6}$',
        r'^rgb\(', r'^Color::',
        # Placeholders only
        r'^\{.*\}$',
        r'^\s*$',
    ]
    for pat in excluded_patterns:
        if re.match(pat, s_clean):
            return False
    
    # Check for user-facing keywords
    user_keywords = [
        'login', 'sign in', 'sign-in', 'signin', 'logout', 'log in', 'log out',
        'authorize', 'authorization', 'authenticate', 'authentication',
        'api key', 'API key', 'apikey',
        'provider', 'oauth', 'token',
        'account', 'credential', 'password',
        'setup', 'configured', 'expired',
        'welcome', 'onboarding',
        'import', 'importing',
        'enter', 'press', 'choose', 'select', 'type',
        'yes', 'no', 'continue', 'cancel',
        'openai', 'claude', 'anthropic', 'gemini', 'copilot', 'cursor',
        'openrouter', 'antigravity', 'jcode',
        'username', 'email', 'password',
        'browser', 'callback', 'redirect',
        'subscription', 'hosted', 'subscribe',
        'ready', 'attention', 'needs attention',
        'filter', 'search', 'result',
        'tip', 'hint', 'instruction',
        'saved', 'refresh', 'reconnect',
        'transport', 'effort', 'premium', 'fast mode',
        'diagnose', 'doctor', 'health', 'status',
        'validation', 'validate',
        'no matching', 'no provider', 'no account',
        '/login', '/logout', '/account', '/auth',
        'default provider', 'default model',
        'manage', 'setting', 'overview',
        'add', 'remove', 'replace', 'switch',
        'run ', 'use /cancel',
    ]
    
    s_lower = s_clean.lower()
    for kw in user_keywords:
        if kw in s_lower:
            return True
    
    # Check line context (is this in a user-facing rendering path?)
    line_lower = line_text.lower()
    render_indicators = [
        'span::styled', 'paragraph::new', 'line::from',
        'push_display_message', 'displaymessage::system',
        'displaymessage::error', 'push_status', 'set_status_notice',
        'frame.render_widget', 'title(', 'title_bottom(',
        'metric_span(', 'hotkey(', 'lozenge_pill_spans(',
        'yes_no_pill_line(', 'continue_pill_line(',
        'import_summary_pills_line(', 'telemetry_settings_lines(',
        'prompt_value', 'status_notice',
        'format!("', 'format!("',
    ]
    for ind in render_indicators:
        if ind in line_lower:
            return True
    
    return False

def extract_strings_from_file(filepath):
    """Extract user-visible string literals from a Rust source file."""
    results = []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except FileNotFoundError:
        return results
    
    # Pattern for Rust string literals (double-quoted)
    # Match "string content" with balanced escapes
    for lineno, line in enumerate(lines, 1):
        line = line.rstrip('\n')
        # Find all string literals
        for m in re.finditer(r'"((?:[^"\\]|\\.)*)"', line):
            s = m.group(1)
            if is_user_facing_string(s, line, filepath):
                # Escape TSV special characters
                s_escaped = s.replace('\\', '\\\\').replace('\t', '\\t').replace('\n', '\\n')
                results.append((filepath, lineno, s_escaped))
    return results

def find_extra_files():
    """Find additional files matching glob patterns."""
    import glob
    extra_files = set()
    for pattern in EXTRA_GLOB_PATTERNS:
        full_pattern = os.path.join(ROOT, pattern)
        for f in glob.glob(full_pattern, recursive=True):
            if os.path.isfile(f) and f.endswith('.rs'):
                extra_files.add(f)
    return sorted(extra_files)

def main():
    all_results = []
    
    # Scan primary files
    for rel_path in SCAN_FILES:
        full_path = os.path.join(ROOT, rel_path)
        if os.path.exists(full_path):
            results = extract_strings_from_file(full_path)
            all_results.extend(results)
            print(f"  {rel_path}: {len(results)} strings")
        else:
            print(f"  {rel_path}: NOT FOUND")
    
    # Scan extra files
    extra_files = find_extra_files()
    for f in extra_files:
        rel = os.path.relpath(f, ROOT)
        results = extract_strings_from_file(f)
        all_results.extend(results)
        if results:
            print(f"  {rel}: {len(results)} strings")
    
    # Write TSV
    with open(TSV_PATH, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, delimiter='\t', quoting=csv.QUOTE_NONE, escapechar='\\')
        writer.writerow(['file', 'line', 'string'])
        for filepath, lineno, s in all_results:
            rel = os.path.relpath(filepath, ROOT)
            writer.writerow([rel, str(lineno), s])
    
    # Summary
    print(f"\nTotal strings: {len(all_results)}")
    
    # Per-file counts (top 15)
    from collections import Counter
    file_counts = Counter(os.path.relpath(fp, ROOT) for fp, _, _ in all_results)
    print("\nPer-file counts (top 15):")
    for fname, count in file_counts.most_common(15):
        print(f"  {count:5d}  {fname}")
    
    # 10 representative examples
    print("\n10 representative examples:")
    seen = set()
    shown = 0
    for fp, ln, s in all_results:
        key = s[:40]
        if key not in seen:
            seen.add(key)
            rel = os.path.relpath(fp, ROOT)
            print(f"  {rel}:{ln}  \"{s[:80]}{'...' if len(s)>80 else ''}\"")
            shown += 1
            if shown >= 10:
                break
    
    print(f"\nTSV written to: {TSV_PATH}")

if __name__ == '__main__':
    main()
