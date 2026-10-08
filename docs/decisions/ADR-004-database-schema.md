# ADR-004: Database Schema Principles

## Status

Accepted — 2026-10-07

## Context

The MVP uses SQLite (`CLAUDE.md` §8). Before implementing ingestion, the schema must define what is stored, which rules the database enforces, and how production and downtime are related.

Previous decisions constrain the design:

- ADR-001: downtime events are linked to production records by `date + line + shift + product`.
- ADR-002: reloads replace whole shifts; orphan downtime events are kept and reported (REQ-005).
- Master lists live in `data/master/*.csv`.

## Options and Decisions

### 1. Link between downtime and production

| Option | Result |
|---|---|
| Foreign key (composite) | Replacing a production shift would be blocked, or would cascade-delete downtime events silently |
| **No foreign key; validate at load time and report orphans with a query** | **Chosen** |

Reason: ADR-002 requires orphans to be kept and reported, which a foreign key does not allow.

### 2. Master lists in the database

| Option | Result |
|---|---|
| Copy CSV to tables and enforce with foreign keys | Two copies to synchronize; removing a product from the list breaks historical data |
| **Only in CSV; validated in Python** | **Chosen** |

Reason: single source of truth; no synchronization.

### 3. Store calculated results

| Option | Result |
|---|---|
| Store KPIs, baselines and alerts | Must be recalculated after every reload; risk of outdated results |
| **Calculate on demand** | **Chosen** |

Reason: ~750 rows per month are calculated instantly; results are never outdated. Consequence: past alerts cannot be reviewed (accepted for the MVP, REQ-011).

### 4. Transactions

**One transaction per upload** (all accepted shifts + load history). This is stricter than one transaction per shift and guarantees that a failed write leaves the database unchanged.

### 5. Data types

- Dates stored as ISO text (`YYYY-MM-DD`): SQLite has no date type; ISO text sorts correctly and maps to `DATE` in PostgreSQL.
- `downtime_minutes` stored as **integer** minutes (REQ-002 updated from "number" to "integer").

### 6. Schema management

`src/database/schema.sql` with `CREATE ... IF NOT EXISTS`, applied at startup. No migration tool in the MVP.

## Consequences

Positive:

- Simple schema: 3 tables, no synchronization, no stored derived data.
- Database constraints catch single-row errors even if Python validation has a bug.
- Portable to PostgreSQL with minor type changes.

Negative:

- Rules across rows (orphans, shift total ≤ 480) and master list membership depend only on Python validation; they must be covered by tests.
- No history of past alerts.
- Schema changes after real data exists will need a manual migration.
