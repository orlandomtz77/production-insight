# Sample Dataset Design

> Phase 2 — Data.
> The sample dataset is the test oracle of the MVP: every injected problem has a documented expected result.

---

## 1. Purpose

- Provide realistic data to develop and demonstrate Production Insight.
- Provide **known problems** so that validation (REQ-001, REQ-002), data quality (REQ-005), detection (REQ-011) and prioritization (REQ-013) can be verified objectively.

If the system does not produce the expected results below, either the implementation or the design is wrong.

---

## 2. Generation

| Decision | Choice |
|---|---|
| Method | Python script with a fixed random seed |
| Script | `scripts/generate_sample_data.py` |
| Seed | `42` |
| Output | CSV files in `data/sample/` and master lists in `data/master/` |

- Running the script twice produces identical files.
- Injected anomalies are written explicitly in the script (not random), each with a comment referencing its ID in this document (e.g., `# A1`).
- `scripts/` is a new top-level folder (not in `CLAUDE.md` §22): the generator is a development tool, not part of the application in `src/`.

---

## 3. Period and Calendar

| Item | Value |
|---|---|
| Period | 2026-09-01 (Tuesday) to 2026-09-30 (Wednesday) |
| Working days (Mon–Sat) | 26 |
| Sundays | 6, 13, 20, 27 — no production, except overtime on the 27th |
| Evaluated day (REQ-011) | **2026-09-30** |
| Last 6 working days (REQ-013) | 24, 25, 26, 28, 29, 30 |

---

## 4. Lines and Products

### Master Lists

```text
data/master/lines.csv             L1, L2, L3
data/master/products.csv          Producto A, Producto B, Producto C, Producto D, Producto E
data/master/downtime_reasons.csv  Falla de máquina, Falta de material, Problema de calidad,
                                  Ajuste / Cambio de modelo, Mantenimiento, Otro
```

### Line Profiles (normal behavior)

| Line | Products | Rate (pieces / 480 min) | Normal scrap rate | Normal downtime / shift |
|---|---|---|---|---|
| L1 | Producto A, Producto B | ~1,400 | 2.5% ± 0.4 | 20–45 min |
| L2 | Producto B, Producto C, Producto D | ~1,100 | 3.0% ± 0.4 | 25–55 min |
| L3 | Producto D, Producto E | ~900 | 3.5% ± 0.4 | 30–60 min |

### Generation Rules (normal behavior)

- 3 shifts per working day per line.
- **Downtime first, then production:** each shift gets 1–3 downtime events; production is derived from the time available:

  ```text
  production ≈ rate × (480 − downtime_minutes) / 480 × random factor (0.95–1.05)
  ```

  This keeps production and downtime consistent, as in a real line.
- **Product changeovers:** about 1 in 5 shifts on L2 and L3 runs two products. The shift is split between them, and an `Ajuste / Cambio de modelo` event (10–20 min) is attributed to the incoming product.
- Downtime reasons, normal mix: Falla de máquina 30%, Falta de material 20%, Ajuste / Cambio de modelo 20% (only with changeovers), Mantenimiento 15%, Problema de calidad 10%, Otro 5%.
- Normal values stay inside the ranges above, so normal days do not trigger alerts.

---

## 5. Injected Anomalies

Each anomaly has an ID, used in the script and in the tests.

| ID | Where | When | What | Purpose |
|---|---|---|---|---|
| **A1** | L2, Producto C | Sep 28, 29, 30 | Scrap rate of Producto C rises to ~9% (line scrap rate ~6%) | Recurring problem on the evaluated day |
| **A2** | L1, shift 2 | Sep 30 only | One `Falla de máquina` event of 180 min | One-day problem on the evaluated day |
| **A3** | L3 | Sep 10 only | Scrap rate ~10% | Past problem: must **not** alert on Sep 30, but must be visible in the scrap trend |
| **A4** | L3 | Sep 30 | Normal behavior | Control: no alert expected |

### Expected Results on the Evaluated Day (2026-09-30)

| Line | Metric | Expected | Frequency (REQ-013) | Investigation area (REQ-012) |
|---|---|---|---|---|
| L2 | Scrap rate | **Alert** (A1) | 3 of 6 | Producto C |
| L1 | Downtime per shift | **Alert** (A2) | 1 of 6 | Falla de máquina, shift 2 |
| L1 | Production per shift | Likely alert (A2 reduces available time) | 1 of 6 | Shift 2 |
| L3 | All metrics | **No alert** (A3 is in the past, A4 is normal) | — | — |
| L1 | Scrap rate | No alert | — | — |
| L2 | Production, downtime | No alert | — | — |

- The L1 production alert, if raised, demonstrates the documented limitation "overlap between metrics" (REQ-013).

### Expected Ranking (REQ-013, ADR-003)

**A1 must rank above A2**: a recurring problem goes first.

Approximate values (design targets):

| Alert | Daily impact | Frequency | Cumulative impact | Score |
|---|---|---|---|---|
| A1 — L2 scrap | ~83 pieces | 3 | ~250 | ~750 |
| A2 — L1 downtime | ~460 pieces | 1 | ~460 | ~460 |

If the generated data does not produce this ranking, the anomaly sizes are adjusted in the script (not the formula), and the change is documented here.
- Exact values (value, mean, std, z, impact, score) are recorded in `data/sample/expected_results.md` after generation, and verified by a manual calculation.

---

## 6. Data Quality Cases

### In the Main Files (loaded without errors)

| ID | Case | Expected in REQ-005 |
|---|---|---|
| **Q1** | L3, shift 3 has no data on Sep 15 and Sep 16 | 2 missing shifts; no alert caused by them (normalization per shift worked) |
| **Q2** | Sunday Sep 27: L1 shifts 1 and 2 work overtime | 2 Sunday overtime shifts; included in KPIs; excluded from baselines |

### Separate Files for Validation Tests

| File | Contents | Expected result |
|---|---|---|
| `production_invalid.csv` | One row of each error: negative production, scrap > production, invalid date (`2026-09-31`), future date, unknown line (`L9`), shift `4`, unknown product, duplicate row | Each row rejected with its reason; valid shifts stored; shifts containing an invalid row are not stored |
| `production_missing_column.csv` | No `scrap_quantity` column | Whole file rejected, naming the missing column |
| `downtime_invalid.csv` | Orphan event (no production record), unknown reason (`Falla`), `downtime_minutes = 0`, a shift totaling 510 min | Each case rejected with its reason |
| `production_reload.csv` | Sep 29, L2, shift 1, with only one of its two products | Shift replaced; the removed product's downtime events become **orphans** in REQ-005 |

---

## 7. Output Files

```text
data/master/
├── lines.csv
├── products.csv
└── downtime_reasons.csv

data/sample/
├── production.csv                 main file, valid
├── downtime.csv                   main file, valid
├── production_invalid.csv         validation tests
├── production_missing_column.csv  validation tests
├── downtime_invalid.csv           validation tests
├── production_reload.csv          reload / orphan test
└── expected_results.md            exact expected values, recorded after generation
```

---

## 8. Acceptance Criteria

```text
[ ] Running the script twice produces identical files.
[ ] Main files load without rejected rows (REQ-001, REQ-002).
[ ] Normal values stay within the line profiles.
[ ] Total downtime per shift never exceeds 480 minutes in the main files.
[ ] Each anomaly (A1–A4) and data quality case (Q1–Q2) is present as designed.
[ ] Each invalid test file produces exactly the documented rejections.
[ ] expected_results.md is filled in and verified by manual calculation.
```
