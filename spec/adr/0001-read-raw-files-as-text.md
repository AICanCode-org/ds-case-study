# ADR-0001: Read every raw CSV as text; the cleaning rules decide every type

* **Status:** accepted
* **Date:** 2026-06-04
* **Deciders:** data science team

## Context
The TiffinBox export has prices like `₹3,299`, ` 3299.0 ` and `-150.00`, two date formats (one day-first), padded
ids and blank labels. Three tracks (pandas, DuckDB, readr) must produce identical features, and each library
guesses types differently.

## Options considered
1. **Let the reader infer types** (`pd.read_csv`, `read_csv_auto`, `readr::read_csv`): least code; each library
   guesses differently, a bad value becomes missing silently, and `05/03/2025` may be read as 3 May.
2. **Declare types at read time:** explicit; one bad value fails the read or becomes NA without being counted.
3. **Read everything as text, parse in the cleaning rules:** more code; every rejected value is counted, and the
   rule is the same in every language.

## Decision
Option 3. Every track reads all columns as text with no NA conversion; parsing happens in the rules of
`contract/feature-spec.md` §2, each with its issue counter in `data_quality.issues`.

## Consequences
Every defect is visible and the tracks agree exactly. Cleaning code is longer and is unit-tested on the tiny
fixture. A new format in a future export fails loudly instead of being half-parsed.
