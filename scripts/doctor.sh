#!/usr/bin/env bash
# Phase 0 environment check. Prints what is installed and what is missing for each track.
# Usage: scripts/doctor.sh            (Linux, macOS, WSL2, Git Bash)
set -u
ok()   { printf '  \033[32m✔\033[0m %-28s %s\n' "$1" "$2"; }
miss() { printf '  \033[31m✘\033[0m %-28s %s\n' "$1" "$2"; MISSING=$((MISSING + 1)); }
warn() { printf '  \033[33m!\033[0m %-28s %s\n' "$1" "$2"; }
MISSING=0
ver() { "$@" 2>&1 | head -1; }

echo "Common (every track)"
command -v git >/dev/null && ok git "$(ver git --version)" || miss git "https://git-scm.com/downloads"
command -v make >/dev/null && ok make "$(ver make --version)" || warn make "Ubuntu/WSL: sudo apt install make · macOS: xcode-select --install"
PY=$(command -v python3 || command -v python || true)
[ -n "$PY" ] && ok python "$(ver "$PY" --version)" || miss python "Python 3.12+ (every track: scripts, SQL runner, API): https://www.python.org/downloads/"
[ -n "$PY" ] && { "$PY" -m venv --help >/dev/null 2>&1 && ok "python venv" "available" || warn "python venv" "Ubuntu/WSL: sudo apt install python3-venv"; }
if command -v docker >/dev/null; then
  ok docker "$(ver docker --version)"
  docker compose version >/dev/null 2>&1 && ok "docker compose" "$(ver docker compose version)" || warn "docker compose" "needed from Phase 6"
else
  warn docker "needed from Phase 6: https://docs.docker.com/get-docker/"
fi

echo; echo "Python track (pandas, scikit-learn, Jupyter) and SQL track (DuckDB)"
echo "  (both install everything into tracks/<track>/.venv with: make install)"

echo; echo "R track (tidymodels): the pinned Docker image is the recommended toolchain"
if command -v docker >/dev/null && docker image inspect churncast-r-dev:local >/dev/null 2>&1; then
  ok "R image" "churncast-r-dev:local (R 4.6.1 + CRAN snapshot 2026-09-15)"
else
  warn "R image" "docker build -f tracks/r/Dockerfile --target dev -t churncast-r-dev:local ."
fi
if command -v Rscript >/dev/null; then
  ok "local R (optional)" "$(ver Rscript --version)"
  command -v pandoc >/dev/null && ok pandoc "$(ver pandoc --version)" || warn pandoc "needed to knit R Markdown locally: https://pandoc.org/installing.html"
fi

echo
case "$(uname -s 2>/dev/null)" in
  Linux*) grep -qi microsoft /proc/version 2>/dev/null && echo "Detected WSL — keep the repo inside the Linux filesystem (~/code), not /mnt/c (much faster)." ;;
  MINGW*|MSYS*) echo "Detected Git Bash on Windows — WSL2 is recommended (see README › Windows)." ;;
esac
[ "$MISSING" -eq 0 ] && echo "All required tools found. You need the tools for ONE track only." || { echo "$MISSING required tool(s) missing."; exit 1; }
