# Requirements — Production Insight

> Phase 2 — Requirements Definition.
> Each requirement follows the format defined in `CLAUDE.md` §17.

---

## Index

| ID | Name | Status |
|---|---|---|
| REQ-001 | Upload Production CSV | Defined |
| REQ-002 | Upload Downtime CSV | Defined |
| REQ-003 | Validate Production Records | Merged into REQ-001 |
| REQ-004 | Validate Downtime Records | Merged into REQ-002 |
| REQ-005 | Data Quality Report | Defined |
| REQ-006 | Store Valid Records | Merged into REQ-001 / REQ-002 |
| REQ-007 | Calculate Production KPIs | Defined |
| REQ-008 | Calculate Quality KPIs | Defined |
| REQ-009 | Calculate Downtime KPIs | Defined |
| REQ-010 | Calculate Baselines | Defined |
| REQ-011 | Detect Deviations | Defined |
| REQ-012 | Generate Explainable Alerts | Pending |
| REQ-013 | Calculate Priority Scores | Pending |
| REQ-014 | Display Dashboard | Pending |

Merged IDs are kept (not reused) so references stay stable.

---

## Cross-Cutting Decisions

These decisions apply to all data ingestion requirements.

| Decision | Choice |
|---|---|
| Upload method | File upload button in Streamlit |
| File with errors | Store valid records; report invalid records |
| Reloading existing data | Replace, by shift |
| Error detail | Shown after the upload and downloadable as CSV; not stored in the database |
| Load history | Each upload's summary is stored in the database (see REQ-005) |

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

---

## REQ-005: Data Quality Report

### Problem

Upload summaries (REQ-001, REQ-002) show what happened in a single upload, but not the overall state of the data. Before trusting KPIs and alerts, the supervisor needs to know:

- Whether there are downtime events without a production record.
- Whether there are missing dates, lines or shifts that could distort averages and baselines.
- What was loaded, when, and with what result.

### Input

Data already stored in the database:

- Production records
- Downtime events
- Load history
- Master lists (`data/master/`)

### Process

The report is calculated from the database every time the user opens it. It has three sections.

#### 1. Orphan Downtime Events

Downtime events whose `date + line + shift + product` has no production record.

They can appear when a production shift is replaced and a product is removed (see REQ-001, Open Points).

#### 2. Coverage Gaps

Production records expected but not found.

```text
Period   = from the earliest to the latest date with production records
Expected = every Monday–Saturday in the period × every line in lines.csv × shifts 1, 2, 3
Gap      = expected date + line + shift with no production record
```

**Working calendar:**

- Monday to Saturday are regular working days and are expected to have data.
- Sunday is not a regular working day and **never generates gaps**.
- **Sunday overtime:** production and downtime on a Sunday are accepted and stored like any other day. They are counted in KPIs and shown in the coverage report as "overtime shifts". No configuration is needed: Sunday overtime is detected from the data itself.

Gaps are shown as **"missing data"**, not as errors: a gap may still be planned (e.g., a holiday).

#### 3. Load History

A record of every upload, stored in the database when the upload finishes:

| Field | Description |
|---|---|
| loaded_at | Date and time of the upload |
| file_type | `production` or `downtime` |
| file_name | Name of the uploaded file |
| rows_read | Rows in the file |
| rows_stored | Rows stored |
| rows_rejected | Rows rejected |
| shifts_replaced | Existing shifts replaced |
| shifts_new | New shifts stored |
| shifts_rejected | Shifts rejected |
| warnings | Number of warnings |
| status | `completed` or `rejected` (whole file rejected) |

Uploads rejected at file level (e.g., missing columns) are also recorded, with `status = rejected`.

Error detail per row is **not** stored (see Cross-Cutting Decisions).

### Output

A **Data Quality** section in the dashboard:

```text
Data Quality — Period 2026-09-01 to 2026-09-30

Orphan downtime events:   3   (45 min)
Coverage:                 232 / 234 shifts with data (99.1%)   (Mon–Sat)
Missing shifts:           2
Sunday overtime shifts:   4
Last upload:              2026-10-07 09:14 — downtime — completed
```

Each section can be expanded to see the detail (list of orphan events, list of missing shifts, full load history).

### Acceptance Criteria

