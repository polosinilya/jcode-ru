#!/usr/bin/env bash
# Build a .deb that installs the localized jcode binary to /usr/bin/jcode
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="$REPO/target/release/jcode"
VER="${JCODE_DEB_VERSION:-0.84.0-ru.0001}"
OUT="${JCODE_DEB_OUT:-$REPO/dist/jcode_${VER}_amd64.deb}"
ROOT="$(mktemp -d)/debroot"

[[ -x "$BIN" ]] || { echo "binary not found: $BIN" >&2; exit 1; }

rm -rf "$ROOT"
mkdir -p "$ROOT/DEBIAN" "$ROOT/usr/bin" "$ROOT/usr/share/doc/jcode"

install -m 0755 "$BIN" "$ROOT/usr/bin/jcode"

cat > "$ROOT/usr/share/doc/jcode/README.Debian" <<'EOF'
jcode (русская сборка)
======================

Это локальная сборка jcode с частичной русской локализацией интерфейса.
Исходники: https://github.com/1jehuang/jcode (MIT).
EOF

cat > "$ROOT/usr/share/doc/jcode/copyright" <<'EOF'
jcode is distributed under the MIT License.
Upstream: https://github.com/1jehuang/jcode
EOF

SIZE_KB=$(du -sk "$ROOT/usr" | cut -f1)

cat > "$ROOT/DEBIAN/control" <<EOF
Package: jcode
Version: ${VER}
Section: utils
Priority: optional
Architecture: amd64
Installed-Size: ${SIZE_KB}
Maintainer: Ilya <ilya@localhost>
Description: jcode - terminal AI coding agent (Russian build)
 jcode is a fast terminal AI coding agent written in Rust.
 This is a local build with a partial Russian UI localization.
EOF

dpkg-deb --build --root-owner-group "$ROOT" "$OUT" >/dev/null
rm -rf "$ROOT"
echo "built: $OUT"
ls -la "$OUT"
