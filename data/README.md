# Data dictionary: TiffinBox exports

Each folder under `raw/` is one export, named after its export month. It holds four CSV files and an `export.json`
with the period and a SHA-256 of every file. The data is **synthetic** (made by `scripts/generate_data.py` with a
fixed seed) but has the defects of real exports on purpose. Never "fix" a raw file by hand: the cleaning rules in
`contract/feature-spec.md` §2 do that, and count it.

```bash
python3 scripts/generate_data.py --check   # every committed file is byte-identical to a fresh generation
```

| Export | Period | Notes |
|---|---|---|
| `2026-05` | 2025-01-01 to 2026-05-31 | the export of the brief (v1.0): train 2025-09 … 2026-02, test 2026-03 … 04 |

## `customers.csv` (one row per customer)
| Column | Type (after cleaning) | Notes |
|---|---|---|
| `customer_id` | text `C00001` | a few exact duplicate rows; stray spaces |
| `signup_date` | date | `2025-03-05` **or** `05/03/2025` (day first); a few impossible dates |
| `city` | text | five cities, mixed case, stray spaces, the old name `Bangalore` |
| `acquisition_channel` | `organic` / `referral` / `paid_social` / `partner` / `unknown` | ~9 % blank |
| `age_band` | `18-24` / `25-34` / `35-44` / `45+` / `unknown` | protected: fairness check only, never a feature |
| `cancellation_reason` | text or blank | **leaky**: filled in when a customer cancels, i.e. after the outcome. Never a feature |

## `invoices.csv` (one row per charge or refund)
| Column | Type | Notes |
|---|---|---|
| `invoice_id` | text `INV0000001` | a few exact duplicates |
| `customer_id` | text | a few point to no customer |
| `billing_month` | `YYYY-MM` | the month the subscription covers |
| `kind` | `charge` / `refund` | mixed case |
| `plan` | `basic` / `standard` / `premium` | mixed case |
| `list_price`, `discount` | rupees as text | `4499`, `₹3,299`, `3,299.00`, `-150.00` (refunds are negative) |
| `status` | `paid` / `failed` | a failed charge is a payment problem, not a renewal |

## `usage.csv` (one row per customer and month)
| Column | Type | Notes |
|---|---|---|
| `customer_id`, `month` | text, `YYYY-MM` | a few exact duplicates and orphans |
| `meals_ordered`, `meals_skipped`, `late_deliveries` | integer | a few negative counts (a logging bug) |
| `ratings_count`, `ratings_sum` | integer | stars 1-5; average = sum / count |

## `tickets.csv` (one row per support ticket)
| Column | Type | Notes |
|---|---|---|
| `ticket_id` | text `T000001` | |
| `customer_id` | text | a few orphans |
| `created_at`, `resolved_at` | timestamp | `2025-01-10 09:19:00` **or** `10/01/2025 09:19` (day first); blank = open; a few resolutions before the creation |
| `category` | `delivery` / `food_quality` / `billing` / `app` / `other` / `cancellation` | mixed case |
