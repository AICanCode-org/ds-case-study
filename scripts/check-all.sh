#!/usr/bin/env bash
# Run the same checks CI runs, for every track (or TRACKS="python" for one).
#   scripts/check-all.sh          lint + unit tests (+ the API's tests from Phase 6)
#   scripts/check-all.sh --full   + data and model tests with the coverage gate, the run, schema validation, the
#                                 evaluation gate, the report, and parity with the golden files and across tracks
# The R track runs in its pinned toolchain image (tracks/r/Dockerfile, target dev) unless R_LOCAL=1 and Rscript
# is installed. Optional settings for maintainers (used by scripts/verify-tags.sh):
#   PY_VENV=/path/to/venv   reuse an existing virtualenv for the Python and SQL tracks and the API
#   DOCKER="sudo docker"    how to call Docker
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FULL=0
[ "${1:-}" = "--full" ] && FULL=1
TRACKS="${TRACKS:-python sql r}"
DOCKER="${DOCKER:-docker}"
R_IMAGE="${R_IMAGE:-churncast-r-dev:local}"
RESULTS=()
FAILED=0
RUNS=()

step() { # step <label> <command...>
  local label="$1"; shift
  echo; echo "──── $label"
  if "$@"; then RESULTS+=("PASS  $label"); else RESULTS+=("FAIL  $label"); FAILED=$((FAILED + 1)); fi
}

venv() { # a .venv for a Python-based folder
  [ -e .venv ] && return 0
  if [ -n "${PY_VENV:-}" ]; then ln -s "$PY_VENV" .venv; else make -s install; fi
}

r_make() { # make <targets> for the R track: in the dev image, or with a local R if R_LOCAL=1
  if [ "${R_LOCAL:-0}" = 1 ] && command -v Rscript >/dev/null; then make -s "$@"; return; fi
  $DOCKER run --rm --network none -u "$(id -u):$(id -g)" -e HOME=/tmp -v "$ROOT":/repo -w /repo/tracks/r \
    "$R_IMAGE" make -s "$@"
}

host_python() { # a Python that can import jsonschema (for validate_outputs.py)
  local p
  for p in "${PY_VENV:+$PY_VENV/bin/python}" "$ROOT/tracks/python/.venv/bin/python" "$ROOT/serving/.venv/bin/python" python3; do
    [ -n "$p" ] && "$p" -c 'import jsonschema' 2>/dev/null && { echo "$p"; return 0; }
  done
  echo python3
}

if [[ " $TRACKS " == *" r "* ]] && [ "${R_LOCAL:-0}" != 1 ] && ! $DOCKER image inspect "$R_IMAGE" >/dev/null 2>&1; then
  step "r: build the toolchain image $R_IMAGE" $DOCKER build -q -f "$ROOT/tracks/r/Dockerfile" --target dev -t "$R_IMAGE" "$ROOT"
fi

for track in $TRACKS; do
  dir="$ROOT/tracks/$track"
  [ -d "$dir" ] || { RESULTS+=("SKIP  $track (no tracks/$track)"); continue; }
  cd "$dir" || exit 1
  if [ "$track" = r ]; then run=r_make; else venv; run="make -s"; fi
  step "$track: lint" $run lint
  step "$track: unit tests" $run test
  if [ "$FULL" = 1 ]; then
    step "$track: unit + data and model tests + coverage gate" $run coverage
    step "$track: run (features.csv, metrics.json, model.json)" $run run OUT=out
    step "$track: outputs match the schemas" "$(host_python)" "$ROOT/scripts/validate_outputs.py" out
    step "$track: evaluation gate" python3 "$ROOT/scripts/eval_gate.py" out/metrics.json
    step "$track: report" $run report OUT=out
    RUNS+=("$dir/out")
  fi
done

if [ -d "$ROOT/serving" ] && [ -z "${SKIP_SERVING:-}" ]; then
  cd "$ROOT/serving" || exit 1
  venv
  step "serving: lint" make -s lint
  if [ "$FULL" = 1 ]; then step "serving: tests + coverage gate" make -s coverage; else step "serving: tests" make -s test; fi
fi

if [ "$FULL" = 1 ]; then
  cd "$ROOT" || exit 1
  step "data: the export is byte-identical to the seeded generator" python3 scripts/generate_data.py --check
  step "cms: the export is up to date with docs/" python3 scripts/build-cms.py --check
  if [ ${#RUNS[@]} -gt 0 ]; then
    export_month=$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["dataset"]["export"])' "${RUNS[0]}/metrics.json")
    metrics=() models=() features=()
    for r in "${RUNS[@]}"; do metrics+=("$r/metrics.json"); models+=("$r/model.json"); features+=("$r/features.csv"); done
    step "parity: metrics.json = golden $export_month (1e-6)" python3 scripts/parity.py "contract/golden/metrics-$export_month.json" "${metrics[@]}"
    step "parity: model.json = golden $export_month (1e-6)" python3 scripts/parity.py "contract/golden/model-$export_month.json" "${models[@]}"
    [ ${#features[@]} -gt 1 ] && step "parity: features.csv identical across tracks (1e-9)" python3 scripts/parity.py "${features[@]}"
    if [ -f docs/model-card.md ]; then
      step "model card: generated from the golden files" python3 scripts/model_card.py --check docs/model-card.md \
        "contract/golden/metrics-$export_month.json" "contract/golden/model-$export_month.json"
    fi
  fi
fi

echo; echo "════ Summary"
printf '%s\n' "${RESULTS[@]}"
[ "$FAILED" -eq 0 ]