```text
[ ] Orphan downtime events are listed with date, line, shift, product, minutes and reason.
[ ] Coverage shows expected shifts, shifts with data, percentage, and the list of missing shifts.
[ ] The coverage period is calculated from the stored production data.
[ ] Missing shifts are labeled as "missing data", not as errors.
[ ] Only Monday–Saturday shifts are expected; a Sunday without data never appears as a gap.
[ ] Sunday shifts with data are accepted and listed as overtime shifts.
[ ] Every upload (completed or rejected) creates a load history record.
[ ] The load history is shown from newest to oldest.
[ ] With an empty database, the report shows a clear "no data loaded" message instead of failing.
[ ] Results match a manual check on the sample dataset (known orphans and known gaps).
```

### Dependencies

- REQ-001 and REQ-002 (data and load summaries).
- Master list `data/master/lines.csv`.
- Database table for load history.

### Open Points

- **Holidays and planned stops:** holidays (Monday–Saturday) and lines not running a given shift still appear as gaps. A holiday calendar is out of scope for the MVP.
- **Effect on baselines:** resolved in REQ-010 — daily values are normalized per shift worked, so gaps do not distort baselines.
- **Sunday overtime in baselines:** resolved in REQ-010 — Sundays are excluded from baselines and from alert evaluation.

---

## KPI Common Rules

These rules apply to REQ-007, REQ-008 and REQ-009.

### Scope of Calculation

- KPIs are calculated over the data matching the active filters: **period**, **line**, **product** and **shift**. Without filters, all stored data is used.
- Filters are displayed in the dashboard (REQ-014); KPI calculations must accept them as inputs.
- Sunday overtime shifts are included like any other shift.
- **Orphan downtime events are excluded** from KPIs, because they have no production record to relate to. The dashboard shows how many were excluded (see REQ-005).

### Definitions

| Term | Definition |
|---|---|
| Production record | One row: `date + line + shift + product` |
| Shift worked | One distinct `date + line + shift` with at least one production record |
| Ratio of totals | A rate is always calculated as `SUM(numerator) / SUM(denominator)` over the group, never as an average of individual rates |

### Display

- Quantities: whole units, with thousands separator (e.g., `12,450`).
- Rates: percentage with one decimal (e.g., `3.2%`).
- Minutes: whole minutes; hours shown in parentheses when ≥ 60 (e.g., `1,230 min (20.5 h)`).
- When a rate cannot be calculated (denominator = 0), show `N/A`, never `0%` or an error.

---

## REQ-007: Calculate Production KPIs

### Problem

The supervisor needs to know how much was produced and which lines, products and shifts produced more or less, to detect low output.

### Input

Production records in the database, filtered by the active filters.

### Process

| KPI | Formula |
|---|---|
| Total production | `SUM(production_quantity)` |
| Average production per shift | `Total production / number of shifts worked` |
| Production by line | Total production grouped by `line` |
| Production by product | Total production grouped by `product` |
| Production by shift | Total production grouped by `shift` (1, 2, 3) |

Each grouped KPI also shows the number of shifts worked in the group, so groups with different activity can be compared (e.g., `L1: 24,500 units in 26 shifts`).

### Output

Values for each KPI, ready to be displayed in the dashboard.

### Acceptance Criteria

```text
[ ] Total production matches a manual sum on the sample dataset.
[ ] Average production per shift uses distinct date + line + shift, not number of rows (a shift with two products counts once).
[ ] Production by line, product and shift matches manual calculations.
[ ] Each grouped KPI shows the number of shifts worked.
[ ] KPIs respond to period, line, product and shift filters.
[ ] With no data for the filters, KPIs show a "no data" message instead of failing.
```

### Dependencies

- REQ-001 (production records).

---

## REQ-008: Calculate Quality KPIs

### Problem

The supervisor needs to know how much scrap was generated, the scrap rate, and which lines, products and shifts have the highest scrap rate, to decide where to investigate quality issues.

### Input

Production records in the database, filtered by the active filters.

### Process

| KPI | Formula |
|---|---|
| Total scrap quantity | `SUM(scrap_quantity)` |
| Scrap rate | `SUM(scrap_quantity) / SUM(production_quantity)` |
| Scrap by line | Scrap quantity and scrap rate grouped by `line` |
| Scrap by product | Scrap quantity and scrap rate grouped by `product` |
| Scrap by shift | Scrap quantity and scrap rate grouped by `shift` |

**Ratio of totals** (decided 2026-10-07): the scrap rate of a group is total scrap divided by total production, so each shift weighs according to what it produced.

Example:

```text
Shift A: production 1,000, scrap 10   (1.0%)
Shift B: production    10, scrap  5   (50.0%)

Scrap rate = 15 / 1,010 = 1.5%     ← used
Average of rates = 25.5%           ← not used
```

