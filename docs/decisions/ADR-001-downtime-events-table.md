# ADR-001: Downtime as Separate Events Linked by Product

## Status

Accepted — 2026-10-07

## Context

The initial data model in `CLAUDE.md` §10 stores `downtime_minutes` and `downtime_reason` inside the production record.

During problem definition, two facts were confirmed:

1. A shift can have multiple downtime events with different causes (machine failure, material shortage, etc.). A single `downtime_reason` per record loses information.
2. A line can run more than one product in the same shift (product changeovers). The production record is therefore one per `date + line + shift + product`.

The **Downtime by product** KPI requires knowing which product each downtime event belongs to.

## Options

1. **Keep downtime in the production record** — one total and one reason per record.
2. **Separate downtime events table linked by `date + line + shift`**, distributing downtime across products proportionally to production.
3. **Separate downtime events table linked by `date + line + shift + product`**, with the product captured per event.
4. **Separate downtime events table without product**, removing the Downtime by product KPI from the MVP.

## Decision

Option 3.

- Downtime is stored as individual events in a separate table.
- Each event records `date`, `line`, `shift`, `product`, `downtime_minutes` and `downtime_reason`.
- `downtime_reason` must belong to a controlled list: Machine failure, Material shortage, Quality issue, Setup / Changeover, Maintenance, Other.
- **Setup / Changeover** downtime is attributed to the **incoming product**.
- Total downtime is never stored in the production record; it is calculated as `SUM(downtime_minutes)`.

## Reason

- Multiple causes per shift are the real operational behavior.
- Capturing the product per event keeps every downtime figure traceable and explainable. Proportional distribution (option 2) would produce estimates that the supervisor cannot verify.
- A single source of truth for downtime avoids inconsistencies between a stored total and its events.
- A controlled list of reasons prevents inconsistent capture and makes grouping by cause reliable.

## Consequences

Positive:

- Downtime by cause and by product are exact and explainable.
- Multiple downtime events per shift are supported.
- No duplicated downtime data.

Negative:

- Two input CSV files instead of one.
- Additional validations required:
  - Each event must match a production record (`date + line + shift + product`); otherwise it is an orphan event.
  - Total downtime per `date + line + shift` (all products) must not exceed 480 minutes.
  - `downtime_reason` must be in the allowed list.
- The person capturing data must record the product for each event.
- `CLAUDE.md` §10 (Initial Data Model) must be updated to reflect this decision.
