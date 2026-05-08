#!/bin/bash
# Pre-commit hook: auto-fill ts on new seeds, update updated_at on modified.
# Install via: bash scripts/install-seed-hooks.sh

# Skip during rebase / merge / cherry-pick (don't rewrite history)
if [ -d .git/rebase-merge ] || [ -d .git/rebase-apply ] || [ -f .git/MERGE_HEAD ] || [ -f .git/CHERRY_PICK_HEAD ]; then
  exit 0
fi

NOW=$(TZ='Asia/Taipei' date +'%Y-%m-%dT%H:%M:%S+08:00')

# Use newline-only IFS so filenames with spaces survive the loop
process() {
  local mode="$1"
  local filter="$2"
  git diff --cached --name-only --diff-filter="$filter" 2>/dev/null \
    | grep '^seeds/posts/.*\.md$' \
    | while IFS= read -r f; do
        [ -z "$f" ] && continue
        python3 scripts/seed-touch.py "$mode" --file "$f" --now "$NOW" || true
        git add "$f"
      done
}

process --new A
process --modified M

exit 0
