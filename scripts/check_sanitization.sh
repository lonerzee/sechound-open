#!/usr/bin/env bash
#
# check_sanitization.sh — fail if any target-specific data leaked into the repo.
#
# Mechanical enforcement of SANITIZATION.md. Runs locally and in CI on every PR.
# Non-zero exit = something that must never be public is about to be committed.
#
# Patterns here are GENERIC leak indicators (secrets, private IPs, credential
# headers). Keep your private/operator pattern list OUT of this repo; pass it in
# via $SECHOUND_LEAK_EXTRA (a single regex).
#
# Usage: scripts/check_sanitization.sh

set -uo pipefail
cd "$(dirname "$0")/.." || exit 2

# Search tracked files when in a git repo (portable: no mapfile/bash4 needed),
# otherwise the whole tree minus .git.
search() {
  local pat="$1"
  if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git grep -InE "$pat" -- . 2>/dev/null
  else
    grep -rInE --exclude-dir=.git "$pat" . 2>/dev/null
  fi
}

PATTERNS=(
  '-----BEGIN (RSA|EC|OPENSSH|PGP) PRIVATE KEY-----'
  'AKIA[0-9A-Z]{16}'                               # AWS access key id
  'sk-[A-Za-z0-9]{20,}'                            # OpenAI-style secret key
  'xox[baprs]-[0-9A-Za-z-]{10,}'                   # Slack token
  'ghp_[A-Za-z0-9]{36}'                            # GitHub PAT
  'eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}'   # JWT
  'pub-c-[0-9a-f-]{30,}'                           # PubNub publish key
  'sub-c-[0-9a-f-]{30,}'                           # PubNub subscribe key
  'Authorization:[[:space:]]*Bearer[[:space:]]+[A-Za-z0-9._-]{16,}'
  'AW_AT|AW_RT'                                     # sealed-cookie names
)
# Note: generic attack payloads (e.g. the 169.254.169.254 metadata IP) are NOT
# leaks — they legitimately appear in hunt skills. This gate targets secrets and
# target-specific identifiers only.
[ -n "${SECHOUND_LEAK_EXTRA:-}" ] && PATTERNS+=("$SECHOUND_LEAK_EXTRA")

# Exclude this script itself (it necessarily contains the patterns).
fail=0
for pat in "${PATTERNS[@]}"; do
  hits=$(search "$pat" | grep -v 'check_sanitization\.sh:')
  if [ -n "$hits" ]; then
    echo "LEAK: pattern /$pat/ matched:"
    echo "$hits" | sed 's/^/  /'
    fail=1
  fi
done

if [ "$fail" -ne 0 ]; then
  echo
  echo "Sanitization check FAILED — see SANITIZATION.md. Do not commit/push."
  echo "If a credential matched, rotate it; deleting the file later is not enough (git history)."
  exit 1
fi
echo "Sanitization check passed."
