# ADR-003: Priority Score Formula

## Status

Accepted — 2026-10-07

## Context

`CLAUDE.md` §13 proposed an initial model:

```text
Priority Score = Impact × Deviation × Frequency
```

While designing the sample dataset, two injected anomalies were evaluated with this formula (approximate values):

| | A1: L2 scrap, 3 days | A2: L1 downtime, 1 day |
|---|---|---|
| Impact on evaluated day | ~83 pieces | ~460 pieces |
| Deviation (\|z\|) | ~3.2 | ~11.7 |
| Frequency | 3 | 1 |
| Score | ~800 | ~5,400 |

The one-day problem ranked first. The business criterion (production supervisor) is the opposite: **a recurring problem should be investigated first**, because a one-day failure has often already been addressed, while a recurring problem is still active.

Causes:

1. Deviation is counted twice: impact already grows with the deviation, and `|z|` multiplies it again.
2. A recurring problem enters its own baseline, which lowers its `|z|`.
3. Frequency (1–6) has little weight compared with `|z|` (which can exceed 10).

## Options

1. Keep `Impact × Deviation × Frequency`.
2. Always rank recurring alerts (2+ days) above isolated ones; then by impact.
3. `Cumulative Impact × Frequency`, without deviation.

## Decision

Option 3.

```text
Priority Score    = Cumulative Impact × Frequency
Cumulative Impact = SUM(daily lost pieces) over the days beyond the threshold
                    in the last 6 working days
```

Deviation remains the **trigger** of an alert (REQ-011) and is shown to the user, but it is not part of the ranking.

## Reason

- Reflects the business criterion: A1 ≈ 250 × 3 = 750 ranks above A2 ≈ 460 × 1 = 460.
- Removes the double counting of deviation.
- Keeps a single, continuous score: a very large one-day problem (e.g., 1,000 pieces) can still rank above a small recurring one. Option 2 would never allow that.
- Easy to explain: "pieces lost this week × days it happened".

## Consequences

Positive:

- Recurring problems rank higher, as expected by supervisors.
- The score depends on pieces and days, both understandable on the shop floor.

Negative:

- Frequency weighs twice (in cumulative impact and as a multiplier). This is intentional.
- `CLAUDE.md` §13 and the project brief must reference this ADR.
- The ranking must be validated with the generated sample dataset; exact values will be recorded in `data/sample/expected_results.md`.
