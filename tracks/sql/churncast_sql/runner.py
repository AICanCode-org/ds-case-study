"""Thin runner: sets the variables, loads the contract lists into cfg_* tables, runs sql/*.sql in order, runs the
contract checks (sql/checks/<type>.sql), fits the logistic regressions (fit.py) and turns the result tables into
out/features.csv, metrics.json, model.json and experiments.jsonl.

No analysis happens here: every number comes out of a SQL table. The runner only moves and formats them.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import duckdb
import numpy as np
import yaml

from . import __version__
from .fit import fit_logistic

TRACK = "sql"
TRACK_DIR = Path(__file__).resolve().parents[1]
REPO = TRACK_DIR.parents[1]
SQL_DIR = TRACK_DIR / "sql"
DEFAULT_CONTRACT = REPO / "contract" / "data-contract.yaml"
SCRIPTS = [
    "01_load.sql",
    "02_clean.sql",
    "03_features.sql",
    "04_models.sql",
    "05_metrics.sql",
    "06_evaluate.sql",
    "07_monitoring.sql",
]
TABLES = ["customers", "invoices", "usage", "tickets"]
SLICE_COLUMNS = ["city", "city_tier", "age_band", "channel", "plan", "price_inr"]
IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")
TEST_METRICS = ["auc", "average_precision", "brier", "log_loss", "ece"]
CAPACITY = [
    "contacted",
    "churners_reached",
    "precision_at_top",
    "recall_at_top",
    "lift_at_top",
    "net_value_inr_per_month",
]
SCHEMA_VERSION = "1.1"  # 1.1: monitoring, retraining, monitoring_reference, lineage (all additive)
ARTEFACT_TEST_KEYS = ["auc", "average_precision", "brier", "ece", "precision_at_top", "recall_at_top"]
POST = ("recent", "holdout", "score")
MONITORING_DEFAULTS = {
    "psi_bins": 10,
    "psi_floor": 1e-4,
    "psi_watch": 0.10,
    "psi_drift": 0.25,
    "alert_max_ece": 0.03,
    "alert_max_mean_gap": 0.02,
    "alert_min_auc": 0.72,
}
EPS = 1e-15


class ContractError(Exception):
    """The export breaks the data contract: the run must stop (exit code 3)."""


def load_contract(path: str | os.PathLike | None = None) -> dict:
    p = Path(path or os.environ.get("CONTRACT_PATH") or DEFAULT_CONTRACT)
    with open(p, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def feature_names(contract: dict, core_only: bool = False) -> list[str]:
    return [f["name"] for f in contract["features"] if f["core"] or not core_only]


def experiment_features(exp: dict, contract: dict) -> list[str]:
    if exp["kind"] != "logistic":
        return []
    return feature_names(contract, core_only=exp["features"] == "core")


def ident(value: str) -> str:
    """Contract values become SQL identifiers, so accept only plain lower-case names."""
    if not isinstance(value, str) or not IDENT.match(value):
        raise ContractError(f"not a plain identifier in the contract: {value!r}")
    return value


def month_index(label: str) -> int:
    year, month = label.strip().split("-")
    return int(year) * 12 + int(month) - 1


def load_export(data_dir: str | os.PathLike) -> dict:
    path = Path(data_dir) / "export.json"
    if not path.exists():
        raise ContractError("missing file: export.json")
    return json.loads(path.read_text(encoding="utf-8"))


def connect() -> duckdb.DuckDBPyConnection:
    """One thread: a parallel SUM adds the same numbers in a different order on every run, which changes the last
    bits of a float. With one thread the same export gives bit-identical metrics (tests/data/test_model_quality)."""
    con = duckdb.connect(":memory:")
    con.execute("SET threads = 1")
    return con


def setvar(con, name: str, value) -> None:
    con.execute(f"SET VARIABLE {ident(name)} = ?", [value])


def table(con, name: str, columns: str, rows: list) -> None:
    con.execute(f"CREATE OR REPLACE TABLE {ident(name)} ({columns})")
    if rows:
        marks = ", ".join("?" for _ in rows[0])
        con.executemany(f"INSERT INTO {name} VALUES ({marks})", rows)


def snapshot_rows(contract: dict, export_month: int) -> list[tuple]:
    """The contract snapshots the export covers. recent/holdout (1.1) also need their label month in the export."""
    rows = {}
    for split in ("train", "test", "recent", "holdout", "score"):
        lag = 1 if split in ("recent", "holdout") else 0
        for label in contract["snapshots"].get(split, []):
            m = month_index(label)
            if m + lag <= export_month and m not in rows:
                rows[m] = (m, label, split)
    return [rows[m] for m in sorted(rows)]


def prepare(con, data_dir: str | os.PathLike, contract: dict, export: dict) -> None:
    """Variables and cfg_* tables: everything the SQL files read from the contract."""
    cleaning, ev, gate = contract["cleaning"], contract["evaluation"], contract["gate"]
    expected = {"date": ["%Y-%m-%d", "%d/%m/%Y"], "timestamp": ["%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M"]}
    if cleaning["date_formats"] != expected["date"] or cleaning["timestamp_formats"] != expected["timestamp"]:
        raise ContractError("02_clean.sql parses only the contract 1.x date and timestamp formats")
    export_month = month_index(export["export"])
    setvar(con, "data_dir", str(Path(data_dir).resolve()))
    setvar(con, "export_month", export_month)
    setvar(con, "missing_label", cleaning["missing_label"])
    setvar(con, "rating_default", float(cleaning["rating_default"]))
    setvar(con, "folds", int(contract["snapshots"]["folds"]))
    kinds = {e["kind"]: e["id"] for e in contract["experiments"]}
    setvar(con, "prior_id", kinds["prior"])
    setvar(con, "rule_id", kinds["rule"])
    setvar(con, "eps", EPS)
    mon = {**MONITORING_DEFAULTS, **contract.get("monitoring", {})}
    if int(mon["psi_bins"]) != 10:
        raise ContractError("07_monitoring.sql computes decile edges: psi_bins must be 10")
    rt = contract.get("retraining", {})
    for name, value in {
        "psi_floor": float(mon["psi_floor"]),
        "psi_watch": float(mon["psi_watch"]),
        "psi_drift": float(mon["psi_drift"]),
        "alert_max_ece": float(mon["alert_max_ece"]),
        "alert_max_mean_gap": float(mon["alert_max_mean_gap"]),
        "alert_min_auc": float(mon["alert_min_auc"]),
        "rt_max_auc_drop": float(rt.get("max_auc_drop", 0.005)),
        "rt_max_ece": float(rt.get("max_ece", 0.03)),
        "rt_max_recall_gap": float(rt.get("max_recall_gap", 0.15)),
    }.items():
        setvar(con, name, value)
    for name, value in {
        "top_percent": int(ev["top_percent"]),
        "calibration_bins": int(ev["calibration_bins"]),
        "offer_cost_inr": float(ev["offer_cost_inr"]),
        "save_rate": float(ev["save_rate"]),
        "value_months": float(ev["value_months"]),
        "min_slice_rows": int(ev["min_slice_rows_for_auc"]),
        "min_slice_churners": int(ev["min_slice_churners_for_auc"]),
        "fairness_dimension": ident(ev["fairness"]["dimension"]),
        "fairness_min_churners": int(ev["fairness"]["min_churners"]),
        "leakage_limit": float(ev["leakage_max_single_feature_auc"]),
        "min_gain": float(contract["champion"]["min_cv_auc_gain_for_complexity"]),
        "gate_min_test_auc": float(gate["min_test_auc"]),
        "gate_min_auc_uplift": float(gate["min_auc_uplift_over_rule"]),
        "gate_max_ece": float(gate["max_ece"]),
        "gate_max_recall_gap": float(gate["max_recall_gap"]),
    }.items():
        setvar(con, name, value)
    table(con, "cfg_city_aliases", "alias VARCHAR, canonical VARCHAR", list(cleaning["city_aliases"].items()))
    table(con, "cfg_city_tier", "city VARCHAR, tier VARCHAR", list(cleaning["city_tier"].items()))
    table(con, "cfg_snapshots", "month INTEGER, label VARCHAR, split VARCHAR", snapshot_rows(contract, export_month))
    names = feature_names(contract)
    table(con, "cfg_features", "pos INTEGER, name VARCHAR", [(i + 1, ident(n)) for i, n in enumerate(names)])
    rules = [(ident(r["feature"]), r["op"], float(r["value"])) for r in contract["rule_baseline"]]
    if any(op not in (">=", "<=") for _, op, _ in rules):
        raise ContractError("rule_baseline ops must be >= or <=")
    table(con, "cfg_rules", "feature VARCHAR, op VARCHAR, value DOUBLE", rules)
    exps = [(i + 1, e["id"], e["kind"]) for i, e in enumerate(contract["experiments"])]
    table(con, "cfg_experiments", "pos INTEGER, id VARCHAR, kind VARCHAR", exps)
    table(con, "cfg_slices", "pos INTEGER, dim VARCHAR", [(i + 1, ident(d)) for i, d in enumerate(ev["slices"])])
    folds = int(contract["snapshots"]["folds"])
    stages = [(f"cv{k}", k, "train") for k in range(folds)] + [("test", None, "test"), ("train", None, "train")]
    table(con, "cfg_stages", "stage VARCHAR, fold INTEGER, eval_split VARCHAR", stages)


def check_raw_columns(con, data_dir: str | os.PathLike, contract: dict) -> None:
    """Compare each CSV header with the contract before 01_load.sql relies on the column names."""
    for name in TABLES:
        spec = contract["files"][name]
        path = Path(data_dir).resolve() / spec["file"]
        if not path.exists():
            raise ContractError(f"missing file: {spec['file']}")
        cols = {
            r[0]
            for r in con.execute(
                "DESCRIBE SELECT * FROM read_csv(?, header = true, all_varchar = true)", [str(path)]
            ).fetchall()
        }
        missing = [c for c in spec["columns"] if c not in cols]
        if missing:
            raise ContractError(f"{spec['file']}: missing column(s) {', '.join(missing)}")


def run_script(con, name: str) -> None:
    con.execute((SQL_DIR / name).read_text(encoding="utf-8"))


def check_sql(check: dict) -> str:
    """Render sql/checks/<type>.sql for one contract check (identifiers only from the contract)."""
    kind = ident(check["type"])
    path = SQL_DIR / "checks" / f"{kind}.sql"
    if not path.exists():
        raise ContractError(f"unknown check type {kind!r} in check {check['id']}")
    column = check["column"]
    params = {
        "table": ident(check["table"]),
        "column": ", ".join(ident(c) for c in column) if isinstance(column, list) else ident(column),
        "to_table": ident(check.get("to", "customers")),
        "min": repr(float(check.get("min", 0))),
        "max": repr(float(check.get("max", 0))),
    }
    return path.read_text(encoding="utf-8").format(**params)


def run_check(con, check: dict) -> dict:
    values = check.get("values", [check["value"]] if "value" in check else [])
    table(con, "cfg_check_values", "value VARCHAR", [(str(v),) for v in values])
    failing, rows = con.execute(check_sql(check)).fetchone()
    failing, rows = int(failing), int(rows)
    observed = failing / rows if rows else 0.0
    ok = observed <= check["max"] if check["type"] == "max_ratio" else failing == 0
    status = "pass" if ok else ("fail" if check["severity"] == "error" else "warn")
    return {
        "id": check["id"],
        "severity": check["severity"],
        "status": status,
        "failing_rows": failing,
        "observed": observed,
    }


def run_checks(con, contract: dict, tables: set[str]) -> list[dict]:
    return [run_check(con, c) for c in contract["checks"] if c["table"] in tables]


def raise_on_errors(results: list[dict]) -> None:
    failed = [r["id"] for r in results if r["status"] == "fail"]
    if failed:
        raise ContractError("contract check(s) failed: " + ", ".join(failed))


def score_sql(fit: dict) -> str:
    """The linear predictor as a SQL expression, in feature order, with exact (repr) coefficients."""
    terms = [repr(fit["intercept"])] + [f"({b!r}) * f.{ident(n)}" for n, b in fit["coefficients"].items()]
    return " + ".join(terms)


def fit_stage(con, names: list[str], stage: str) -> dict:
    cols = ", ".join(f"f.{ident(n)}" for n in names)
    rows = con.execute(
        f"""SELECT {cols}, f.churned FROM stage_rows AS r
            INNER JOIN features AS f ON r.customer_id = f.customer_id AND r.snapshot = f.snapshot
            WHERE r.stage = ? AND r.role = 'fit' ORDER BY f.snapshot, f.customer_id""",
        [stage],
    ).fetchnumpy()
    x = np.column_stack([rows[n] for n in names])
    return fit_logistic(x, rows["churned"], names)


def fit_rows(con, names: list[str], splits: list[str]) -> dict:
    """Fit on every feature row of the given splits (the v1.1 challenger refit)."""
    cols = ", ".join(f"f.{ident(n)}" for n in names)
    marks = ", ".join("?" for _ in splits)
    rows = con.execute(
        f"SELECT {cols}, f.churned FROM features AS f WHERE f.split IN ({marks}) ORDER BY f.snapshot, f.customer_id",
        splits,
    ).fetchnumpy()
    return fit_logistic(np.column_stack([rows[n] for n in names]), rows["churned"], names)


def fit_logistic_experiments(con, contract: dict) -> dict:
    """Fit every logistic experiment on every stage and score its eval rows back into `scored`."""
    stages = [r[0] for r in con.execute("SELECT stage FROM cfg_stages ORDER BY stage").fetchall()]
    fits = {}
    for exp in contract["experiments"]:
        if exp["kind"] != "logistic":
            continue
        names = experiment_features(exp, contract)
        for stage in stages:
            fit = fit_stage(con, names, stage)
            fits[(exp["id"], stage)] = fit
            con.execute(
                f"""INSERT INTO scored
                    SELECT ?, r.stage, r.customer_id, r.snapshot, f.churned, 1 / (1 + exp(-({score_sql(fit)})))
                    FROM stage_rows AS r
                    INNER JOIN features AS f ON r.customer_id = f.customer_id AND r.snapshot = f.snapshot
                    WHERE r.stage = ? AND r.role = 'eval'""",
                [exp["id"], stage],
            )
    return fits


def deployed_path(contract: dict) -> Path:
    return Path(os.environ.get("DEPLOYED_MODEL_PATH") or REPO / contract["monitoring"]["deployed_model"])


def insert_scores(con, model: str, fit: dict, splits: list[str]) -> None:
    marks = ", ".join("?" for _ in splits)
    con.execute(
        f"""INSERT INTO post_scored
            SELECT ?, f.customer_id, f.snapshot, f.split, f.churned, 1 / (1 + exp(-({score_sql(fit)})))
            FROM features AS f WHERE f.split IN ({marks})""",
        [model, *splits],
    )


def calibration_offset(con, fit: dict, split: str) -> float:
    """Newton's method for the intercept shift d with sum(sigmoid(eta + d)) = sum(y) on one split; each step is one
    SQL aggregate over the rows (the same iteration as glm(y ~ 1, offset = eta) in R)."""
    d = 0.0
    for _ in range(100):
        grad, hess = con.execute(
            f"""WITH s AS (SELECT f.churned AS y, 1 / (1 + exp(-({score_sql(fit)} + ?))) AS p
                           FROM features AS f WHERE f.split = ?)
                SELECT sum(p - y), sum(p * (1 - p)) FROM s""",
            [d, split],
        ).fetchone()
        step = float(grad) / float(hess)
        d -= step
        if abs(step) < 1e-13:
            break
    return d


def score_post_deployment(con, contract: dict, fits: dict) -> dict | None:
    """Fill post_scored for 07_monitoring.sql. With labelled recent and holdout months (1.1): the deployed model on the
    training and post-deployment rows, and the challenger (refit + recalibrated) on its refit, recent and holdout rows.
    Otherwise: this run's champion on its training rows (the reference profile of its artefact)."""
    con.execute(
        "CREATE OR REPLACE TABLE post_scored (model VARCHAR, customer_id VARCHAR, snapshot VARCHAR, split VARCHAR, "
        "y INTEGER, p DOUBLE)"
    )
    labelled = {r[0] for r in con.execute("SELECT DISTINCT split FROM features WHERE churned IS NOT NULL").fetchall()}
    champion_id = con.execute("SELECT champion_id FROM champion").fetchone()[0]
    used = experiment_features(next(e for e in contract["experiments"] if e["id"] == champion_id), contract)
    if "monitoring" not in contract or not {"recent", "holdout"} <= labelled:
        insert_scores(con, "champion", fits[(champion_id, "test")], ["train"])
        table(con, "cfg_model_features", "model VARCHAR, name VARCHAR", [("artefact", ident(n)) for n in used])
        table(con, "cfg_profile_splits", "split VARCHAR", [("train",)])
        return None
    deployed = json.loads(deployed_path(contract).read_text(encoding="utf-8"))
    rt = contract["retraining"]
    insert_scores(con, "champion", deployed, ["train", *POST])
    fit = fit_rows(con, used, list(rt["refit_splits"]))
    offset = calibration_offset(con, fit, rt["calibrate_on"])
    challenger = {"intercept": fit["intercept"] + offset, "coefficients": fit["coefficients"]}
    insert_scores(con, "challenger", challenger, [*rt["refit_splits"], rt["calibrate_on"], rt["decide_on"]])
    table(
        con,
        "cfg_model_features",
        "model VARCHAR, name VARCHAR",
        [("champion", ident(n)) for n in deployed["features"]] + [("artefact", ident(n)) for n in used],
    )
    table(con, "cfg_profile_splits", "split VARCHAR", [(s,) for s in rt["refit_splits"]])
    return {"deployed": deployed, "challenger": challenger, "offset": offset, "features": used}


