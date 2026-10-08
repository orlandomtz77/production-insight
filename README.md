# Production Insight

Operational analytics for production supervisors: load production, scrap and downtime data, calculate KPIs, detect abnormal behavior, and see **where to investigate first and why**.

> Status: MVP in development — Phase 2 (Data).

## Requirements

- Python 3.12+
- Git

## Setup

```bash
git clone https://github.com/orlandomtz77/production-insight.git
cd production-insight

python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Tests

```bash
python -m pytest
```

## Project Structure

```text
data/
├── master/        fixed lists: lines, products, downtime reasons
├── sample/        synthetic sample dataset (test oracle)
├── raw/           real input files (not versioned)
└── processed/     intermediate files (not versioned)
docs/
├── requirements.md      REQ-001 to REQ-014
├── sample-dataset.md    sample dataset design
├── decisions/           Architecture Decision Records (ADR)
└── architecture/
scripts/           development tools (e.g., sample data generator)
src/
├── ingestion/
├── transformation/
├── database/
├── analytics/
├── anomaly_detection/
└── dashboard/
tests/
```

## Documentation

- [Project brief](project-brief.md)
- [Requirements](docs/requirements.md)
- [Sample dataset design](docs/sample-dataset.md)
- [Architecture decisions](docs/decisions/)

## Language

Documentation and code are in English. The dashboard and alerts are in Spanish.