Records with `production_quantity = 0` add nothing to the numerator or denominator, so they do not affect the rate.

If a group has total production = 0, its scrap rate is `N/A`.

### Output

Values for each KPI. Grouped results include both scrap quantity and scrap rate, because a high rate on low volume and a lower rate on high volume can both matter.

### Acceptance Criteria

```text
[ ] Total scrap matches a manual sum on the sample dataset.
[ ] Scrap rate is calculated as total scrap / total production, not as an average of rates.
[ ] A test case with uneven volumes (like the example above) returns 1.5%.
[ ] Records with production_quantity = 0 do not cause errors.
[ ] A group with total production = 0 shows N/A.
[ ] Scrap by line, product and shift shows quantity and rate.
[ ] KPIs respond to period, line, product and shift filters.
```

### Dependencies

- REQ-001 (production records).

---

## REQ-009: Calculate Downtime KPIs

### Problem

The supervisor needs to know how much downtime occurred, where it is concentrated (line, product, shift) and what its main causes are, to decide where to act.

### Input

- Downtime events in the database (excluding orphans), filtered by the active filters.
- Production records, to count shifts worked.

### Process

| KPI | Formula |
|---|---|
| Total downtime | `SUM(downtime_minutes)` |
| Average downtime per shift | `Total downtime / number of shifts worked` |
| Downtime by line | Total downtime grouped by `line` |
| Downtime by product | Total downtime grouped by `product` |
| Downtime by shift | Total downtime grouped by `shift` |
| Downtime by cause | Total downtime and number of events grouped by `downtime_reason`, sorted from highest to lowest minutes, with % of total |

**Shifts without downtime count as zero.** The average is divided by all shifts worked, not only by shifts with downtime events. Otherwise, the average would be inflated.

Example:

```text
4 shifts worked; downtime: 60, 0, 0, 20 min

Average = 80 / 4 = 20 min per shift      ← used
Average of shifts with downtime = 40     ← not used
```

Setup / Changeover downtime is attributed to the incoming product (ADR-001).

### Output

Values for each KPI. Downtime by cause includes minutes, number of events and % of total downtime.

### Acceptance Criteria

```text
[ ] Total downtime matches a manual sum on the sample dataset.
[ ] Average downtime per shift divides by all shifts worked, including shifts with no downtime events.
[ ] A test case like the example above returns 20 min per shift.
[ ] Downtime by line, product and shift matches manual calculations.
[ ] Downtime by cause shows minutes, number of events and % of total, sorted descending.
[ ] Orphan downtime events are excluded, and the number excluded is shown.
[ ] KPIs respond to period, line, product and shift filters.
```

### Dependencies

- REQ-001 (production records, shifts worked).
- REQ-002 (downtime events).
- REQ-005 (orphan detection).

---

## Detection Decisions

Decided 2026-10-07. These apply to REQ-010 and REQ-011.

| Decision | Choice |
|---|---|
| Compared against | The **same line's own history** (not other lines) |
| Period evaluated | The **last working day** with data |
| Alert threshold | More than **2 standard deviations** from the baseline mean, in the unfavorable direction |

Comparing a line against other lines ("which line is worst") is already answered by the KPIs (REQ-007 to REQ-009). Detection answers a different question: **"did something change?"**

---

## REQ-010: Calculate Baselines

### Problem

To decide whether a value is abnormal, the system needs a reference of what is normal for each line. Without a defined baseline, an alert cannot explain what it was compared against.

### Input

- Production records and downtime events (excluding orphans).
- The evaluated day (see REQ-011).

### Process

#### Metrics

A baseline is calculated per **line** for three daily metrics:

| Metric | Daily value per line | Unfavorable direction |
|---|---|---|
| Production per shift | `SUM(production_quantity) / shifts worked` | Lower |
| Scrap rate | `SUM(scrap_quantity) / SUM(production_quantity)` | Higher |
| Downtime per shift | `SUM(downtime_minutes) / shifts worked` | Higher |

Values are normalized **per shift worked** so that a day with a missing shift (coverage gap, REQ-005) does not look like a production drop or a downtime improvement.

#### Baseline Days

The baseline of a line uses its **previous days**, with these rules:

- Only days **before** the evaluated day (the evaluated day is never part of its own baseline).
- Only **Monday to Saturday**. Sunday overtime is excluded because it usually runs with different crews, products or number of shifts.
- Only days where the line has at least one shift worked.
- For scrap rate, days with total production = 0 are excluded (rate undefined).