def rows_of(con, sql: str, params: list | None = None) -> list[dict]:
    cur = con.execute(sql, params or [])
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]


def num(v):
    """DuckDB returns HUGEINT sums as int and DECIMAL never (all DOUBLE); keep None as None."""
    if v is None:
        return None
    return int(v) if isinstance(v, int) and not isinstance(v, bool) else float(v)


def load_and_clean(con, data_dir: str | os.PathLike, contract: dict) -> dict:
    """M1: variables, raw tables (01_load.sql) and clean tables (02_clean.sql). Returns export.json."""
    export = load_export(data_dir)
    prepare(con, data_dir, contract, export)
    check_raw_columns(con, data_dir, contract)
    run_script(con, "01_load.sql")
    run_script(con, "02_clean.sql")
    return export


def analyse(con, data_dir: str | os.PathLike, contract: dict) -> dict:
    export = load_and_clean(con, data_dir, contract)
    checks = run_checks(con, contract, {"customers", "invoices", "usage", "tickets", "raw_usage"})
    raise_on_errors(checks)
    run_script(con, "03_features.sql")
    snap_checks = run_checks(con, contract, {"snapshots"})
    checks += snap_checks
    raise_on_errors(snap_checks)
    run_script(con, "04_models.sql")
    fits = fit_logistic_experiments(con, contract)
    run_script(con, "05_metrics.sql")
    run_script(con, "06_evaluate.sql")
    post = score_post_deployment(con, contract, fits)
    run_script(con, "07_monitoring.sql")
    return assemble(con, contract, export, checks, fits, post)


