#!/usr/bin/env bash
# Agent Skill Installer - bootstrap for Linux / macOS
#
#   bash <(curl -fsSL https://raw.githubusercontent.com/Turkishmadaraa/agent-skill-installer/main/install.sh)
#   bash <(curl -fsSL .../install.sh) anthropics/skills@pdf --agent claude-code
#
# No arguments: installs the installer itself as a skill for every detected agent.
# Pin a release for reproducible installs: SKILL_INSTALLER_REF=v2.0.1
set -eu

REPO="Turkishmadaraa/agent-skill-installer"
REF="${SKILL_INSTALLER_REF:-main}"
case "$REF" in *[!A-Za-z0-9._/-]*|*..*) echo "Hata: geçersiz SKILL_INSTALLER_REF" >&2; exit 1;; esac
RAW="https://raw.githubusercontent.com/${REPO}/${REF}/skills/installing-agent-skills/auto_install.py"

PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' 2>/dev/null; then
    PY="$c"; break
  fi
done
[ -n "$PY" ] || { echo "Hata: Python 3.8+ bulunamadı." >&2; exit 1; }

TMP="$(mktemp -d "${TMPDIR:-/tmp}/skill-installer.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
if command -v curl >/dev/null 2>&1; then
  curl -fsSL --proto '=https' --tlsv1.2 "$RAW" -o "$TMP/auto_install.py"
else
  wget -q --https-only -O "$TMP/auto_install.py" "$RAW"
fi

if [ "$#" -eq 0 ]; then
  exec "$PY" "$TMP/auto_install.py" "https://github.com/${REPO}/tree/${REF}"
fi
exec "$PY" "$TMP/auto_install.py" "$@"
