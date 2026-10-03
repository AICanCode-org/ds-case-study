#!/usr/bin/env python3
"""Generate the TiffinBox exports in data/raw/<export>/ (synthetic, seeded, standard library only).

    python3 scripts/generate_data.py            # write every export
    python3 scripts/generate_data.py --check    # exit 1 if a committed file differs from what the seed produces

The whole timeline (2025-01 .. 2026-07) is simulated once with a fixed seed; each export is a cut of it as the
data team would have seen it at the end of its last month (signups, invoices and usage up to that month, tickets
created by then, and resolution times / cancellation reasons only if they were known by then). So a later export
contains every row of an earlier one: an append-only history, exactly what monitoring in Phase 7 relies on.

The data is synthetic but realistic on purpose: churn depends on usage, service quality, tickets, payment failures,
price changes and tenure, plus things the model cannot see (acquisition channel, age band, a latent "mood"). The raw
files carry the defects real exports have (label variants, two date formats, money as text, duplicates, orphans,
impossible values) and one leaky column (customers.cancellation_reason). All of it is documented in
contract/feature-spec.md; nothing here is a person's data.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import sys
from pathlib import Path

SEED = 20260603
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
EXPORTS = ["2026-05", "2026-07"]
FIRST = (2025, 1)
N_MONTHS = 19  # 2025-01 .. 2026-07
DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

CITIES = [("pune", 0.30), ("bengaluru", 0.25), ("hyderabad", 0.20), ("nagpur", 0.13), ("indore", 0.12)]
CITY_VARIANTS = {
    "pune": ["Pune", "PUNE", " pune"],
    "bengaluru": ["Bangalore", "Bengaluru ", "BENGALURU", "bangalore"],
    "hyderabad": ["Hyderabad", "HYDERABAD", "hyderabad "],
    "nagpur": ["Nagpur", " NAGPUR"],
    "indore": ["Indore", "INDORE "],
}
LATE_BASE = {"pune": 0.06, "bengaluru": 0.10, "hyderabad": 0.07, "nagpur": 0.05, "indore": 0.05}
CHANNELS = [("organic", 0.35), ("referral", 0.20), ("paid_social", 0.30), ("partner", 0.15)]
CHANNEL_EFFECT = {"organic": 0.0, "referral": -0.25, "paid_social": 0.25, "partner": 0.1, "influencer": 0.75}
AGE_BANDS = [("18-24", 0.25), ("25-34", 0.40), ("35-44", 0.20), ("45+", 0.15)]
AGE_EFFECT = {"18-24": 0.15, "25-34": 0.0, "35-44": -0.05, "45+": -0.1}
PLANS = ["basic", "standard", "premium"]
PLAN_MEALS = {"basic": 20, "standard": 24, "premium": 26}
PLAN_VARIANTS = {
    "basic": ["Basic", "BASIC", "basic "],
    "standard": ["Standard", "STANDARD", " standard"],
    "premium": ["Premium", "PREMIUM ", "premium"],
}
REASONS = [
    "too expensive",
    "food quality",
    "moving to another city",
    "late deliveries",
    "cooking at home now",
    "not using it enough",
    "found a cheaper option",
]
CATEGORIES = ["delivery", "food_quality", "billing", "app", "other"]


def month_name(i: int) -> str:
    y, m = FIRST[0] + (FIRST[1] - 1 + i) // 12, (FIRST[1] - 1 + i) % 12 + 1
    return f"{y:04d}-{m:02d}"


def days_in(i: int) -> int:
    y, m = month_name(i).split("-")
    d = DAYS[int(m) - 1]
    return 29 if d == 28 and int(y) % 4 == 0 else d


def list_price(plan: str, i: int) -> int:
    if plan == "standard":
        return 3799 if month_name(i) >= "2026-06" else 3299  # the June 2026 price rise (Phase 7)
    return {"basic": 2499, "premium": 4499}[plan]


def pick(rng: random.Random, weighted):
    return rng.choices([v for v, _ in weighted], weights=[w for _, w in weighted])[0]


def poisson(rng: random.Random, lam: float) -> int:
    limit, k, p = math.exp(-lam), 0, rng.random()
    while p > limit:
        k += 1
        p *= rng.random()
    return k


def sigmoid(z: float) -> float:
    return 1 / (1 + math.exp(-z))


def ts(i: int, day: int, minute_of_day: int) -> tuple:
    return (month_name(i), day, minute_of_day // 60, minute_of_day % 60, 0)


def fmt_ts(t: tuple, style: str) -> str:
    ym, day, hh, mm, ss = t
    y, m = ym.split("-")
    if style == "dmy":
        return f"{day:02d}/{m}/{y} {hh:02d}:{mm:02d}"
    return f"{y}-{m}-{day:02d} {hh:02d}:{mm:02d}:{ss:02d}"


def add_hours(t: tuple, hours: float) -> tuple:
    ym, day, hh, mm, _ = t
    i = next(k for k in range(N_MONTHS + 2) if month_name(k) == ym)
    total = (day - 1) * 1440 + hh * 60 + mm + int(hours * 60)
    while total >= days_in(i) * 1440:
        total -= days_in(i) * 1440
        i += 1
    return (month_name(i), total // 1440 + 1, (total % 1440) // 60, total % 60, 0)


def money(rng: random.Random, rupees: int) -> str:
    style = rng.random()
    if rupees < 0:
        return f"-{abs(rupees)}.00"
    if style < 0.55:
        return str(rupees)
    if style < 0.80:
        return f"{rupees:,}.00"
    if style < 0.95:
        return f"₹{rupees:,}"
    return f" {rupees}.0 "


def simulate() -> dict:
    rng = random.Random(SEED)
    customers, invoices, usage, tickets = [], [], [], []
    cid = 0
    inv_no = 0
    tk_no = 0
    for t0 in range(N_MONTHS):
        n_new = 250 + 8 * t0 + (90 if month_name(t0) >= "2026-06" else 0)
        for k in range(n_new):
            cid += 1
            c_id = f"C{cid:05d}"
            influencer = month_name(t0) >= "2026-06" and k >= n_new - 90
            channel = "influencer" if influencer else pick(rng, CHANNELS)
            city = pick(rng, CITIES)
            age = pick(rng, AGE_BANDS)
            plan = (
                "basic"
                if influencer and rng.random() < 0.7
                else pick(rng, [("basic", 0.45), ("standard", 0.40), ("premium", 0.15)])
            )
            day = rng.randint(1, days_in(t0))
            engagement = PLAN_MEALS[plan] * math.exp(rng.gauss(0, 0.15))
            mood = rng.gauss(0, 0.6) + CHANNEL_EFFECT[channel] * 0.6
            rate_prop = 0.0 if rng.random() < 0.25 else rng.uniform(0.1, 0.5)
            price_sensitive = rng.random() < 0.2
            cust = {
                "customer_id": c_id,
                "t0": t0,
                "day": day,
                "city": city,
                "channel": channel,
                "age_band": age,
                "churn_month": None,
                "reason": "",
            }
            customers.append(cust)
            prev_price = None
            had_discount_months = 0
            i = t0
            while i < N_MONTHS:
                tenure = i - t0
                price = list_price(plan, i)
                promo = tenure < 2 and channel in ("paid_social", "influencer", "partner")
                share_off = 0.4 if channel == "influencer" else 0.2  # influencer codes: 40 % off for two months
                discount = round(price * share_off) if promo else (round(price * 0.1) if rng.random() < 0.04 else 0)
                had_discount_months += discount > 0
                failed = rng.random() < (0.07 if price_sensitive else 0.025)
                if failed:
                    inv_no += 1
                    invoices.append(
                        {
                            "invoice_id": f"INV{inv_no:07d}",
                            "customer_id": c_id,
                            "month": i,
                            "kind": "charge",
                            "plan": plan,
                            "list_price": price,
                            "discount": discount,
                            "status": "failed",
                        }
                    )
                    if rng.random() > 0.85:  # the retry fails too: involuntary churn this month
                        cust["churn_month"], cust["reason"] = i, "payment failed"
                        break
                inv_no += 1
                invoices.append(
                    {
                        "invoice_id": f"INV{inv_no:07d}",
                        "customer_id": c_id,
                        "month": i,
                        "kind": "charge",
                        "plan": plan,
                        "list_price": price,
                        "discount": discount,
                        "status": "paid",
                    }
                )
                if rng.random() < 0.02:
                    inv_no += 1
                    invoices.append(
                        {
                            "invoice_id": f"INV{inv_no:07d}",
                            "customer_id": c_id,
                            "month": i,
                            "kind": "refund",
                            "plan": plan,
                            "list_price": -rng.choice([150, 300, 450]),
                            "discount": 0,
                            "status": "paid",
                        }
                    )
                # usage of month i
                share = 1.0 if tenure > 0 else (days_in(i) - day + 1) / days_in(i)
                late_rate = max(0.0, LATE_BASE[city] + rng.gauss(0, 0.03))
                meals = max(0, min(60, round(engagement * share * (1 - 0.22 * max(mood, -1)) + rng.gauss(0, 2))))
                skipped = max(0, min(30, round(rng.gauss(1.5 + 5.0 * max(mood, 0), 1.2) * max(share, 0.3))))
                late = max(0, min(meals, round(meals * late_rate + rng.gauss(0, 0.8))))
                r_count = round(meals * rate_prop)
                r_mean = min(5.0, max(1.0, 4.4 - 0.45 * mood - 3 * late_rate + rng.gauss(0, 0.3)))
                usage.append(
                    {
                        "customer_id": c_id,
                        "month": i,
                        "meals_ordered": meals,
                        "meals_skipped": skipped,
                        "late_deliveries": late,
                        "ratings_count": r_count,
                        "ratings_sum": round(r_mean * r_count),
                    }
                )
                n_tk = poisson(rng, 0.05 + 0.12 * max(mood, 0) + 1.2 * late_rate + (0.5 if failed else 0))
                for _ in range(n_tk):
                    tk_no += 1
                    cat = (
                        "billing"
                        if failed and rng.random() < 0.5
                        else pick(
                            rng,
                            [("delivery", 0.25 + late_rate * 3), ("food_quality", 0.3), ("app", 0.15), ("other", 0.15)],
                        )
                    )
                    created = ts(i, rng.randint(1, days_in(i)), rng.randint(7 * 60, 23 * 60))
                    hours = None if rng.random() < 0.05 else math.exp(rng.gauss(3.0, 1.0))
                    tickets.append(
                        {
                            "ticket_id": f"T{tk_no:06d}",
                            "customer_id": c_id,
                            "created": created,
                            "category": cat,
                            "resolved": None if hours is None else add_hours(created, hours),
                        }
                    )
                skip_rate = skipped / (meals + skipped) if meals + skipped else 0.0
                price_jump = (price - prev_price) / prev_price if prev_price else 0.0
                z = (
                    -3.45
                    + 1.0 * mood
                    + 0.8 * (tenure < 3)
                    - 0.03 * min(tenure, 18)
                    + 2.2 * skip_rate
                    + 3.0 * late_rate
                    - 0.3 * (r_mean - 4) * (r_count > 0)
                    + 0.3 * n_tk
                    + 0.6 * failed
                    + CHANNEL_EFFECT[channel]
                    + AGE_EFFECT[age]
                    + 3.5 * max(price_jump, 0)
                    + (0.5 if promo and tenure == 1 else 0)
                    + (1.0 if channel == "influencer" and tenure == 1 else 0)
                )
                if month_name(i) >= "2026-05":  # a rival service launched in May 2026: bad service now costs more
                    z += 6.0 * max(late_rate - 0.05, 0) + 2.0 * skip_rate + 0.2 * n_tk
                prev_price = price
                if rng.random() < sigmoid(z):
                    cust["churn_month"], cust["reason"] = i + 1, rng.choice(REASONS)
                    if rng.random() < 0.6:  # many churners raise a cancellation ticket in the month they leave
                        tk_no += 1
                        created = (
                            ts(i + 1, rng.randint(1, 5), rng.randint(8 * 60, 22 * 60)) if i + 1 < N_MONTHS + 1 else None
                        )
                        tickets.append(
                            {
                                "ticket_id": f"T{tk_no:06d}",
                                "customer_id": c_id,
                                "created": created,
                                "category": "cancellation",
                                "resolved": add_hours(created, 2.0),
                            }
                        )
                    break
                mood = 0.75 * mood + rng.gauss(0, 0.45) + 1.5 * (late_rate - 0.06)
                r = rng.random()
                if r < 0.02 and plan != "premium":
                    plan = PLANS[PLANS.index(plan) + 1]
                elif r < 0.04 and plan != "basic":
                    plan = PLANS[PLANS.index(plan) - 1]
                i += 1
    return {"customers": customers, "invoices": invoices, "usage": usage, "tickets": tickets}


def render(sim: dict) -> dict:
    """Raw rows with their defects. Every random choice is made once per row, so the defects are the same in
    every export that contains the row. Returns {table: [(month_index_visible_from, csv_line_fields), ...]}."""
    rng = random.Random(SEED + 1)
    out = {"customers": [], "invoices": [], "usage": [], "tickets": []}
    for c in sim["customers"]:
        city = rng.choice(CITY_VARIANTS[c["city"]]) if rng.random() < 0.15 else c["city"].capitalize()
        y, m = month_name(c["t0"]).split("-")
        date = f"{y}-{m}-{c['day']:02d}" if rng.random() > 0.03 else f"{c['day']:02d}/{m}/{y}"
        if rng.random() < 0.0008:
            date = f"{y}-{m}-{c['day'] + 31:02d}"  # an impossible date: the row cannot be used
        channel = "" if month_name(c["t0"]) < "2025-03" else c["channel"]  # channel tracking started in March 2025
        if channel and rng.random() < 0.1:
            channel = channel.upper() if rng.random() < 0.5 else f" {channel}"
        age = "" if rng.random() < 0.03 else c["age_band"]
        row = [c["customer_id"], date, city, channel, age]
        out["customers"].append((c["t0"], row, c))
        if rng.random() < 0.01:
            out["customers"].append((c["t0"], list(row), c))
    for v in sim["invoices"]:
        plan = rng.choice(PLAN_VARIANTS[v["plan"]]) if rng.random() < 0.1 else v["plan"]
        row = [
            v["invoice_id"],
            v["customer_id"],
            month_name(v["month"]),
            v["kind"],
            plan,
            money(rng, v["list_price"]),
            str(v["discount"]),
            v["status"],
        ]
        out["invoices"].append((v["month"], row))
        if rng.random() < 0.005:
            out["invoices"].append((v["month"], list(row)))
    orphan = 0
    for u in sim["usage"]:
        row = [
            u["customer_id"],
            month_name(u["month"]),
            str(u["meals_ordered"]),
            str(u["meals_skipped"]),
            str(u["late_deliveries"]),
            str(u["ratings_count"]),
            str(u["ratings_sum"]),
        ]
        if rng.random() < 0.002:
            row[3] = "-1"  # an impossible value from a broken upstream job
        out["usage"].append((u["month"], row))
        if rng.random() < 0.005:
            out["usage"].append((u["month"], list(row)))
        if rng.random() < 0.0006:
            orphan += 1
            out["usage"].append((u["month"], [f"C9{orphan:04d}", *row[1:]]))
    for t in sim["tickets"]:
        if t["created"] is None:
            continue
        cat = t["category"].upper() if rng.random() < 0.05 else t["category"]
        style = "dmy" if rng.random() < 0.05 else "iso"
        created = fmt_ts(t["created"], style)
        resolved = t["resolved"]
        if resolved is not None and rng.random() < 0.006:
            resolved = ("swap", t["created"])  # resolved before created: a clock problem in the helpdesk tool
        visible = next(k for k in range(N_MONTHS + 1) if month_name(k) == t["created"][0])
        out["tickets"].append(
            (visible, [t["ticket_id"], t["customer_id"], created, cat, resolved, style, t["created"]])
        )
        if rng.random() < 0.0015:
            out["tickets"].append(
                (
                    visible,
                    [
                        t["ticket_id"].replace("T", "T9"),
                        f"C9{rng.randint(1, 999):04d}",
                        created,
                        cat,
                        resolved,
                        style,
                        t["created"],
                    ],
                )
            )
    return out


def export_files(rendered: dict, e: int) -> dict[str, str]:
    cut_end = (month_name(e + 1) if e + 1 <= N_MONTHS else "9999-99", 1, 0, 0, 0)  # first instant after the export
    files = {}
    lines = ["customer_id,signup_date,city,acquisition_channel,age_band,cancellation_reason"]
    for t0, row, c in rendered["customers"]:
        if t0 <= e:
            reason = c["reason"] if c["churn_month"] is not None and c["churn_month"] <= e else ""
            lines.append(",".join([*row, reason]))
    files["customers.csv"] = "\n".join(lines) + "\n"
    lines = ["invoice_id,customer_id,billing_month,kind,plan,list_price,discount,status"]
    lines += [",".join(f'"{x}"' if "," in x else x for x in row) for m, row in rendered["invoices"] if m <= e]
    files["invoices.csv"] = "\n".join(lines) + "\n"
    lines = ["customer_id,month,meals_ordered,meals_skipped,late_deliveries,ratings_count,ratings_sum"]
    lines += [",".join(row) for m, row in rendered["usage"] if m <= e]
    files["usage.csv"] = "\n".join(lines) + "\n"
    lines = ["ticket_id,customer_id,created_at,category,resolved_at"]
    for m, (tid, cust, created, cat, resolved, style, created_t) in rendered["tickets"]:
        if m > e:
            continue
        if resolved is None:
            res = ""
        elif resolved[0] == "swap":
            res = fmt_ts(add_hours(created_t, -5.0), style)
        else:
            res = fmt_ts(resolved, style) if (resolved[0], resolved[1], resolved[2], resolved[3]) < cut_end[:4] else ""
        lines.append(",".join([tid, cust, created, cat, res]))
    files["tickets.csv"] = "\n".join(lines) + "\n"
    meta = {
        "export": month_name(e),
        "company": "TiffinBox (synthetic)",
        "period_start": "2025-01-01",
        "period_end": f"{month_name(e)}-{days_in(e):02d}",
        "generator": "scripts/generate_data.py",
        "seed": SEED,
        "files": {k: hashlib.sha256(v.encode()).hexdigest() for k, v in sorted(files.items())},
    }
    files["export.json"] = json.dumps(meta, indent=2) + "\n"
    return files


def main(argv: list[str]) -> int:
    check = "--check" in argv
    rendered = render(simulate())
    bad = 0
    for name in EXPORTS:
        e = next(k for k in range(N_MONTHS) if month_name(k) == name)
        for fname, text in export_files(rendered, e).items():
            path = RAW / name / fname
            if check:
                if not path.exists() or path.read_text(encoding="utf-8") != text:
                    print(f"DIFFERENT: {path.relative_to(ROOT)}")
                    bad += 1
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
                print(f"wrote {path.relative_to(ROOT)} ({text.count(chr(10)) - 1} rows)")
    if check:
        print("data/raw is exactly what the seed produces" if not bad else f"{bad} file(s) differ")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
