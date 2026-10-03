#!/usr/bin/env bash
# Smoke test a running ChurnCast API.   scripts/smoke-test.sh [BASE_URL]   (default http://localhost:8000)
# EXPECT_FALLBACK=true  also requires the explanation to be the template fallback (AI provider unreachable).
# EXPECT_VERSION=1.0.0  the model version /health must report (default: any).
set -euo pipefail
BASE=${1:-http://localhost:8000}
EXPECT_FALLBACK=${EXPECT_FALLBACK:-}
EXPECT_VERSION=${EXPECT_VERSION:-}
pass=0
fail=0
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
ROW='{"tenure_months": 2, "is_new": 1, "plan_standard": 1, "plan_premium": 0, "discount_share": 0.2,
  "price_change_pct": 0.0, "meals_last_month": 9, "skip_rate_last_month": 0.35, "meals_trend": -6.0,
  "late_rate_3m": 0.12, "avg_rating_3m": 3.4, "rating_missing": 0, "tickets_90d": 2, "open_tickets": 1,
  "failed_payments_3m": 1}'

check() {  # check NAME COMMAND...
  local name=$1
  shift
  if "$@" >"$TMP/out" 2>&1; then
    pass=$((pass + 1))
    echo "ok   $name"
  else
    fail=$((fail + 1))
    echo "FAIL $name: $(head -c 300 "$TMP/out")"
  fi
}

status_is() {  # status_is CODE METHOD PATH [BODY]
  local got
  if [ "$2" = GET ]; then
    got=$(curl -s -o "$TMP/body" -w '%{http_code}' "$BASE$3")
  else
    got=$(curl -s -o "$TMP/body" -w '%{http_code}' -X "$2" -H 'Content-Type: application/json' -d "$4" "$BASE$3")
  fi
  [ "$got" = "$1" ] || { echo "HTTP $got for $2 $3: $(head -c 200 "$TMP/body")"; return 1; }
}

body_check() {  # body_check PYTHON_EXPR (d = the JSON body of the last status_is)
  python3 -c "import json,sys; d=json.load(open(sys.argv[1])); assert $1, d" "$TMP/body"
}

ok_json() {  # ok_json METHOD PATH BODY PYTHON_EXPR
  status_is 200 "$1" "$2" "$3" && body_check "$4"
}

check "health" ok_json GET /health "" "d['status'] == 'ok' and ('$EXPECT_VERSION' in ('', d['model_version']))"
check "model card" ok_json GET /v1/model "" "len(d['features']) == 15 and 0 < d['high_risk_threshold'] < 1"
check "form page" status_is 200 GET /
check "predict" ok_json POST /v1/predict "{\"customers\": [{\"customer_id\": \"smoke-1\", \"features\": $ROW}]}" \
  "d['predictions'][0]['customer_id'] == 'smoke-1' and 0 < d['predictions'][0]['churn_probability'] < 1 and len(d['predictions'][0]['top_reasons']) == 3"
check "out-of-range input is 422" status_is 422 POST /v1/predict '{"customers": [{"features": {"tenure_months": -5}}]}'
check "422 is problem+json" body_check "d['status'] == 422 and any(e['field'].endswith('tenure_months') for e in d['errors'])"
check "explain" ok_json POST /v1/explain "{\"features\": $ROW}" \
  "d['explanation']['source'] in ('template', 'llm') and '[R1]' in d['explanation']['text'] and len(d['explanation']['text']) <= 600"
if [ "$EXPECT_FALLBACK" = true ]; then
  check "explanation fell back to the template" body_check \
    "d['explanation']['source'] == 'template' and d['explanation']['fallback'] is True and d['explanation']['reason'].startswith('provider unreachable')"
fi
check "unknown path is 404" status_is 404 GET /v1/nope
echo "smoke: $pass passed, $fail failed ($BASE)"
[ "$fail" -eq 0 ]
