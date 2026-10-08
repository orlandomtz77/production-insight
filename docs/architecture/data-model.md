# Data Model — SQLite

> Phase 2 — Data. Decisions: `docs/decisions/ADR-004-database-schema.md`.

---

## 1. Principles

- The database stores **only input data** and the load history. KPIs, baselines, deviations, alerts and priority scores are calculated on demand (single source of truth; nothing becomes outdated after a reload).
- **Python validation is the main gate** (REQ-001, REQ-002). Database constraints are a safety net for rules that can be checked on a single row.
- Master lists (lines, products, downtime reasons) live **only** in `data/master/*.csv`. They are not copied into the database.
- Standard SQL where possible, to allow a future migration to PostgreSQL.

---

## 2. Tables

```text
production_records          downtime_events               load_history
──────────────────          ───────────────               ────────────
id               PK         id               PK           id               PK
date                        date                          loaded_at
line                        line                          file_type
shift                       shift                         file_name
product                     product                       rows_read
production_quantity         downtime_minutes              rows_stored
scrap_quantity              downtime_reason               rows_rejected
                                                          shifts_replaced
UNIQUE(date, line,                                        shifts_new
       shift, product)                                    shifts_rejected
                                                          warnings
         ▲                                                status
         │ logical link: date + line + shift + product
         │ (no foreign key — orphans are allowed and reported, REQ-005)
         └──────────── downtime_events
```

---

## 3. Schema

```sql
CREATE TABLE IF NOT EXISTS production_records (
    id                  INTEGER PRIMARY KEY,
    date                TEXT    NOT NULL,          -- ISO 'YYYY-MM-DD'
    line                TEXT    NOT NULL,
    shift               INTEGER NOT NULL CHECK (shift IN (1, 2, 3)),
    product             TEXT    NOT NULL,
    production_quantity INTEGER NOT NULL CHECK (production_quantity >= 0),
    scrap_quantity      INTEGER NOT NULL CHECK (scrap_quantity >= 0
                                                AND scrap_quantity <= production_quantity),
    UNIQUE (date, line, shift, product)
);

CREATE TABLE IF NOT EXISTS downtime_events (
    id               INTEGER PRIMARY KEY,
    date             TEXT    NOT NULL,             -- ISO 'YYYY-MM-DD'
    line             TEXT    NOT NULL,
    shift            INTEGER NOT NULL CHECK (shift IN (1, 2, 3)),
    product          TEXT    NOT NULL,
    downtime_minutes INTEGER NOT NULL CHECK (downtime_minutes > 0
                                             AND downtime_minutes <= 480),
    downtime_reason  TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_downtime_events_shift
    ON downtime_events (date, line, shift);

CREATE TABLE IF NOT EXISTS load_history (
    id              INTEGER PRIMARY KEY,
    loaded_at       TEXT    NOT NULL,              -- ISO 'YYYY-MM-DD HH:MM:SS'
    file_type       TEXT    NOT NULL CHECK (file_type IN ('production', 'downtime')),
    file_name       TEXT    NOT NULL,
    rows_read       INTEGER NOT NULL,
    rows_stored     INTEGER NOT NULL,
    rows_rejected   INTEGER NOT NULL,
    shifts_replaced INTEGER NOT NULL,
    shifts_new      INTEGER NOT NULL,
    shifts_rejected INTEGER NOT NULL,
    warnings        INTEGER NOT NULL,
    status          TEXT    NOT NULL CHECK (status IN ('completed', 'rejected'))
);
```

The schema is stored in `src/database/schema.sql` and applied with `CREATE ... IF NOT EXISTS` when the application starts. No migration tool is used in the MVP.

---

## 4. Where Each Rule Is Enforced

| Rule | Python validation | Database |
|---|---|---|
| Required fields | ✔ | `NOT NULL` |
| Valid date, not in the future | ✔ | — |
| Shift 1, 2, 3 | ✔ | `CHECK` |
| Quantities ≥ 0, scrap ≤ production | ✔ | `CHECK` |
| Downtime minutes > 0 and ≤ 480 per event | ✔ | `CHECK` |
| Line / product / reason in master lists | ✔ | — (master lists only in CSV) |
| No duplicate production record | ✔ | `UNIQUE` |
| Downtime event matches a production record | ✔ (at load time) | — (orphans allowed after reload) |
| Shift total downtime ≤ 480 min | ✔ | — (rule across rows) |

---

## 5. Writing Data (Replacement by Shift)

One upload = **one transaction**:

```sql
BEGIN;
-- for each accepted shift in the file:
DELETE FROM production_records
 WHERE date = :date AND line = :line AND shift = :shift;
INSERT INTO production_records (...) VALUES (...);   -- rows of that shift
-- ...
INSERT INTO load_history (...) VALUES (...);
COMMIT;
```

- If anything fails, the transaction is rolled back: no shift is partially replaced and no load history is written for a failed write.
- Downtime uploads follow the same pattern on `downtime_events`.
- Replacing production shifts **does not** delete downtime events (orphans are reported, REQ-005).

---

## 6. Reading Data

- `shifts worked`, totals per shift and orphans are obtained with SQL queries (`GROUP BY`, `LEFT JOIN`).
- KPIs and detection load the needed rows into pandas and calculate there.

Example — orphan downtime events:

```sql
SELECT d.*
  FROM downtime_events d
  LEFT JOIN production_records p
    ON p.date = d.date AND p.line = d.line
   AND p.shift = d.shift AND p.product = d.product
 WHERE p.id IS NULL;
```

---

## 7. Location

`data/production_insight.db` — not versioned (`*.db` in `.gitignore`). It can be deleted and rebuilt by loading the CSV files again.

---

## 8. PostgreSQL Migration Notes

| SQLite | PostgreSQL |
|---|---|
| `INTEGER PRIMARY KEY` | `INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY` |
| `TEXT` date (ISO) | `DATE` |
| `TEXT` datetime (ISO) | `TIMESTAMP` |

All other statements are standard SQL.
