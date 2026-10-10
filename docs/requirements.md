# Requirements — Production Insight

> Phase 2 — Requirements Definition.
> Each requirement follows the format defined in `CLAUDE.md` §17.

---

## Index

| ID | Name | Status |
|---|---|---|
| REQ-001 | Upload Production CSV | Implemented (logic + tests; dashboard UI pending) |
| REQ-002 | Upload Downtime CSV | Implemented (logic + tests; dashboard UI pending) |
| REQ-003 | Validate Production Records | Merged into REQ-001 |
| REQ-004 | Validate Downtime Records | Merged into REQ-002 |
| REQ-005 | Data Quality Report | Implemented (logic + tests; dashboard UI pending) |
| REQ-006 | Store Valid Records | Merged into REQ-001 / REQ-002 |
| REQ-007 | Calculate Production KPIs | Defined |
| REQ-008 | Calculate Quality KPIs | Defined |
| REQ-009 | Calculate Downtime KPIs | Defined |
| REQ-010 | Calculate Baselines | Defined |
| REQ-011 | Detect Deviations | Defined |
| REQ-012 | Generate Explainable Alerts | Defined |
| REQ-013 | Calculate Priority Scores | Defined |
| REQ-014 | Display Dashboard | Defined |

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

### Language Decision

Decided 2026-10-07.

| Element | Language |
|---|---|
| Documentation (requirements, ADRs, README) | English |
| Source code (names, comments) | English |
| Dashboard, messages, alerts, error detail shown to the user | **Spanish** |

Details: `docs/decisions/ADR-002-reload-strategy.md`.

### Master Lists

Lines, products and downtime reasons must belong to a **fixed list**. Free text is not allowed, to prevent inconsistent capture (e.g., `L1` vs. `Ll` creating a new line).

The lists are stored as small CSV files, maintained manually:

```text
data/master/
├── lines.csv              (column: line)
├── products.csv           (column: product)
├── downtime_reasons.csv   (columns: downtime_reason, planned)
└── planned_stops.csv      (columns: date, line, shift, reason) — optional
```

- Values are compared exactly (case-sensitive, after trimming spaces).
- Adding a new line or product means adding a row to the corresponding file.
- If a master list file is missing or empty, the upload is rejected with a clear message.
- The MVP does not validate which products can run on which lines.
- `downtime_reasons.csv` marks each reason as planned (`sí`) or unplanned (`no`); `planned_stops.csv` lists days or shifts a line is not scheduled to run (ADR-005).
- Values are stored as captured by supervisors, in **Spanish** (e.g., `Falla de máquina`), and shown in the dashboard as stored.

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
| downtime_minutes | integer | > 0 and ≤ 480 (whole minutes, ADR-004) |
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
           − planned stops (planned_stops.csv)
Gap      = expected date + line + shift with no production record
```

**Working calendar:**

- Monday to Saturday are regular working days and are expected to have data.
- Sunday is not a regular working day and **never generates gaps**.
- **Sunday overtime:** production and downtime on a Sunday are accepted and stored like any other day. They are counted in KPIs and shown in the coverage report as "overtime shifts". No configuration is needed: Sunday overtime is detected from the data itself.
- **Planned stops (ADR-005):** shifts listed in `planned_stops.csv` (empty shift = whole day) are not expected and never generate gaps. If they have data anyway, they are listed with the overtime shifts. The report shows the number of planned stop shifts in the period and any invalid rows of `planned_stops.csv` (ignored).

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
[ ] Shifts in planned_stops.csv (or the whole day when shift is empty) are not expected and never appear as gaps.
[ ] Invalid rows in planned_stops.csv are ignored and listed in the report.
[ ] A missing planned_stops.csv means no planned stops (no error).
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

- **Holidays and planned stops:** resolved by `planned_stops.csv` (ADR-005).
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

### Time Grain

Trend charts can group values by **day**, **week** (Monday–Sunday) or **month**, selected by the user. Rates are always recalculated as ratio of totals for each period, never averaged from daily rates.

With one month of data, the monthly view has a single point; it becomes useful as history grows.

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
| Scrap by shift over time | Scrap rate per shift (rows) × week (columns) |

**Ratio of totals** (decided 2026-10-07): the scrap rate of a group is total scrap divided by total production, so each shift weighs according to what it produced.

Example:

```text
Shift A: production 1,000, scrap 10   (1.0%)
Shift B: production    10, scrap  5   (50.0%)

