"""Generate the synthetic sample dataset for Production Insight.

Design: docs/sample-dataset.md
Each injected anomaly or data quality case is marked with its ID (A1, A2, A3, Q1, Q2).

Usage:
    python scripts/generate_sample_data.py
"""

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = PROJECT_ROOT / "data" / "sample"
MASTER_DIR = PROJECT_ROOT / "data" / "master"

PERIOD_START = date(2026, 9, 1)
PERIOD_END = date(2026, 9, 30)
SHIFTS = (1, 2, 3)
SHIFT_MINUTES = 480
SUNDAY = 6  # date.weekday()

PRODUCTS = ["Producto A", "Producto B", "Producto C", "Producto D", "Producto E"]

CHANGEOVER = "Ajuste / Cambio de modelo"
MACHINE_FAILURE = "Falla de máquina"
DOWNTIME_REASONS = [
    MACHINE_FAILURE,
    "Falta de material",
    "Problema de calidad",
    CHANGEOVER,
    "Mantenimiento",
    "Otro",
]

# Normal mix of downtime reasons. Changeover events are only created when a shift
# runs two products, so they are not part of the random mix.
NORMAL_REASONS = [MACHINE_FAILURE, "Falta de material", "Mantenimiento", "Problema de calidad", "Otro"]
NORMAL_REASON_WEIGHTS = np.array([30, 20, 15, 10, 5]) / 80

# Normal behavior per line (docs/sample-dataset.md, section 4).
LINE_PROFILES = {
    "L1": {
        "products": ["Producto A", "Producto B"],
        "rate_per_shift": 1400,
        "scrap_mean": 0.025,
        "downtime_range": (20, 45),
        "changeover_probability": 0.0,
    },
    "L2": {
        "products": ["Producto B", "Producto C", "Producto D"],
        "rate_per_shift": 1100,
        "scrap_mean": 0.030,
        "downtime_range": (25, 55),
        "changeover_probability": 0.2,
    },
    "L3": {
        "products": ["Producto D", "Producto E"],
        "rate_per_shift": 900,
        "scrap_mean": 0.035,
        "downtime_range": (30, 60),
        "changeover_probability": 0.2,
    },
}
SCRAP_STD = 0.004
MIN_EVENT_MINUTES = 5

ALL_PRODUCTS = "*"  # key for scrap overrides that apply to every product of a shift

# --- Injected anomalies and data quality cases ------------------------------

A1_DAYS = [date(2026, 9, 28), date(2026, 9, 29), date(2026, 9, 30)]
A2_DAY = date(2026, 9, 30)
A3_DAY = date(2026, 9, 10)
Q1_MISSING = {(date(2026, 9, 15), "L3", 3), (date(2026, 9, 16), "L3", 3)}
Q2_SUNDAY = date(2026, 9, 27)
Q2_SHIFTS = {("L1", 1), ("L1", 2)}
RELOAD_SHIFT = (date(2026, 9, 29), "L3", 1)

# Products forced for a shift: (date, line, shift) -> products
FORCED_PRODUCTS = {
    # A1: L2 runs Producto C in shifts 1 and 2 on the last three working days.
    **{(day, "L2", shift): ["Producto C"] for day in A1_DAYS for shift in (1, 2)},
    # Reload test: a shift with two products, so one can be removed later.
    RELOAD_SHIFT: ["Producto D", "Producto E"],
}

# Scrap rates forced for a shift: (date, line, shift) -> {product: rate}
SCRAP_OVERRIDES = {
    # A1: Producto C scrap rises to ~9% on L2.
    **{(day, "L2", shift): {"Producto C": 0.09} for day in A1_DAYS for shift in (1, 2)},
    # A3: L3 scrap ~10% on a past day.
    **{(A3_DAY, "L3", shift): {ALL_PRODUCTS: 0.10} for shift in SHIFTS},
}

# Extra downtime events: (date, line, shift) -> [(minutes, reason)]
EXTRA_EVENTS = {
    # A2: one long machine failure on L1, shift 2, evaluated day only.
    (A2_DAY, "L1", 2): [(180, MACHINE_FAILURE)],
}