def experiment_block(con, exp: dict, contract: dict) -> dict:
    folds = rows_of(
        con,
        "SELECT CAST(substr(stage, 3) AS INTEGER) AS fold, rows, auc, brier, log_loss FROM fit_metrics "
        "WHERE exp_id = ? AND stage LIKE 'cv%' ORDER BY fold",
        [exp["id"]],
    )
    cv = rows_of(con, "SELECT * EXCLUDE (exp_id) FROM cv_summary WHERE exp_id = ?", [exp["id"]])[0]
    test = rows_of(con, "SELECT * FROM fit_metrics WHERE exp_id = ? AND stage = 'test'", [exp["id"]])[0]
    cap = rows_of(con, "SELECT * EXCLUDE (exp_id) FROM capacity WHERE exp_id = ?", [exp["id"]])[0]
    return {
        "id": exp["id"],
        "name": exp["name"],
        "kind": exp["kind"],
        "features": experiment_features(exp, contract),
        "cv": {
            **{k: num(cv[k]) for k in ("auc_mean", "auc_sd", "brier_mean", "log_loss_mean")},
            "folds": [{k: num(v) for k, v in f.items()} for f in folds],
        },
        "test": {**{k: num(test[k]) for k in TEST_METRICS}, **{k: num(cap[k]) for k in CAPACITY}},
    }


