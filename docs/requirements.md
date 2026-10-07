# Requirements — Production Insight

> Phase 2 — Requirements Definition.
> Each requirement follows the format defined in `CLAUDE.md` §17.

---

## Cross-Cutting Decisions

These decisions apply to all data ingestion requirements.

| Decision | Choice |
|---|---|
| Upload method | File upload button in Streamlit |
| File with errors | Store valid records; report invalid records |
| Reloading existing data | Replace, by shift |

Details: `docs/decisions/ADR-002-reload-strategy.md`.

### Master Lists

Lines, products and downtime reasons must belong to a **fixed list**. Free text is not allowed, to prevent inconsistent capture (e.g., `L1` vs. `Ll` creating a new line).

The lists are stored as small CSV files, maintained manually:

```text
data/master/
├── lines.csv              (column: line)
├── products.csv           (column: product)
└── downtime_reasons.csv   (column: downtime_reason)
```

- Values are compared exactly (case-sensitive, after trimming spaces).
- Adding a new line or product means adding a row to the corresponding file.
- If a master list file is missing or empty, the upload is rejected with a clear message.
- The MVP does not validate which products can run on which lines.

### Replacement Unit: the Shift

The unit of replacement is `date + line + shift`.

- For every `date + line + shift` present in the uploaded file, all existing records for that shift are deleted and replaced with the records in the file.
- The uploaded file is treated as the **complete truth** for every shift it contains.
- Shifts not present in the file are not modified.

### Invalid Rows and Replacement

A shift is replaced **only if all of its rows in the file are valid**.

If any row of a shift is invalid:

- None of the rows of that shift are stored.
- The existing data for that shift is kept unchanged.
- All rows of that shift are reported, indicating which row caused the rejection.

