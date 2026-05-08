#!/bin/bash
# Pre-commit hook: auto-fill ts on new seeds, update updated_at on modified.
# Install via: bash scripts/install-seed-hooks.sh

# Skip during rebase / merge / cherry-pick (don't rewrite history)
if [ -d .git/rebase-merge ] || [ -d .git/rebase-apply ] || [ -f .git/MERGE_HEAD ] || [ -f .git/CHERRY_PICK_HEAD ]; then
  exit 0
fi

NEW=$(git diff --cached --name-only --diff-filter=A 2>/dev/null | grep '^seeds/posts/.*\.md$' || true)
MOD=$(git diff --cached --name-only --diff-filter=M 2>/dev/null | grep '^seeds/posts/.*\.md$' || true)

[ -z "$NEW" ] && [ -z "$MOD" ] && exit 0

NOW=$(TZ='Asia/Taipei' date +'%Y-%m-%dT%H:%M:%S+08:00')

for f in $NEW; do
  python3 scripts/seed-touch.py --new --file "$f" --now "$NOW" || true
  git add "$f"
done

for f in $MOD; do
  python3 scripts/seed-touch.py --modified --file "$f" --now "$NOW" || true
  git add "$f"
done

exit 0