def profile_of(con, edges: str, shares: str, features: list[str]) -> dict:
    """Edges and shares per variable from 07_monitoring.sql, in the artefact's feature order."""
    e, sh = {}, {}
    for var, edge in con.execute(f"SELECT var, edge FROM {ident(edges)} ORDER BY var, edge").fetchall():
        e.setdefault(var, []).append(float(edge))
    for var, share in con.execute(f"SELECT var, share FROM {ident(shares)} ORDER BY var, bin").fetchall():
        sh.setdefault(var, []).append(float(share))
    return {v: {"edges": e.get(v, []), "shares": sh[v]} for v in [*features, "__score__"]}


def monitoring_section(con, contract: dict, post: dict) -> dict:
    mon = contract["monitoring"]
    names = post["deployed"]["features"]
    drift_rows = rows_of(con, "SELECT snapshot, var, psi, status FROM drift_status")
    by = {(r["snapshot"], r["var"]): r for r in drift_rows}
    counts = rows_of(
        con,
        "SELECT snapshot, any_value(split) AS split, count(*) AS rows FROM post_scored "
        "WHERE model = 'champion' AND split <> 'train' GROUP BY snapshot ORDER BY snapshot",
    )
    perf = {r["snapshot"]: r for r in rows_of(con, "SELECT * FROM monitor_performance")}
    drift, performance, alerts = [], [], []
    for c in counts:
        snap = c["snapshot"]
        per = {f: float(by[(snap, f)]["psi"]) for f in names}
        status = {f: by[(snap, f)]["status"] for f in names}
        score = by[(snap, "__score__")]
        drift.append(
            {
                "snapshot": snap,
                "split": c["split"],
                "rows": int(c["rows"]),
                "score_psi": float(score["psi"]),
                "score_status": score["status"],
                "feature_psi": per,
                "features_watch": [f for f in names if status[f] == "watch"],
                "features_drift": [f for f in names if status[f] == "drift"],
            }
        )
        alerts += [f"{snap}: {f} drifted (PSI {per[f]:.3f})" for f in drift[-1]["features_drift"]]
        if snap in perf:
            m = perf[snap]
            own = []
            if m["alert_ece"]:
                own.append(f"ECE {m['ece']:.3f} > {mon['alert_max_ece']}")
            if m["alert_mean_gap"]:
                own.append(f"mean predicted {m['mean_pred']:.3f} vs observed {m['observed_rate']:.3f}")
            if m["alert_auc"]:
                own.append(f"AUC {m['auc']:.3f} < {mon['alert_min_auc']}")
            performance.append(
                {
                    "snapshot": snap,
                    "split": c["split"],
                    "rows": int(m["rows"]),
                    **{k: float(m[k]) for k in ("auc", "brier", "ece", "mean_pred", "observed_rate")},
                    "alerts": own,
                }
            )
            alerts += [f"{snap}: {a}" for a in own]
    ref_rows = con.execute("SELECT count(*) FROM post_scored WHERE model = 'champion' AND split = 'train'").fetchone()
    return {
        "deployed_model": {
            "path": mon["deployed_model"],
            "model_version": post["deployed"]["model_version"],
            "trained_by_track": post["deployed"]["generator"]["track"],
        },
        "reference": {"split": "train", "rows": int(ref_rows[0])},
        "drift": drift,
        "performance": performance,
        "alerts": alerts,
        "status": "retrain" if any(r["alerts"] for r in performance) else ("watch" if alerts else "ok"),
    }


