#!/bin/bash
# Install pre-commit hook for auto-timestamping seeds.
# Run once per clone: bash scripts/install-seed-hooks.sh

set -e

REPO_ROOT="$(git rev-parse --show-toplevel)"
HOOK_SRC="$REPO_ROOT/scripts/seed-precommit.sh"
HOOK_DST="$REPO_ROOT/.git/hooks/pre-commit"

if [ ! -f "$HOOK_SRC" ]; then
  echo "❌ Source not found: $HOOK_SRC"
  exit 1
fi

cp "$HOOK_SRC" "$HOOK_DST"
chmod +x "$HOOK_DST"

echo "✅ Installed pre-commit hook → $HOOK_DST"
echo
echo "From now on, every git commit on this clone will:"
echo "  - new seed (.md added) → auto-fill ts with current Taipei time"
echo "  - modified seed → auto-update updated_at field"
echo
echo "If you ever rebase / cherry-pick, hook auto-skips so history isn't rewritten."
