#!/usr/bin/env bash
# Install a native git pre-commit hook that runs the sanitization leak gate.
# No dependencies (alternative to the pre-commit framework). Run once after clone.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "not a git repo yet — run 'git init' first"; exit 1
fi

hook=".git/hooks/pre-commit"
cat > "$hook" <<'EOF'
#!/usr/bin/env bash
# SecHound: block commits that leak target data / secrets.
exec bash scripts/check_sanitization.sh
EOF
chmod +x "$hook"
echo "installed $hook — commits now run scripts/check_sanitization.sh"
