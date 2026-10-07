# ADR-002: Data Reload Strategy

## Status

Accepted — 2026-10-07

## Context

Users will upload CSV files through Streamlit. A file may contain dates, lines and shifts that already exist in the database (e.g., a corrected file or an overlapping export).

A file may also contain invalid rows.

The system needs a predictable rule for what happens to existing data and to partially invalid files.

## Options

**File with errors:**

1. Reject the whole file.
2. Store valid records; report invalid records.

**Reload of existing data:**

1. Reject records that already exist.
2. Allow duplicates.
3. Replace by record (`date + line + shift + product`).
4. Replace by shift (`date + line + shift`).

## Decision

- Store valid records and report invalid ones.
- Replace by shift: for every `date + line + shift` in the file, all existing records of that shift are deleted and replaced.
- A shift is replaced only if **all** its rows in the file are valid. Otherwise, the existing data for that shift is kept and the rows are reported.
- Each shift replacement runs inside a database transaction.

## Reason

- Storing valid records lets the user work with most of the data while fixing errors.
- Duplicates would inflate every KPI.
- Replacing by record would leave stale data: if a corrected file removes a product from a shift, the old record would remain.
- Replacing by shift makes the file the complete truth for each shift it contains, which matches how a corrected export is used.
- Skipping shifts with any invalid row avoids silently losing correct existing data because of a typo.

## Consequences

Positive:

- Reloading a corrected file is safe and repeatable (same file → same result).
- No duplicates.
- No partial shifts.

Negative:

- One invalid row blocks the whole shift until the file is corrected.
- Replacing a production shift may leave orphan downtime events; they must be detected and reported.
- Validation must group rows by shift before storing, which is slightly more complex than row-by-row insertion.