def working_schedule():
    """Yield every (date, line, shift) that has production in the main files."""
    day = PERIOD_START
    while day <= PERIOD_END:
        for line in LINE_PROFILES:
            for shift in SHIFTS:
                key = (day, line, shift)
                if day.weekday() == SUNDAY:
                    # Q2: Sunday is only worked as overtime.
                    if day == Q2_SUNDAY and (line, shift) in Q2_SHIFTS:
                        yield key
                    continue
                if key in Q1_MISSING:  # Q1: coverage gaps
                    continue
                yield key
        day += timedelta(days=1)


def choose_products(rng, key, profile):
    if key in FORCED_PRODUCTS:
        return FORCED_PRODUCTS[key]
    if rng.random() < profile["changeover_probability"]:
        return list(rng.choice(profile["products"], size=2, replace=False))
    return [str(rng.choice(profile["products"]))]


def split_minutes(rng, total, max_events=3):
    """Split total minutes into 1..max_events parts of at least MIN_EVENT_MINUTES."""
    events = int(rng.integers(1, max_events + 1))
    events = max(1, min(events, total // MIN_EVENT_MINUTES))
    free = total - MIN_EVENT_MINUTES * events
    weights = rng.dirichlet(np.ones(events))
    parts = [MIN_EVENT_MINUTES + int(round(w * free)) for w in weights]
    parts[-1] = total - sum(parts[:-1])
    return parts


def generate_shift(rng, key):
    """Generate production rows and downtime events for one shift.

    Downtime is generated first; production is derived from the time left,
    so a shift with more downtime produces less (docs/sample-dataset.md, section 4).
    """
    day, line, shift = key
    profile = LINE_PROFILES[line]
    products = choose_products(rng, key, profile)

    low, high = profile["downtime_range"]
    target_downtime = int(rng.integers(low, high + 1))

    events = []
    if len(products) == 2:
        # Changeover downtime is attributed to the incoming product (ADR-001).
        setup_minutes = int(rng.integers(10, 21))
        events.append((products[1], setup_minutes, CHANGEOVER))
        target_downtime -= setup_minutes

    for minutes in split_minutes(rng, target_downtime):
        reason = str(rng.choice(NORMAL_REASONS, p=NORMAL_REASON_WEIGHTS))
        product = str(rng.choice(products))
        events.append((product, minutes, reason))

    for minutes, reason in EXTRA_EVENTS.get(key, []):
        events.append((products[0], minutes, reason))

    total_downtime = sum(minutes for _, minutes, _ in events)
    available_minutes = SHIFT_MINUTES - total_downtime
    total_production = (
        profile["rate_per_shift"] * available_minutes / SHIFT_MINUTES * rng.uniform(0.95, 1.05)
    )

    if len(products) == 2:
        first_share = rng.uniform(0.3, 0.7)
        quantities = [total_production * first_share, total_production * (1 - first_share)]
    else:
        quantities = [total_production]

    overrides = SCRAP_OVERRIDES.get(key, {})
    production_rows = []
    for product, quantity in zip(products, quantities):
        normal_rate = max(0.005, rng.normal(profile["scrap_mean"], SCRAP_STD))
        scrap_rate = overrides.get(product, overrides.get(ALL_PRODUCTS, normal_rate))
        quantity = int(round(quantity))
        production_rows.append(
            {
                "date": day.isoformat(),
                "line": line,
                "shift": shift,
                "product": product,
                "production_quantity": quantity,
                "scrap_quantity": int(round(quantity * scrap_rate)),
            }
        )

    downtime_rows = [
        {
            "date": day.isoformat(),
            "line": line,
            "shift": shift,
            "product": product,
            "downtime_minutes": minutes,
            "downtime_reason": reason,
        }
        for product, minutes, reason in events
    ]
    return production_rows, downtime_rows


def generate_main_files(rng):
    production_rows, downtime_rows = [], []
    for key in working_schedule():
        shift_production, shift_downtime = generate_shift(rng, key)
        production_rows.extend(shift_production)
        downtime_rows.extend(shift_downtime)
    return pd.DataFrame(production_rows), pd.DataFrame(downtime_rows)


def product_of(production, day, line, shift):
    """First product produced in a shift of the main production file."""
    match = production[
        (production["date"] == day) & (production["line"] == line) & (production["shift"] == shift)
    ]
    return match["product"].iloc[0]


def build_production_invalid():
    """One row per validation error (docs/sample-dataset.md, section 6)."""
    columns = ["date", "line", "shift", "product", "production_quantity", "scrap_quantity"]
    rows = [
        ("2026-09-02", "L1", 1, "Producto A", 1300, 30),   # valid
        ("2026-09-02", "L1", 2, "Producto A", -5, 0),      # negative production
        ("2026-09-02", "L1", 2, "Producto B", 600, 20),    # valid, but its shift has an invalid row
        ("2026-09-02", "L1", 3, "Producto A", 100, 150),   # scrap > production
        ("2026-09-31", "L2", 1, "Producto B", 1000, 30),   # invalid date
        ("2030-01-01", "L2", 1, "Producto B", 1000, 30),   # future date
        ("2026-09-02", "L9", 1, "Producto A", 1000, 30),   # unknown line
        ("2026-09-02", "L2", 4, "Producto B", 1000, 30),   # invalid shift
        ("2026-09-02", "L2", 2, "Producto Z", 1000, 30),   # unknown product
        ("2026-09-02", "L3", 1, "Producto D", 900, 30),    # duplicate
        ("2026-09-02", "L3", 1, "Producto D", 900, 30),    # duplicate
        ("2026-09-02", "L3", 2, "Producto E", 850, 25),    # valid
    ]
    return pd.DataFrame(rows, columns=columns)


def build_downtime_invalid(production):
    """One shift per downtime error. Requires the main production file to be loaded."""
    columns = ["date", "line", "shift", "product", "downtime_minutes", "downtime_reason"]
    rows = [
        # Orphan: Producto E never runs on L1.
        ("2026-09-03", "L1", 1, "Producto E", 15, MACHINE_FAILURE),
        # Unknown reason.
        ("2026-09-03", "L2", 1, product_of(production, "2026-09-03", "L2", 1), 15, "Falla"),
        # Zero minutes.
        ("2026-09-03", "L3", 1, product_of(production, "2026-09-03", "L3", 1), 0, "Otro"),
        # Shift total 510 min > 480.
        ("2026-09-04", "L1", 1, product_of(production, "2026-09-04", "L1", 1), 300, MACHINE_FAILURE),
        ("2026-09-04", "L1", 1, product_of(production, "2026-09-04", "L1", 1), 210, MACHINE_FAILURE),
        # Valid: replaces the existing events of this shift.
        ("2026-09-04", "L2", 1, product_of(production, "2026-09-04", "L2", 1), 25, "Mantenimiento"),
    ]
    return pd.DataFrame(rows, columns=columns)


def build_production_reload(production):
    """The reload shift with only its first product: the second product's downtime becomes orphan."""
    day, line, shift = RELOAD_SHIFT
    shift_rows = production[
        (production["date"] == day.isoformat())
        & (production["line"] == line)
        & (production["shift"] == shift)
    ]
    return shift_rows.head(1)


def write_csv(df, path):
    df.to_csv(path, index=False, encoding="utf-8", lineterminator="\n")
    print(f"  {path.relative_to(PROJECT_ROOT)}  ({len(df)} rows)")


def main():
    rng = np.random.default_rng(SEED)
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    MASTER_DIR.mkdir(parents=True, exist_ok=True)

    print("Master lists:")
    write_csv(pd.DataFrame({"line": list(LINE_PROFILES)}), MASTER_DIR / "lines.csv")
    write_csv(pd.DataFrame({"product": PRODUCTS}), MASTER_DIR / "products.csv")
    write_csv(pd.DataFrame({"downtime_reason": DOWNTIME_REASONS}), MASTER_DIR / "downtime_reasons.csv")

    production, downtime = generate_main_files(rng)

    print("Sample files:")
    write_csv(production, SAMPLE_DIR / "production.csv")
    write_csv(downtime, SAMPLE_DIR / "downtime.csv")
    write_csv(build_production_invalid(), SAMPLE_DIR / "production_invalid.csv")
    write_csv(
        production.drop(columns=["scrap_quantity"]).head(3),
        SAMPLE_DIR / "production_missing_column.csv",
    )
    write_csv(build_downtime_invalid(production), SAMPLE_DIR / "downtime_invalid.csv")
    write_csv(build_production_reload(production), SAMPLE_DIR / "production_reload.csv")


if __name__ == "__main__":
    main()
