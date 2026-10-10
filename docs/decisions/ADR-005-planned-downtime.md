# ADR-005: Planned Downtime and Planned Stops

## Status

Accepted — 2026-10-08

## Context

The production supervisor identified two situations that the current design treats as problems, although they are planned:

1. **A line does not run on a working day or shift** (e.g., holiday, no production plan). REQ-005 reports it as missing data.
2. **Planned downtime inside a worked shift** (e.g., preventive maintenance, meetings, cleaning). REQ-009 counts it as downtime, and REQ-010 to REQ-013 may raise alerts and count "lost pieces" that were never meant to be produced.

## Options

**Days or shifts not running:**

1. **Planned stops calendar file** (`date, line, shift, reason`) maintained by the supervisor.
2. Production record with 0 units + a 480-minute downtime event "Paro programado".

**Planned downtime inside a shift:**

1. **Classify downtime reasons as planned / unplanned** in the master list.
2. Treat all downtime the same.

## Decision

### 1. Planned stops calendar

`data/master/planned_stops.csv`, maintained manually:

| Column | Rule |
|---|---|
| date | `YYYY-MM-DD` |
| line | Must exist in `lines.csv` |
| shift | 1, 2, 3, or **empty = all shifts of that day** |
| reason | Free text, informative (e.g., `Día festivo`, `Sin programa`) |

- The file is **optional**: if it does not exist, there are no planned stops.
- Invalid rows are ignored and listed in the data quality report (they do not block uploads).
- A planned stop shift is **not expected** in coverage (REQ-005).
- If a planned stop shift has data anyway, it is accepted and listed as an extra shift (like Sunday overtime).
- Baselines need no change: a day or shift without data is not part of the daily values, and metrics are normalized per shift worked.

### 2. Planned / unplanned downtime reasons

`downtime_reasons.csv` gets a second column, `planned` (`sí` / `no`):

| downtime_reason | planned |
|---|---|
| Falla de máquina | no |
| Falta de material | no |
| Problema de calidad | no |
| Ajuste / Cambio de modelo | no |
| Mantenimiento | **sí** |
| Paro programado | **sí** (new: meetings, cleaning, training) |
| Otro | no |

- `Mantenimiento` means **preventive** maintenance. Corrective maintenance is captured as `Falla de máquina`.
- `Ajuste / Cambio de modelo` is **unplanned** (a loss to reduce), following common OEE practice.

Effects:

| Area | Rule |
|---|---|
| Shift total ≤ 480 min (REQ-002) | Planned + unplanned |
| Downtime KPIs (REQ-009) | Unplanned and planned shown **separately**; averages and charts use unplanned by default |
| Downtime metric for alerts (REQ-010, REQ-011) | **Unplanned** minutes only |
| Production metric for alerts (REQ-010, REQ-011) | **Production per available shift**: planned downtime does not count as lost time |
| Impact in pieces (REQ-013) | Based on unplanned downtime and available time |

```text
available shifts             = (shifts_worked × 480 − planned_minutes) / 480
production per available shift = SUM(production_quantity) / available shifts
downtime per shift (unplanned) = SUM(unplanned minutes) / shifts_worked
```

## Reason

- A planned stop is not a problem to investigate; alerting on it would reduce trust in the alerts.
- A calendar file keeps production records clean (no artificial zero-production records) and is simple to maintain.
- Classifying reasons in the master list keeps the rule in one place: adding a new planned reason requires no code change.

## Consequences

Positive:

- No false gaps for planned non-working days.
- No false alerts or "lost pieces" caused by planned downtime.
- Supervisors see planned and unplanned downtime separately.

Negative:

- One more file to maintain (`planned_stops.csv`).
- Master list `downtime_reasons.csv` changes format (second column); the master list loader and REQ-002 validation must read it.
- The production metric becomes "per available shift", slightly harder to explain than "per shift".
- Sample data expected results must be recalculated (`Mantenimiento` events become planned).
