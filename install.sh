#!/usr/bin/env bash
# Abacus.AI Skill Auto-Installer - one-line bootstrap
#
#   curl -sSL https://raw.githubusercontent.com/Turkishmadaraa/abacus-skill-installer/main/install.sh | bash
#   curl -sSL .../install.sh | bash -s -- https://github.com/anthropics/skills --skill pdf
#
# With no arguments it installs the installer itself as a skill, then the recommended profile skills.
set -euo pipefail

REPO="${SKILL_INSTALLER_REPO:-Turkishmadaraa/abacus-skill-installer}"
BRANCH="${SKILL_INSTALLER_BRANCH:-main}"
RAW="https://raw.githubusercontent.com/${REPO}/${BRANCH}/auto_install.py"

PY=""
for c in python3 python py; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' 2>/dev/null; then
    PY="$c"; break
  fi
done
[ -n "$PY" ] || { echo "Hata: Python 3.8+ bulunamadı." >&2; exit 1; }

TMP="$(mktemp "${TMPDIR:-/tmp}/auto_install.XXXXXX")"
trap 'rm -f "$TMP"' EXIT
if command -v curl >/dev/null 2>&1; then
  curl -fsSL "$RAW" -o "$TMP"
else
  wget -qO "$TMP" "$RAW"
fi

if [ "$#" -eq 0 ]; then
  echo "▶ 1/2: Kurulum aracı skill olarak ekleniyor (${REPO})"
  "$PY" "$TMP" "https://github.com/${REPO}/tree/${BRANCH}" || true
  echo "▶ 2/2: Önerilen skill'ler kuruluyor"
  exec "$PY" "$TMP" --profile
fi
exec "$PY" "$TMP" "$@"
