"""The SQL track's report: the key result tables of a run as Markdown (out/report.md), straight from DuckDB."""

from __future__ import annotations

from pathlib import Path

SECTIONS = [
    ("Cleaning: rows dropped or changed per rule", "SELECT issue, n FROM issues ORDER BY pos"),
    ("Snapshots: rows and churn rate per month", "SELECT * FROM snapshots ORDER BY snapshot"),
    (
        "Experiments: cross-validation and test",
        "SELECT e.id, round(cv.auc_mean, 4) AS cv_auc, round(cv.auc_sd, 4) AS cv_sd, round(t.auc, 4) AS test_auc, "
        "round(t.brier, 4) AS test_brier, round(t.ece, 4) AS test_ece FROM cfg_experiments AS e "
        "JOIN cv_summary AS cv ON cv.exp_id = e.id JOIN fit_metrics AS t ON t.exp_id = e.id AND t.stage = 'test' "
        "ORDER BY e.pos",
    ),
    (
        "Capacity: the top 10 % of each test month",
        "SELECT exp_id, contacted, churners_reached, round(precision_at_top, 3) AS precision, "
        "round(recall_at_top, 3) AS recall, round(net_value_inr_per_month) AS net_inr_per_month "
        "FROM capacity ORDER BY exp_id",
    ),
    (
        "Calibration of the champion (test)",
        "SELECT b.bin, b.n, round(b.mean_pred, 4) AS mean_pred, round(b.observed, 4) AS observed "
        "FROM calibration_bins AS b JOIN champion AS c ON b.exp_id = c.champion_id WHERE b.stage = 'test' ORDER BY bin",
    ),
    (
        "Slices of the champion (test)",
        "SELECT s.dim, s.value, s.n, s.churners, round(s.mean_pred, 3) AS mean_pred, round(s.auc, 3) AS auc, "
        "round(s.recall_at_top, 3) AS recall FROM slices AS s JOIN champion AS c ON s.exp_id = c.champion_id "
        "ORDER BY s.dim_pos, s.value",
    ),
    ("Leakage scan (training rows)", "SELECT kind, name, round(auc, 4) AS auc FROM leakage ORDER BY auc DESC"),
    ("Gate", "SELECT id, round(value, 4) AS value, round(threshold, 4) AS threshold, passed FROM gate ORDER BY pos"),
]
MONITORING = [
    (
        "Monitoring: PSI per feature",
        "PIVOT (SELECT d.snapshot, d.var, round(d.psi, 3) AS psi FROM drift AS d) ON snapshot USING any_value(psi) "
        "ORDER BY var",
    ),
    (
        "Monitoring: realised performance of the deployed model",
        "SELECT snapshot, rows, round(auc, 4) AS auc, round(brier, 4) AS brier, round(ece, 4) AS ece, "
        "round(mean_pred, 4) AS mean_pred, round(observed_rate, 4) AS observed, alert_ece, alert_mean_gap, alert_auc "
        "FROM monitor_performance ORDER BY snapshot",
    ),
    (
        "Champion vs challenger (holdout)",
        "SELECT model, round(auc, 4) AS auc, round(brier, 4) AS brier, round(ece, 4) AS ece, "
        "round(mean_pred, 4) AS mean_pred, round(observed_rate, 4) AS observed, round(recall_gap, 4) AS recall_gap "
        "FROM holdout_metrics ORDER BY model",
    ),
    (
        "Retraining gate",
        "SELECT id, round(value, 4) AS value, round(threshold, 4) AS threshold, passed "
        "FROM retraining_gate ORDER BY pos",
    ),
]


def markdown_table(cols: list[str], rows: list[tuple]) -> str:
    def cell(v) -> str:
        return "" if v is None else str(v)

    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(cell(v) for v in r) + " |" for r in rows]
    return "\n".join(lines)


def write_report(con, result: dict, path: Path) -> None:
    m = result["metrics"]
    parts = [
        f"# ChurnCast SQL report: export {m['dataset']['export']}",
        "",
        f"Champion **{m['champion']['experiment']}** ({m['champion']['reason']}); gate "
        f"**{'PASSED' if m['gate']['passed'] else 'FAILED'}**.",
    ]
    sections = SECTIONS + (MONITORING if "monitoring" in m else [])
    if "retraining" in m:
        parts += [
            "",
            f"Monitoring status **{m['monitoring']['status']}**; "
            f"retraining decision **{m['retraining']['decision']}**.",
        ]
    for title, sql in sections:
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description]
        parts += ["", f"## {title}", "", markdown_table(cols, cur.fetchall())]
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")