def retraining_section(con, contract: dict, post: dict) -> dict:
    rt = contract["retraining"]
    one = lambda sql, p=None: con.execute(sql, p or []).fetchone()  # noqa: E731
    marks = ", ".join("?" for _ in rt["refit_splits"])
    refit_snaps = [
        r[0]
        for r in con.execute(
            f"SELECT DISTINCT snapshot FROM features WHERE split IN ({marks}) ORDER BY snapshot", rt["refit_splits"]
        ).fetchall()
    ]
    refit_rows = one(f"SELECT count(*) FROM features WHERE split IN ({marks})", rt["refit_splits"])[0]
    calib = one("SELECT min(snapshot) FROM features WHERE split = ?", [rt["calibrate_on"]])[0]
    hold = rows_of(
        con,
        "SELECT min(snapshot) AS snapshot, count(*) AS rows, avg(churned) AS churn_rate FROM features WHERE split = ?",
        [rt["decide_on"]],
    )[0]
    metrics = {r.pop("model"): r for r in rows_of(con, "SELECT * EXCLUDE (rows) FROM holdout_metrics")}
    checks = [
        {"id": r["id"], "value": float(r["value"]), "threshold": float(r["threshold"]), "passed": bool(r["passed"])}
        for r in rows_of(con, "SELECT id, value, threshold, passed FROM retraining_gate ORDER BY pos")
    ]
    passed = all(c["passed"] for c in checks)
    ch = post["challenger"]
    return {
        "challenger": {
            "features": post["features"],
            "refit_snapshots": refit_snaps,
            "refit_rows": int(refit_rows),
            "calibration_snapshot": calib,
            "calibration_offset": post["offset"],
            "intercept": ch["intercept"],
            "coefficients": ch["coefficients"],
        },
        "holdout": {"snapshot": hold["snapshot"], "rows": int(hold["rows"]), "churn_rate": float(hold["churn_rate"])},
        "champion_holdout": {k: num(v) for k, v in metrics["champion"].items()},
        "challenger_holdout": {k: num(v) for k, v in metrics["challenger"].items()},
        "gate": {"checks": checks, "passed": passed},
        "decision": "promote" if passed else "keep",
    }


