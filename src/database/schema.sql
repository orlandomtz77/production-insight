-- Production Insight schema. Design: docs/architecture/data-model.md (ADR-004).

CREATE TABLE IF NOT EXISTS production_records (
    id                  INTEGER PRIMARY KEY,
    date                TEXT    NOT NULL,
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
    date             TEXT    NOT NULL,
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
    loaded_at       TEXT    NOT NULL,
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
