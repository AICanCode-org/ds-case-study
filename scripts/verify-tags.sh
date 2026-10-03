#!/usr/bin/env bash
# Maintainer tool: check out every phase tag in a temporary git worktree and run scripts/check-all.sh.
# Tags from phase-4-end on run the full check (data and model tests, coverage gate, run, gate, reports, parity).
#   scripts/verify-tags.sh                    all phase-*/v* tags
#   scripts/verify-tags.sh phase-3-end v1.0.0 only these
# PY_VENV, DOCKER and R_IMAGE are passed through to check-all.sh.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
TAGS=("$@")
[ ${#TAGS[@]} -eq 0 ] && mapfile -t TAGS < <(git tag -l 'phase-*' 'v*' --sort=creatordate)
WORK="$(mktemp -d)"
SUMMARY=()

needs_full() { case "$1" in phase-[0-3]-end) return 1 ;; *) return 0 ;; esac; }

for tag in "${TAGS[@]}"; do
  echo; echo "████ $tag ($(git rev-parse --short "$tag^{commit}"))"
  wt="$WORK/$tag"
  git worktree add --quiet --detach "$wt" "$tag" || { SUMMARY+=("FAIL  $tag (worktree)"); continue; }
  args=()
  needs_full "$tag" && args=(--full)
  if (cd "$wt" && bash scripts/check-all.sh "${args[@]}") > "$WORK/$tag.log" 2>&1; then
    SUMMARY+=("PASS  $tag ${args[*]:-(lint + unit)}")
  else
    SUMMARY+=("FAIL  $tag ${args[*]:-(lint + unit)}  → see $WORK/$tag.log")
  fi
  sed -n '/════ Summary/,$p' "$WORK/$tag.log"
  git worktree remove --force "$wt"
done

echo; echo "████ verify-tags summary"
printf '%s\n' "${SUMMARY[@]}"
! printf '%s\n' "${SUMMARY[@]}" | grep -q '^FAIL'