def assemble(con, contract: dict, export: dict, checks: list[dict], fits: dict, post: dict | None = None) -> dict:
    names = feature_names(contract)
    one = lambda sql, p=None: con.execute(sql, p or []).fetchone()  # noqa: E731
    issues = {r["issue"]: int(r["n"]) for r in rows_of(con, "SELECT issue, n FROM issues ORDER BY pos")}
    raw_rows = {t: one(f"SELECT count(*) FROM raw_{t}")[0] for t in TABLES}
    clean_rows = {t: one(f"SELECT count(*) FROM {t}")[0] for t in TABLES}
    summary = [
        {k: (num(v) if k in ("rows", "churned", "churn_rate") else v) for k, v in r.items()}
        for r in rows_of(con, "SELECT snapshot, split, rows, churned, churn_rate FROM snapshots ORDER BY snapshot")
    ]
    split = rows_of(
        con,
        """SELECT count(*) FILTER (WHERE split = 'train') AS train_rows, count(*) FILTER (WHERE split = 'test')
           AS test_rows, avg(churned) FILTER (WHERE split = 'train') AS train_churn_rate,
           avg(churned) FILTER (WHERE split = 'test') AS test_churn_rate FROM features""",
    )[0]
    folds = rows_of(
        con,
        """SELECT k.fold, count(f.customer_id) AS rows, count(DISTINCT f.customer_id) AS customers,
           coalesce(sum(f.churned), 0) AS churners
           FROM (SELECT CAST(range AS INTEGER) AS fold FROM range(getvariable('folds'))) AS k
           LEFT JOIN features AS f ON f.fold = k.fold AND f.split = 'train' GROUP BY k.fold ORDER BY k.fold""",
    )
    two_folds = one(
        "SELECT count(*) FROM (SELECT customer_id FROM features WHERE split = 'train' "
        "GROUP BY customer_id HAVING count(DISTINCT fold) > 1)"
    )[0]
    leak_rows = rows_of(con, "SELECT * FROM leakage ORDER BY pos")
    per = {r["name"]: r["auc"] for r in leak_rows if r["kind"] == "feature"}
    worst = max(names, key=lambda k: per[k])
    limit = float(contract["evaluation"]["leakage_max_single_feature_auc"])
    leak = {
        "feature_auc": {n: per[n] for n in names},
        "max_feature": worst,
        "max_feature_auc": per[worst],
        "limit": limit,
        "probe": "customers.cancellation_reason is filled",
        "probe_auc": next(r["auc"] for r in leak_rows if r["kind"] == "probe"),
        "passed": bool(per[worst] < limit),
    }
    experiments = [experiment_block(con, e, contract) for e in contract["experiments"]]
    ch = rows_of(con, "SELECT * FROM champion")[0]
    champion_id, gain = ch["champion_id"], ch["gain"]
    need = contract["champion"]["min_cv_auc_gain_for_complexity"]
    if champion_id == ch["bigger_id"]:
        reason = f"{ch['bigger_id']} beats {ch['simple_id']} by {gain:.4f} mean CV AUC (>= {need})"
    else:
        reason = f"{ch['bigger_id']} gains only {gain:.4f} mean CV AUC (< {need}): keep the simpler {ch['simple_id']}"
    champ = next(e for e in experiments if e["id"] == champion_id)
    used = champ["features"]
    fit = fits[(champion_id, "test")]
    stats = {
        r["feature"]: r
        for r in rows_of(
            con,
            "SELECT l.feature, avg(l.value) AS mean, stddev_pop(l.value) AS sd FROM feature_long AS l "
            "WHERE l.split = 'train' GROUP BY l.feature",
        )
    }
    means = {f: float(stats[f]["mean"]) for f in used}
    sds = {f: float(stats[f]["sd"]) for f in used}
    threshold = one("SELECT quantile_cont(p, 0.9) FROM scored WHERE exp_id = ? AND stage = 'train'", [champion_id])[0]
    importance = sorted(
        (
            {
                "feature": f,
                "coefficient": fit["coefficients"][f],
                "sd": sds[f],
                "standardised": fit["coefficients"][f] * sds[f],
            }
            for f in used
        ),
        key=lambda r: -abs(r["standardised"]),
    )
    bins = rows_of(
        con,
        "SELECT bin, lower, upper, n, mean_pred, observed FROM calibration_bins "
        "WHERE exp_id = ? AND stage = 'test' ORDER BY bin",
        [champion_id],
    )
    test_fit = rows_of(con, "SELECT * FROM fit_metrics WHERE exp_id = ? AND stage = 'test'", [champion_id])[0]
    calibration = {
        "bins": [{k: num(v) for k, v in b.items()} for b in bins],
        "ece": float(test_fit["ece"]),
        "mean_pred": float(test_fit["mean_pred"]),
        "observed_rate": float(test_fit["observed_rate"]),
    }
    slices = {}
    for r in rows_of(
        con, "SELECT * EXCLUDE (exp_id, dim_pos) FROM slices WHERE exp_id = ? ORDER BY dim_pos, value", [champion_id]
    ):
        dim = r.pop("dim")
        slices.setdefault(dim, []).append({k: (v if k == "value" else num(v)) for k, v in r.items()})
    fair_row = rows_of(con, "SELECT * FROM fairness WHERE exp_id = ?", [champion_id])[0]
    fcfg = contract["evaluation"]["fairness"]
    fairness = {
        "dimension": fcfg["dimension"],
        "groups": list(fair_row["groups"]),
        "recall_gap": float(fair_row["recall_gap"]),
        "flagged_rate_ratio": num(fair_row["flagged_rate_ratio"]),
        "max_recall_gap": fcfg["max_recall_gap"],
        "passed": bool(fair_row["recall_gap"] <= fcfg["max_recall_gap"]),
    }
    gate_checks = [
        {"id": r["id"], "value": float(r["value"]), "threshold": float(r["threshold"]), "passed": bool(r["passed"])}
        for r in rows_of(con, "SELECT id, value, threshold, passed FROM gate ORDER BY pos")
    ]
    gate = {"checks": gate_checks, "passed": all(c["passed"] for c in gate_checks)}
    test_m = champ["test"]
    train_churners = one("SELECT sum(churned) FROM features WHERE split = 'train'")[0]
    training = {
        "export": export["export"],
        "contract_version": contract["contract_version"],
        "snapshots": contract["snapshots"]["train"],
        "rows": int(split["train_rows"]),
        "churners": int(train_churners),
    }
    artefact = {
        "schema_version": SCHEMA_VERSION,
        "name": "churncast",
        "model_version": __version__,
        "kind": "logistic_regression",
        "target": "churned_next_month",
        "experiment": champion_id,
        "features": used,
        "intercept": fit["intercept"],
        "coefficients": {f: fit["coefficients"][f] for f in used},
        "feature_means": means,
        "high_risk_threshold": float(threshold),
        "base_rate": float(split["train_churn_rate"]),
        "training": training,
        "test_metrics": {k: test_m[k] for k in ARTEFACT_TEST_KEYS},
        "monitoring_reference": None,
        "lineage": {"parent_model_version": None, "trained_on": contract["snapshots"]["train"]},
        "generator": {"track": TRACK, "version": __version__},
    }
    sections = {}
    if post is not None:
        sections["monitoring"] = monitoring_section(con, contract, post)
        sections["retraining"] = rt = retraining_section(con, contract, post)
        c = rt["challenger"]
        rtc = contract["retraining"]
        marks = ", ".join("?" for _ in rtc["refit_splits"])
        refit_means = {
            r["feature"]: float(r["mean"])
            for r in rows_of(
                con,
                f"SELECT feature, avg(value) AS mean FROM feature_long WHERE split IN ({marks}) GROUP BY feature",
                rtc["refit_splits"],
            )
        }
        recent = rows_of(
            con,
            "SELECT quantile_cont(p, 0.9) AS threshold, avg(y) AS base_rate FROM post_scored "
            "WHERE model = 'challenger' AND split = ?",
            [rtc["calibrate_on"]],
        )[0]
        churners = one(f"SELECT sum(churned) FROM features WHERE split IN ({marks})", rtc["refit_splits"])[0]
        artefact.update(
            {
                "intercept": c["intercept"],
                "coefficients": {f: c["coefficients"][f] for f in used},
                "feature_means": {f: refit_means[f] for f in used},
                "high_risk_threshold": float(recent["threshold"]),
                "base_rate": float(recent["base_rate"]),
                "training": {
                    "export": export["export"],
                    "contract_version": contract["contract_version"],
                    "snapshots": c["refit_snapshots"],
                    "rows": c["refit_rows"],
                    "churners": int(churners),
                },
                "test_metrics": {k: rt["challenger_holdout"][k] for k in ARTEFACT_TEST_KEYS},
                "lineage": {
                    "parent_model_version": post["deployed"]["model_version"],
                    "refit_snapshots": c["refit_snapshots"],
                    "calibration_snapshot": c["calibration_snapshot"],
                    "calibration_offset": c["calibration_offset"],
                    "decided_on": rt["holdout"]["snapshot"],
                    "decision": rt["decision"],
                },
            }
        )
    prof = profile_of(con, "profile_edges", "profile_shares", used)
    n_profile = one("SELECT count(*) FROM profile_values WHERE var = '__score__'")[0]
    artefact["monitoring_reference"] = {
        "bins": 10,
        "rows": int(n_profile),
        "features": {f: prof[f] for f in used},
        "score": prof["__score__"],
    }
    metrics = {
        "schema_version": SCHEMA_VERSION,
        "generator": {"track": TRACK, "version": __version__},
        "dataset": {
            "export": export["export"],
            "period_end": export["period_end"],
            "contract_version": contract["contract_version"],
        },
        "data_quality": {"raw_rows": raw_rows, "clean_rows": clean_rows, "issues": issues, "checks": checks},
        "snapshots": summary,
        "split": {
            "train_snapshots": contract["snapshots"]["train"],
            "test_snapshots": contract["snapshots"]["test"],
            "train_rows": int(split["train_rows"]),
            "test_rows": int(split["test_rows"]),
            "train_churn_rate": float(split["train_churn_rate"]),
            "test_churn_rate": float(split["test_churn_rate"]),
            "folds": [{k: int(v) for k, v in f.items()} for f in folds],
            "customers_in_two_folds": int(two_folds),
        },
        "leakage": leak,
        "experiments": experiments,
        "champion": {
            "experiment": champion_id,
            "reason": reason,
            "features": used,
            "intercept": fit["intercept"],
            "coefficients": fit["coefficients"],
            "feature_means": means,
            "importance": importance,
            "high_risk_threshold": float(threshold),
        },
        "test": test_m,
        "calibration": calibration,
        "slices": slices,
        "fairness": fairness,
        "gate": gate,
        **sections,
    }
    return {"metrics": metrics, "artefact": artefact}