Scrap rate = 15 / 1,010 = 1.5%     ← used
Average of rates = 25.5%           ← not used
```

**Scrap by shift over time** answers: is the problem always in the same shift, or does it move? Each cell is `SUM(scrap) / SUM(production)` for that shift and week.

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
| Unplanned downtime | `SUM(downtime_minutes)` of unplanned reasons |
| Planned downtime | `SUM(downtime_minutes)` of planned reasons (shown separately) |
| Total downtime | Unplanned + planned |
| Average unplanned downtime per shift | `Unplanned downtime / number of shifts worked` |
| Downtime by line | Total downtime grouped by `line` |
| Downtime by product | Total downtime grouped by `product` |
| Downtime by shift | Total downtime grouped by `shift` |
| Downtime by cause | Total downtime and number of events grouped by `downtime_reason`, sorted from highest to lowest minutes, with % of total |

Planned / unplanned comes from the `planned` column of `downtime_reasons.csv` (ADR-005). Grouped KPIs (by line, product, shift) show unplanned downtime by default; downtime by cause lists every reason with its classification.

**Shifts without downtime count as zero.** The average is divided by all shifts worked, not only by shifts with downtime events. Otherwise, the average would be inflated.

Example:

```text
4 shifts worked; downtime: 60, 0, 0, 20 min

Average = 80 / 4 = 20 min per shift      ← used
Average of shifts with downtime = 40     ← not used
```

`Ajuste / Cambio de modelo` (setup / changeover) downtime is attributed to the incoming product (ADR-001).

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
| Production per available shift | `SUM(production_quantity) / available shifts` | Lower |
| Scrap rate | `SUM(scrap_quantity) / SUM(production_quantity)` | Higher |
| Unplanned downtime per shift | `SUM(unplanned downtime_minutes) / shifts worked` | Higher |

```text
available shifts = (shifts worked × 480 − planned downtime minutes) / 480
```

Planned downtime (ADR-005) is not a loss: it does not count as downtime for alerts, and it reduces the time available for production.

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
| Production per available shift | `z < −2` |
| Scrap rate | `z > 2` |
| Unplanned downtime per shift | `z > 2` |

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

---

## REQ-012: Generate Explainable Alerts

### Problem

A detected deviation (REQ-011) is a set of numbers. The supervisor needs a message that explains, in plain language, what happened, how much it deviated, what it was compared against, why it matters, and where to start looking.

### Input

- Detected deviations (REQ-011).
- Production records and downtime events of the evaluated day, to identify the investigation area.

### Process

Each deviation becomes one alert with these parts (`CLAUDE.md` §12):

| Part | Content |
|---|---|
| What happened | Line, metric, date and current value |
| How much it deviated | Percent deviation and number of standard deviations |
| Compared against | Baseline mean, number of days and period used |
| Why it matters | Estimated impact in pieces (REQ-013) |
| Where to investigate | The detail of the evaluated day that contributes most to the deviation |

#### Investigation Area

| Metric | Investigation area shown |
|---|---|
| Production per available shift | Shift with the lowest production, and the main unplanned downtime cause of the line that day |
| Scrap rate | Product with the highest scrap rate on that line that day |
| Unplanned downtime per shift | Unplanned downtime cause with the most minutes on that line that day, and its shift |

The investigation area points to **where to look**, not to the root cause.

#### Message Template (example)

```text
L2 — Scrap rate above normal (2026-09-30)

Current value:    8.7%
Baseline:         3.2% (average of 24 working days, 2026-09-01 to 2026-09-29)
Deviation:        +171.8% (6.1 standard deviations)
Impact:           ~138 extra scrap pieces today (~400 in the last 6 working days)
Recurrence:       3 of the last 6 working days

Where to investigate: Product B on L2 — scrap rate 12.4% that day.
```

### Output

A list of alerts, each with the parts above, ready to be displayed in the dashboard (REQ-014) and ranked by priority (REQ-013).

### Acceptance Criteria

```text
[ ] Every deviation from REQ-011 produces exactly one alert.
[ ] Every alert shows what happened, current value, baseline, deviation, sample size, impact and recurrence.
[ ] Every alert states the period and number of days used as baseline.
[ ] Every alert shows an investigation area according to its metric.
[ ] Messages contain no internal codes or variable names (e.g., "scrap rate", not "scrap_rate").
[ ] The alert for each injected anomaly in the sample dataset points to the injected line, product or cause.
```

### Dependencies

- REQ-011 (deviations).
- REQ-013 (impact and recurrence values).

### Open Points

- **Language:** alert messages are shown in **Spanish** (see Language Decision). The template above is written in English as documentation; the implemented text will be in Spanish.

---

## REQ-013: Calculate Priority Scores

### Problem

When there are several alerts, the supervisor needs to know which one to investigate first. Alerts measure different things (pieces, %, minutes), so they cannot be compared directly.

### Input

- Detected deviations (REQ-011) and their baselines (REQ-010).
- Daily values of the last 6 working days for each line.

### Process

```text
Priority Score = Cumulative Impact × Frequency
```

Decided 2026-10-07 (ADR-003). This replaces the initial model `Impact × Deviation × Frequency` from `CLAUDE.md` §13.

- **Impact** is measured in **lost pieces**.
- **Frequency** is measured over the **last 6 working days**.
- **Deviation is not part of the score.** It decides whether an alert exists (REQ-011) and is shown in the alert, but it does not rank it.

#### Daily Impact (lost pieces on one day)

All metrics are converted to pieces so they can be compared:

| Metric | Daily impact formula |
|---|---|
| Production per available shift | `(baseline_mean − value) × available_shifts` |
| Scrap rate | `(value − baseline_mean) × production_quantity of the day` |
| Unplanned downtime per shift | `(value − baseline_mean) × shifts_worked × line_rate` |

```text
line_rate (pieces per minute) =
    baseline mean production per available shift
  / (480 − baseline mean unplanned downtime per shift)
