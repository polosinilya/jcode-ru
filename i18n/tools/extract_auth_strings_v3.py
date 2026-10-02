#!/usr/bin/env python3
"""
Extract user-visible English string literals for AUTH / LOGIN / ACCOUNT surfaces.
Third pass: balanced filtering.
"""
import re, os, csv, json
from collections import Counter

TSV_PATH = "/tmp/opencode/inv_auth.tsv"
ROOT = "/home/ilya/Program/jcode"

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
]

def is_clearly_not_user_facing(s, line, filepath):
    """Return True if this string is DEFINITELY not user-visible."""
    s_clean = s.strip()
    
    # Empty/trivial
    if not s_clean or len(s_clean) < 2:
        return True
    
    line_lower = line.lower()
    
    # Exclude lines that are clearly log/debug/test
    if '#[cfg(test)]' in line or line.strip().startswith('//'):
        pass  # still might be in a user-facing context
    
    # Pure identifiers
    if re.match(r'^[a-z_][a-z0-9_]*$', s_clean):
        return True
    if re.match(r'^[A-Z_][A-Z0-9_]*$', s_clean):
        return True
    
    # Hex colors, numbers, percentages
    if re.match(r'^#[0-9a-fA-F]{6}$', s_clean):
        return True
    if re.match(r'^\d+$', s_clean):
        return True
    if re.match(r'^[\d.]+%?$', s_clean):
        return True
    
    # Rust module paths (with ::)
    if re.match(r'^[a-z][a-z0-9_]*(::[a-z][a-z0-9_]*)+$', s_clean):
        return True
    
    # snake_case identifiers longer than 20 chars (config keys, env var names)
    if re.match(r'^[a-z]+(_[a-z0-9]+)+$', s_clean) and len(s_clean) > 20:
        return True
    
    # UPPER_SNAKE_CASE (env vars, config keys)
    if re.match(r'^[A-Z]+(_[A-Z0-9]+)+$', s_clean):
        return True
    
    # File paths
    if s_clean.startswith('/') or s_clean.startswith('~/'):
        return True
    if s_clean.startswith('./') or s_clean.startswith('../'):
        return True
    
    # CSS/SVG fragments
    if s_clean in ['center', 'left', 'right', 'top', 'bottom'] and len(s_clean) < 10:
        return True
    
    # JSON/debug keys
    if re.match(r'^[a-z]+_[a-z_]*$', s_clean) and len(s_clean) > 5 and '"' not in line:
        return True
    
    return False

def is_in_render_context(line, lines, lineno):
    """Check if this line is in a rendering context."""
    line_lower = line.lower()
    
    # Direct render API calls
    render_apis = [
        '.title(', '.title_bottom(',
        'span::styled', 'paragraph::new(', 'line::from(',
        'push_display_message(', 'displaymessage::system(',
        'displaymessage::error(', 'displaymessage::info(',
        'set_status_notice(',
        'frame.render_widget(',
        'metric_span(', 'hotkey(',
        'lozenge_pill_spans(', 'yes_no_pill_line(', 'continue_pill_line(',
        'import_summary_pills_line(', 'telemetry_settings_lines(',
        'push_status(',
        'status_notice:', 'status_notice =', 'status_notice(',
        '.prompt =', 'prompt:',
        'empty_value:', 'empty_value(',
        'command_prefix:', 'command_prefix =',
        'app.set_status_notice',
        'app.push_display_message',
        'subscribe_pitch_markdown(',
        'RATE_LIMIT_NUDGE_LINE',
        'SUPPORT_NUDGE_NOTICE',
        'long_task_message(',
        'render_provider_settings_markdown(',
        'render_auth_doctor_markdown(',
    ]
    
    for api in render_apis:
        if api in line_lower:
            return True
    
    # Check if the line is a format!() call that builds a message
    # (likely user-facing if it contains login/auth keywords)
    if 'format!(' in line or 'format!("' in line:
        auth_keywords = [
            'login', 'logout', 'account', 'provider', 'oauth', 'token',
            'auth', 'api key', 'api_key', 'credential', 'authenticate',
            'authorize', 'subscription', 'hosted', 'onboarding',
            'import', 'switch', 'setup', 'configured',
            'welcome', 'enter', 'press ', 'choose ',
            '/login', '/logout', '/account', '/auth',
        ]
        for kw in auth_keywords:
            if kw in line_lower:
                return True
    
    # Check nearby lines for render context
    # Look at surrounding lines (previous 2, next 1)
    if lineno > 1:
        for offset in range(-2, 2):
            check_lineno = lineno + offset
            if check_lineno < 1 or check_lineno > len(lines):
                continue
            check_line = lines[check_lineno - 1].lower()
            for api in render_apis:
                if api in check_line:
                    return True
    
    return False

def extract_strings_from_file(filepath):
    results = []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except FileNotFoundError:
        return results
    
    for lineno, line in enumerate(lines, 1):
        line_r = line.rstrip('\n')
        for m in re.finditer(r'"((?:[^"\\]|\\.)*)"', line_r):
            s = m.group(1)
            
            # Quick exclusion
            if is_clearly_not_user_facing(s, line_r, filepath):
                continue
            
            # Check if in render context or contains auth/login keywords
            render_context = is_in_render_context(line_r, lines, lineno)
            has_auth_keyword = any(kw in s.lower() for kw in [
                'login', 'sign in', 'sign-in', 'logout', 'log in', 'log out',
                'authorize', 'authorization', 'authenticate', 'authentication',
                'api key', 'API key', 'apikey',
                'provider', 'oauth', 'token',
                'account', 'credential', 'password',
                'setup', 'configured', 'expired',
                'welcome', 'onboarding',
                'import', 'importing',
                'enter', 'press', 'choose', 'select',
                'yes', 'no', 'continue', 'cancel',
                'openai', 'claude', 'anthropic', 'gemini', 'copilot', 'cursor',
                'openrouter', 'antigravity', 'jcode',
                'username', 'email',
                'browser', 'callback', 'redirect',
                'subscription', 'hosted', 'subscribe',
                'ready', 'attention', 'needs attention',
                'filter', 'tip', 'hint', 'instruction',
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
                'password', 'secret', 'key',
                'press enter', 'press esc', 'type ',
                'ssh login', 'remote', 'host ',
                'click', 'navigate', 'result',
                'recommended', 'setup needed',
                'not set up', 'not validated',
                'add new', 'add another',
                'saved account', 'account(s)',
                'full usage details',
                'configure custom',
                'copilot premium',
                'openai effort',
                'openai transport',
                'openai-compatible',
                'default provider',
                'default model',
                'global defaults',
                'provider setting',
                'browser approval',
                'local login',
                'remote login',
                'paste the',
                'paste a fresh',
                'credentials stay',
                'authorization code',
                'callback url',
                'auth code',
                'user code',
                'enter code',
                'in your browser',
            ])
            
            if render_context or has_auth_keyword:
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
        key = s[:60]
        if key not in seen:
            seen.add(key)
            rel = os.path.relpath(fp, ROOT)
            display = s[:120] + ('...' if len(s) > 120 else '')
            print(f"  {rel}:{ln}  \"{display}\"")
            shown += 1
            if shown >= 10:
                break
    
    print(f"\nTSV: {TSV_PATH}")

if __name__ == '__main__':
    main()