def write_outputs(con, result: dict, contract: dict, out_dir: str | os.PathLike) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    cols = ["customer_id", "snapshot", "split", "fold", "churned", *feature_names(contract), *SLICE_COLUMNS]
    select = ", ".join(ident(c) for c in cols)
    con.execute(
        f"COPY (SELECT {select} FROM features ORDER BY snapshot, customer_id) TO '{(out / 'features.csv').as_posix()}'"
        " (HEADER, DELIMITER ',')"
    )
    (out / "metrics.json").write_text(json.dumps(result["metrics"], indent=2) + "\n", encoding="utf-8")
    (out / "model.json").write_text(json.dumps(result["artefact"], indent=2) + "\n", encoding="utf-8")
    m = result["metrics"]
    with open(out / "experiments.jsonl", "w", encoding="utf-8") as fh:
        for e in m["experiments"]:
            line = {
                "run": {
                    "export": m["dataset"]["export"],
                    "contract_version": m["dataset"]["contract_version"],
                    "track": TRACK,
                    "version": __version__,
                },
                "id": e["id"],
                "name": e["name"],
                "features": e["features"],
                "cv_auc_mean": e["cv"]["auc_mean"],
                "cv_auc_sd": e["cv"]["auc_sd"],
                "test_auc": e["test"]["auc"],
                "test_brier": e["test"]["brier"],
                "champion": e["id"] == m["champion"]["experiment"],
            }
            fh.write(json.dumps(line) + "\n")