```

`line_rate` is calculated from the line's own baseline, so no new data (e.g., standard rates per product) is required.

Example:

```text
L1: baseline 1,200 pieces/shift, baseline downtime 40 min/shift
line_rate = 1,200 / (480 − 40) = 2.73 pieces/min

Evaluated day: 95 min/shift, 3 shifts worked
Daily impact = (95 − 40) × 3 × 2.73 ≈ 450 pieces
```

#### Frequency

Number of days, among the **last 6 working days** (Monday–Saturday, including the evaluated day), on which the same line and metric was beyond the alert threshold, using the same baseline (mean and std) as the evaluated day.

Value from 1 (only the evaluated day) to 6 (every day of the last week).

#### Cumulative Impact

Sum of the daily impact of the days counted in Frequency.

```text
Cumulative Impact = SUM(daily impact) over the days beyond the threshold in the last 6 working days
```

#### Why This Formula

A recurring problem must rank above a one-day problem of similar size: a one-day failure has often already been addressed, while a recurring problem is still active.

Example (approximate values from the sample dataset design):

```text
A1 — L2 scrap, 3 days:   ~83 pieces/day → cumulative ~250 × 3 = ~750   → rank 1
A2 — L1 downtime, 1 day: ~460 pieces    → cumulative  460 × 1 =  460   → rank 2
```

A very large one-day problem (e.g., 1,000 pieces) still ranks above a small recurring one.

#### Ranking

- Alerts are sorted by Priority Score, highest first.
- The position (1, 2, 3...) is shown, together with the components (cumulative impact, frequency) and the deviation, so the user can see **why** an alert ranks higher.
- The score itself has no unit; it is only used to sort.

### Output

Each alert from REQ-012 gets: daily impact (pieces), cumulative impact (pieces), frequency (1–6), deviation (|z|, informative), priority score and rank.

### Acceptance Criteria

```text
[ ] Daily impact is calculated in pieces for all three metrics, using the formulas above.
[ ] line_rate is calculated from the line's baseline.
[ ] A test case like the L1 example returns a daily impact of ≈ 450 pieces.
[ ] Frequency counts the last 6 working days, including the evaluated day, with values from 1 to 6.
[ ] Cumulative impact sums only the days counted in frequency.
[ ] Priority Score = Cumulative Impact × Frequency; deviation is not part of it.
[ ] Alerts are sorted by priority score, highest first.
[ ] Each alert shows rank, cumulative impact, frequency and deviation.
[ ] The dashboard states that the score is a decision-support tool, not an absolute measure of importance.
[ ] In the sample dataset, A1 (recurring scrap on L2) ranks above A2 (one-day downtime on L1).
```

### Dependencies

- REQ-010 (baselines), REQ-011 (deviations), REQ-012 (alerts).

### Known Limitations

- **Overlap between metrics:** a long downtime also reduces production, so the same event may raise a downtime alert and a production alert. Both are shown; the investigation area of each helps relate them.
- **Frequency weighs twice:** frequency increases cumulative impact and multiplies it again. This intentionally favors recurring problems (ADR-003).
- **Recent days in the baseline:** the 5 previous days used for frequency are also part of the baseline. A long recurring problem raises the baseline and may reduce its own frequency. Accepted for the MVP.
- **Pieces are not money:** a lost piece of a cheap product weighs the same as one of an expensive product. Cost per product may be added after the MVP.

---

## REQ-014: Display Dashboard

### Problem

The supervisor needs a single place to load data, check its quality, review KPIs and see which problems to investigate first, without technical knowledge and without manual calculations.

### Input

Results of REQ-001 to REQ-013.

### Process

A single Streamlit application, in **Spanish**.

#### Layout

**Sidebar:**

1. Upload: production CSV button, then downtime CSV button (in that order, as required by REQ-002).
2. Filters: period (date range), line, product, shift. Default: all data.
3. Time grain for trend charts: day, week or month.

**Main area — tabs:**

```text
Resumen | Alertas | Producción | Calidad | Paros | Calidad de datos
```

`Alertas` is placed second because it answers the main question of the project: **where to investigate first**.

#### Filters and Alerts

- KPI tabs (Resumen, Producción, Calidad, Paros) respond to all filters.
- Alerts always evaluate the **last working day** (REQ-011); the period filter does not change them. The line filter does: it shows only alerts for the selected lines.
- Each tab shows the active filters at the top.

#### Content: Every Visualization Answers a Question

Per `CLAUDE.md` §15, each element is listed with the question it answers.

**Resumen**

| Element | Question it answers |
|---|---|
| Cards: total production, scrap rate, total downtime, number of alerts | How did the operation go overall? |
| Evaluated day and top-priority alert | What is the most important problem right now? |

**Alertas**

| Element | Question it answers |
|---|---|
| Ranked table: rank, line, problem, current value, baseline, deviation, impact (pieces), recurrence | Which problem should I investigate first? |
| Expandable detail with the full explanation (REQ-012) | Why was this flagged, and where do I start? |
| Lines/metrics not evaluated, with reason | Is anything missing from the evaluation? |
| Note: the score is decision support, not absolute truth | How much should I trust the ranking? |

**Producción**

| Element | Question it answers |
|---|---|
| Bar chart: production by line, with shifts worked | Which line produced the most / least? |
| Bar chart: production by product | Which products concentrate the volume? |
| Bar chart: production by shift | Is there a shift with lower output? |

**Calidad**

| Element | Question it answers |
|---|---|
| Bar chart: scrap rate by line (with scrap quantity) | Which line has the highest scrap rate? |
| Bar chart: scrap rate by product | Which product has the highest scrap rate? |
| Bar chart: scrap rate by shift | Is scrap concentrated in a shift? |
| Line chart: scrap rate per line, by day / week / month | Is the problem recurring or getting worse? |
| Heatmap: scrap rate by shift × week | Is the problem always in the same shift? |

**Paros**

| Element | Question it answers |
|---|---|
| Bar chart: downtime by line | Which line had the most downtime? |
| Sorted bar chart (Pareto): downtime by cause, with % of total | What are the main downtime causes? |
| Bar chart: downtime by shift and by product | Is downtime concentrated in a shift or product? |
| Line chart: unplanned downtime per shift worked, per line, by day / week / month | Is downtime increasing? |
| Cards: unplanned vs. planned downtime | How much downtime is a real loss? |

**Calidad de datos**

| Element | Question it answers |
|---|---|
| Coverage, missing shifts, Sunday overtime shifts (REQ-005) | Can I trust the KPIs? Is data missing? |
| Orphan downtime events (REQ-005) | Is there downtime not linked to production? |
| Load history (REQ-005) | What was loaded, when, and with what result? |

#### Display Rules

- Number format as defined in KPI Common Rules (e.g., `12,450`, `3.2%`, `1,230 min (20.5 h)`).
- Bar charts sorted from highest to lowest unless the dimension has a natural order (shift 1, 2, 3; dates).
- Charts use Plotly (interactive tooltips with the exact value).
- No chart is added without a question in the tables above.

#### Empty and Error States

- Empty database: a message explaining to load the production CSV first, then the downtime CSV.
- No data for the selected filters: a "no data for these filters" message, not an empty chart or an error.
- No alerts: a message stating that no line deviated on the evaluated day, plus the list of lines not evaluated.

### Output

A Streamlit dashboard, started with:

```text
streamlit run app.py
```

### Acceptance Criteria

```text
[ ] The dashboard starts with streamlit run app.py.
[ ] All text visible to the user is in Spanish.
[ ] Production and downtime CSVs can be uploaded from the sidebar, and the load summary and error detail are shown.
[ ] Filters (period, line, product, shift) update the KPI tabs.
[ ] Alerts are ranked, show all fields, and respond to the line filter but not to the period filter.
[ ] Every element listed in this requirement is present, and no element without a question is added.
[ ] Empty database, no data for filters, and no alerts each show a clear message instead of an error.
[ ] A non-technical user can identify the top-priority problem and where to investigate from the Resumen and Alertas tabs, without opening the raw data.
```

### Dependencies

- REQ-001 to REQ-013.

### Open Points

- **Master list values:** resolved — master lists contain the values as captured by supervisors, in Spanish (e.g., `Falla de máquina`). They are shown in the dashboard as stored.