#### Statistics

For each line and metric:

```text
mean       = average of the daily values in the baseline days
std        = sample standard deviation of the daily values (n − 1)
n          = number of baseline days
```

#### Minimum History

- A baseline requires **at least 10 days** (`n ≥ 10`).
- If `n < 10`, the baseline is marked **"insufficient history"** and no alert is generated for that line and metric.
- If `std = 0` (all baseline days identical), the baseline is marked **"no variation"** and no alert is generated.

With one month of data (≈ 25 working days), every line that runs regularly has enough history.

### Output

One baseline per line and metric:

```text
line   metric          mean    std    n    status
L2     scrap_rate      3.2%    0.9%   24   ok
L3     downtime/shift  41      12     8    insufficient history
```

### Acceptance Criteria

```text
[ ] Baselines are calculated per line for production per shift, scrap rate and downtime per shift.
[ ] The evaluated day is excluded from its own baseline.
[ ] Sundays are excluded from baselines.
[ ] Daily values are normalized per shift worked; a day with a missing shift does not distort the baseline.
[ ] Scrap rate baselines exclude days with total production = 0.
[ ] Standard deviation is the sample standard deviation (n − 1).
[ ] With fewer than 10 baseline days, the status is "insufficient history".
[ ] With std = 0, the status is "no variation".
[ ] Mean, std and n match a manual calculation on the sample dataset.
```

### Dependencies

- REQ-001, REQ-002 (data).
- REQ-005 (orphan exclusion, working calendar).
- REQ-007 to REQ-009 (metric definitions).

### Open Points

- **Baselines per product or per line + shift:** not included in the MVP. Products do not run every day, so their daily history is sparse. May be evaluated after the MVP.

---

## REQ-011: Detect Deviations

### Problem

The supervisor needs the system to point out which lines had abnormal behavior on the last working day, instead of reviewing every KPI manually.

### Input

- Baselines (REQ-010).
- Daily values of the evaluated day.

### Process

#### Evaluated Day

The **last Monday–Saturday date** with production data.

If the last date with data is a Sunday (overtime), the evaluated day is the Saturday before it. Sunday overtime is visible in the KPIs but is not evaluated for alerts in the MVP.

#### Deviation Calculation

For each line and metric with a baseline status `ok`:

```text
z = (value − mean) / std
percent_deviation = (value − mean) / mean × 100
```

#### Alert Rule

A deviation is detected when it is **more than 2 standard deviations in the unfavorable direction**:

| Metric | Condition |
|---|---|
| Production per shift | `z < −2` |
| Scrap rate | `z > 2` |
| Downtime per shift | `z > 2` |

Favorable deviations (e.g., unusually low scrap) do not generate alerts.

The threshold (2) is defined as a single named constant so it can be adjusted and documented.

If the line has no production on the evaluated day, no deviation is calculated for it; the missing shifts appear in the coverage report (REQ-005).

### Output

One record per detected deviation:

| Field | Example |
|---|---|
| date | 2026-09-30 |
| line | L2 |
| metric | scrap_rate |
| value | 8.7% |
| baseline_mean | 3.2% |
| baseline_std | 0.9% |
| sample_size | 24 days |
| z | +6.1 |
| percent_deviation | +171.8% |
| shifts_worked | 3 |

Lines and metrics without a valid baseline are listed separately with their status ("insufficient history", "no variation"), so the user knows they were not evaluated.

These records are the input for explainable alerts (REQ-012) and prioritization (REQ-013).

### Acceptance Criteria

```text
[ ] The evaluated day is the last Monday–Saturday date with production data.
[ ] Each injected anomaly in the sample dataset (on the evaluated day) is detected.
[ ] A normal day in the sample dataset generates no deviations.
[ ] Only unfavorable deviations beyond 2 standard deviations are detected.
[ ] Each deviation includes value, mean, std, sample size, z and percent deviation.
[ ] Lines and metrics without a valid baseline are listed as not evaluated, with the reason.
[ ] A line with no production on the evaluated day does not produce an error.
```

### Dependencies

- REQ-010 (baselines).

### Open Points

- **Threshold value:** 2 standard deviations is the starting point. It will be reviewed with the sample dataset (too many or too few alerts).
- **Evaluating past days:** the MVP evaluates only the last working day. Reviewing alerts for earlier dates may be evaluated later.