Reason: replacing a shift with partial data would silently lose information (e.g., keeping Product A but deleting Product B because B's new row had a typo).

---

## REQ-001: Upload Production CSV

### Problem

The supervisor needs to load production and scrap data into the system so it can be analyzed, and needs to know which data was not accepted and why.

### Input

CSV file uploaded through a button in the Streamlit dashboard.

Required columns:

| Column | Type | Rule |
|---|---|---|
| date | date | Format `YYYY-MM-DD`; valid calendar date; not in the future |
| line | text | Must exist in `data/master/lines.csv` |
| shift | integer | 1, 2 or 3 |
| product | text | Must exist in `data/master/products.csv` |
| production_quantity | integer | ≥ 0 |
| scrap_quantity | integer | ≥ 0 and ≤ `production_quantity` |

### Process

1. **File-level validation.** The whole file is rejected, and nothing is stored, if:
   - The file is not a readable CSV.
   - The file is empty or has no data rows.
   - One or more required columns are missing.
   - A master list file (lines or products) is missing or empty.
2. **Row-level validation.** Each row is checked against the column rules above.
3. **Duplicate check.** Rows with the same `date + line + shift + product` inside the file are all invalid (the system cannot know which one is correct).
4. **Shift grouping.** Rows are grouped by `date + line + shift`. A shift is accepted only if all its rows are valid.
5. **Replacement.** For each accepted shift, existing production records for that `date + line + shift` are deleted and the new rows are inserted, as a single transaction.

Extra columns not in the list are ignored and reported as a warning.

### Output

**Load summary:**

```text
Rows read:              120
Rows stored:            114
Rows rejected:            6
Shifts replaced:         40
Shifts new:               2
Shifts rejected:          2
```

**Error detail**, one line per rejected row:

```text
Row   Column               Value     Reason
14    scrap_quantity       1200      Scrap greater than production (950)
15    —                    —         Rejected: shift 2026-10-03 / L2 / 1 has invalid rows
37    date                 2026-13-01 Invalid date
```

### Acceptance Criteria

```text
[ ] A CSV file can be uploaded from the dashboard.
[ ] A file missing a required column is rejected entirely, with a message naming the missing column(s).
[ ] An empty or unreadable file is rejected with a clear message.
[ ] Each column rule is validated, and each invalid row reports row number, column, value and reason.
[ ] A line or product not in its master list is rejected, naming the unknown value.
[ ] Duplicate rows (same date + line + shift + product) in the file are rejected.
[ ] Valid shifts are stored in the database.
[ ] Loading a file with a shift that already exists replaces all records of that shift.
[ ] A shift with at least one invalid row is not stored, and its existing data is kept.
[ ] The load summary shows rows read, stored, rejected, and shifts replaced / new / rejected.
[ ] A failure during storage does not leave a shift partially replaced.
```

### Dependencies

- Database schema for production records (`CLAUDE.md` §10).
- Master list files `data/master/lines.csv` and `data/master/products.csv`.

### Open Points

- **`production_quantity = 0`:** accepted (e.g., a shift fully stopped). The scrap rate for that record is undefined; this must be handled in the quality KPI requirement.
- **Effect on downtime events:** when a shift is replaced and a product disappears, its downtime events become orphans. They are not deleted automatically; they are reported in the data quality summary (REQ-005). The user fixes them by reloading the downtime file for that shift (REQ-002).

---

## REQ-002: Upload Downtime CSV

### Problem

The supervisor needs to load downtime events, with their cause and product, so downtime can be analyzed by line, shift, product and cause, and needs to know which events were not accepted and why.

### Input

CSV file uploaded through a button in the Streamlit dashboard.

Required columns:

| Column | Type | Rule |
|---|---|---|
| date | date | Format `YYYY-MM-DD`; valid calendar date; not in the future |
| line | text | Must exist in `data/master/lines.csv` |
| shift | integer | 1, 2 or 3 |
| product | text | Must exist in `data/master/products.csv` |
| downtime_minutes | number | > 0 and ≤ 480 |
| downtime_reason | text | Must exist in `data/master/downtime_reasons.csv` |

### Load Order

**Production must be loaded before downtime.**

Each downtime event must match an existing production record in the database with the same `date + line + shift + product`. Otherwise, the event is an **orphan** and is rejected.

This enforces ADR-001: every downtime event belongs to a production record.

### Process

1. **File-level validation.** The whole file is rejected, and nothing is stored, if:
   - The file is not a readable CSV.
   - The file is empty or has no data rows.
   - One or more required columns are missing.
   - A master list file (lines, products or downtime reasons) is missing or empty.
2. **Row-level validation.** Each row is checked against the column rules above.
3. **Production match.** Each row must match an existing production record (`date + line + shift + product`). Otherwise: orphan event, invalid.
4. **Shift grouping.** Rows are grouped by `date + line + shift`.
5. **Shift total.** The sum of `downtime_minutes` of all rows of a shift in the file (all products) must not exceed 480. Otherwise, all rows of that shift are invalid.
6. **Shift acceptance.** A shift is accepted only if all its rows are valid.
7. **Replacement.** For each accepted shift, all existing downtime events for that `date + line + shift` (all products) are deleted and the new rows are inserted, as a single transaction.

Identical rows are **not** treated as duplicates: two events with the same values can be real (e.g., two separate 10-minute machine failures). They are stored and reported as a warning.

Extra columns not in the list are ignored and reported as a warning.

### Output

**Load summary:**

```text
Rows read:               85
Rows stored:             79
Rows rejected:            6
Shifts replaced:         30
Shifts new:               5
Shifts rejected:          2
Warnings:                 1
```

**Error detail**, one line per rejected row:

```text
Row   Column            Value               Reason
8     —                 2026-10-04/L3/2/Product C   Orphan event: no production record found
21    downtime_reason   Falla               Not in downtime reasons list
22    downtime_minutes  —                   Rejected: shift 2026-10-06 / L1 / 3 totals 510 min (max 480)
```

### Acceptance Criteria

```text
[ ] A CSV file can be uploaded from the dashboard.
[ ] A file missing a required column is rejected entirely, with a message naming the missing column(s).
[ ] An empty or unreadable file is rejected with a clear message.
[ ] Each column rule is validated, and each invalid row reports row number, column, value and reason.
[ ] A line, product or downtime reason not in its master list is rejected, naming the unknown value.
[ ] An event without a matching production record is rejected as an orphan.
[ ] A shift whose total downtime in the file exceeds 480 minutes is rejected entirely.
[ ] Identical rows are stored and reported as a warning.
[ ] Valid shifts are stored in the database.
[ ] Loading a file with a shift that already has downtime events replaces all events of that shift.
[ ] A shift with at least one invalid row is not stored, and its existing events are kept.
[ ] The load summary shows rows read, stored, rejected, warnings, and shifts replaced / new / rejected.
[ ] A failure during storage does not leave a shift partially replaced.
```

### Dependencies

- REQ-001: production records must exist before downtime events can be loaded.
- Database schema for downtime events (`CLAUDE.md` §10).
- Master list files `data/master/lines.csv`, `data/master/products.csv` and `data/master/downtime_reasons.csv`.

### Open Points

- **Shift without downtime:** a shift with zero downtime simply has no rows in the file. Because replacement only touches shifts present in the file, the MVP cannot "clear" the downtime events of a shift by uploading a file. This is accepted for the MVP.
