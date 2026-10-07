# Project Brief — Production Insight

> **Phase 1 — Problem Definition**
>
> This document defines the business problem, users, scope, assumptions, inputs, outputs, and success criteria for the Production Insight MVP.
>
> Items explicitly marked as **(to validate)** are assumptions that may require revision as the project evolves.

---

## 1. Problem

Operational data such as production, scrap, and downtime already exists, but it is often distributed across Excel files, CSV exports, reports, and ERP extracts.

Production supervisors spend time consolidating this information and calculating KPIs manually. As a result, they may still be unable to quickly answer the most important operational question:

> **Where should I investigate first, and why?**

The problem is not the lack of data.

The problem is turning operational data into actionable answers.

Production Insight aims to provide a simple and explainable way to transform operational records into:

```text
Data → Information → Decision
```

---

# 2. Target User

## Primary User

**Production Supervisor**

The primary user is responsible for monitoring production performance and identifying operational issues that require investigation.

## Secondary Users

- Production Coordinators
- Process Engineers
- Business Analysts
- Operations Managers

## User Profile

Users are expected to have:

- Strong operational and process knowledge
- Familiarity with production KPIs
- Limited technical knowledge
- Limited time available for data analysis

## User Experience Implications

The application must:

- Present results clearly.
- Minimize the amount of manual analysis required.
- Make important deviations immediately visible.
- Explain every alert.
- Avoid black-box recommendations.
- Require no technical knowledge to interpret the dashboard.

---

# 3. Current Situation

**(to validate)**

The current operational analysis process is assumed to have the following characteristics:

- Data is stored in separate spreadsheets and system exports.
- Production, scrap, and downtime KPIs are calculated manually or independently by different users.
- KPI definitions may not be consistently documented.
- Deviations are often identified through manual analysis, experience, or intuition.
- There is no consistent method for prioritizing which problem should be investigated first.
- Investigation may begin with the most visible problem rather than the problem with the greatest potential impact.

These assumptions will be validated through the project and may be revised.

---

# 4. Desired Outcome

After loading the required data, a user should be able to understand the operational situation within minutes.

The application should provide:

1. Production KPIs by line, product, and shift.
2. Quality KPIs by line, product, and shift.
3. Downtime KPIs by line, product, shift, and cause.
4. Explained alerts identifying significant deviations.
5. A ranked list of problems to support investigation prioritization.

The intended user journey is:

```text
Raw Data
   ↓
Validated Data
   ↓
KPIs
   ↓
Deviations
   ↓
Prioritized Problems
   ↓
Investigation
```

Production Insight does **not** automatically determine the root cause of a problem.

Its purpose is to help the user determine **where to investigate first**.

---

# 5. Inputs

The MVP will use two CSV files.

## 5.1 Production Records

One record per:

```text
date + line + shift + product
```

### Fields

| Field | Type | Description |
|---|---|---|
| date | date | Production date |
| line | text | Production line identifier |
| shift | integer | Shift number (1, 2, or 3) |
| product | text | Product produced |
| production_quantity | integer | Total units of this product processed/produced during the shift |
| scrap_quantity | integer | Units of this product classified as scrap |

### MVP Business Rule

> **One production record represents one product produced on one line during one shift.**

Product changeovers within a shift **are in scope**: if a line runs two products in the same shift, there are two production records.

Example:

```text
date        line  shift  product    production  scrap
2026-10-01  L1    1      Product A  600         20
2026-10-01  L1    1      Product B  550         31
```

Therefore:

```text
date + line + shift → one or more products
date + line + shift + product → unique record
```

---

# 6. Downtime Events

Downtime will be represented as individual events rather than a total stored in the production record.

There may be zero or multiple downtime events for each:

```text
date + line + shift
```

### Fields

| Field | Type | Description |
|---|---|---|
| date | date | Date of the downtime event |
| line | text | Production line |
| shift | integer | Shift number |
| product | text | Product running when the downtime occurred |
| downtime_minutes | number | Duration of the downtime event in minutes |
| downtime_reason | text | Reason for the downtime (from a controlled list) |

`downtime_reason` must come from a **controlled category list**. Free text is not allowed, to prevent inconsistent capture (e.g., "machine failure" vs. "failed machine" counted as different causes). Any value outside the list is an invalid record.

Allowed categories:

- Machine failure
- Material shortage
- Quality issue
- Setup / Changeover
- Maintenance
- Other

Downtime events are linked to production records through:

```text
date + line + shift + product
```

### Product Attribution Rule

Each downtime event records the product that was running when the downtime occurred.

For **Setup / Changeover** events, the downtime is attributed to the **incoming product** (the product being set up).

See `docs/decisions/ADR-001-downtime-events-table.md`.

Total downtime for a production record is calculated as:

```text
Total Downtime =
SUM(downtime_minutes)
```

Downtime is intentionally not stored in the production record to maintain a **single source of truth**.

The 480-minute limit applies to the sum of all downtime events for the same `date + line + shift`, across all products.

---

# 7. Historical Data

The MVP will use:

> **One month of historical data.**

The initial dataset will be synthetic and stored under:

```text
data/sample/
```

The dataset must include:

- Normal operational behavior
- Realistic variation
- Data quality issues
- Known anomalies
- Multiple production lines
- Multiple products
- Three shifts
- Multiple downtime causes

Known anomalies will be intentionally injected so that detection logic can be objectively tested.

---

# 8. Data Definitions

The following definitions apply to the MVP.

## Production Quantity

`production_quantity` represents the total number of units processed during the production record.

This quantity includes units that may later be classified as scrap.

## Scrap Quantity

`scrap_quantity` represents the number of units classified as scrap.

The MVP assumes:

```text
scrap_quantity <= production_quantity
```

## Scrap Rate

```text
scrap_rate =
scrap_quantity / production_quantity
```

Example:

```text
Production = 1,000 units
Scrap = 50 units

Scrap Rate = 50 / 1,000 = 5%
```

## Downtime

Downtime represents the total number of minutes during which the production line was unavailable or stopped according to the recorded downtime events.

---

# 9. Outputs

The system will produce the following outputs.

## 9.1 Validated Records

Valid records will be stored in SQLite.

Invalid records will not be silently discarded.

---

## 9.2 Data Quality Summary

The application must identify invalid records and explain why they were rejected.

Examples:

```text
Missing required field
Invalid date
Invalid shift
Negative production quantity
Scrap greater than production
Downtime greater than allowed shift duration
Orphan downtime event (no production record with the same date + line + shift + product)
Invalid downtime reason (not in the controlled list)
Duplicate production record (same date + line + shift + product)
```

---

## 9.3 Production KPIs

The system must calculate:

- Total production
- Average production
- Production by line
- Production by product
- Production by shift

---

## 9.4 Quality KPIs

The system must calculate:

- Total scrap quantity
- Scrap rate
- Scrap by line
- Scrap by product
- Scrap by shift

---

## 9.5 Downtime KPIs

The system must calculate:

- Total downtime
- Average downtime
- Downtime by line
- Downtime by product
- Downtime by shift
- Downtime by cause

---

# 10. Alerts

The application must identify significant deviations from an established baseline.

The initial MVP will use simple and explainable statistical methods.

Potential methods include:

- Historical average
- Standard deviation
- Percentage change
- Baseline comparison
- Frequency analysis

Each alert must include:

```text
Problem
Current Value
Baseline
Deviation
Sample Size
Explanation
```

Example:

```text
Problem:
High scrap rate on Line L2

Current Value:
8.7%

Baseline:
3.2%

Deviation:
+171.8%

Sample Size:
12 production records

Explanation:
Scrap rate is significantly above the historical baseline for this line.
```

The system should not present an alert without explaining the comparison used.

---

# 11. Baseline

Because the MVP contains only one month of historical data, baselines must be interpreted carefully.

The MVP should prefer simple baselines such as:

- Mean
- Standard deviation
- Historical average
- Relevant comparison groups

The application must display the sample size when appropriate.

Month-over-month trend analysis is out of scope for the MVP because the available historical period is insufficient.

Future versions may introduce longer historical periods and more sophisticated baselines.

---

# 12. Problem Prioritization

The system should provide a ranked list of problems to help determine where an investigation should begin.

The initial conceptual model is:

```text
Priority Score =
Impact × Deviation × Frequency
```

However, the exact definitions of these components must be established before implementation.

## Impact

**(to define before coding)**

Potential candidates include:

- Production loss
- Scrap quantity
- Downtime minutes
- Estimated operational impact

## Deviation

Measures how far the current value is from the established baseline.

## Frequency

Measures how often the identified problem occurs within the available historical period.

The Priority Score is a **decision-support mechanism**.

It must not be presented as an objective or absolute measure of business importance.

---

# 13. MVP Scope

The MVP includes:

1. CSV file ingestion
2. Production data validation
3. Downtime data validation
4. Data quality reporting
5. Data cleaning
6. Data transformation
7. SQLite database storage
8. KPI calculation
9. Baseline calculation
10. Deviation detection
11. Explainable alerts
12. Problem prioritization
13. Streamlit dashboard
14. Basic testing
15. Basic documentation

---

# 14. Out of Scope

The following features are explicitly excluded from the MVP:

- Authentication
- Authorization
- Multi-user management
- Mobile application
- Generative AI
- Machine learning
- Microservices
- Kubernetes
- Cloud infrastructure
- Automated notifications
- Direct SAP integration
- Direct integration with production systems
- Real-time production monitoring
- Root-cause analysis automation
- Blockchain
- Complex forecasting
- Complex architecture

The governing rule is:

> **Do not build complexity before demonstrating value.**

---

# 15. Success Criteria

The MVP will be considered successful when all of the following conditions are met:

### Data ingestion

1. A user can load the production CSV.
2. A user can load the downtime CSV.
3. The system validates both files.
4. Invalid records are identified with a clear reason.
5. Valid records are stored in SQLite.

### Analytics

6. KPI calculations match independently verified manual calculations on the sample dataset.
7. Production, quality, and downtime KPIs are available by the required dimensions.
8. Known anomalies intentionally injected into the dataset are detected.

### Alerts

9. Every alert identifies:
   - What happened
   - Current value
   - Baseline
   - Deviation
   - Sample size
   - Why it matters

### Prioritization

10. The dashboard provides a ranked list of problems.
11. A user can identify the highest-priority problem without opening the raw data.

### Usability

12. A non-technical user can interpret the dashboard without reading the source code.
13. The dashboard does not require manual calculations to understand the main operational situation.

---

# 16. Assumptions

## Confirmed for the MVP

- There are three shifts.
- Each shift represents up to 480 minutes of scheduled production time.
- A production record represents one date + line + shift + product combination.
- A line may run more than one product in the same shift (product changeovers are in scope).
- A shift may contain multiple downtime events.
- Downtime reasons come from a controlled category list: Machine failure, Material shortage, Quality issue, Setup / Changeover, Maintenance, Other.
- Each downtime event records the product running when it occurred.
- Setup / Changeover downtime is attributed to the incoming product.
- Lines and products come from fixed master lists (`data/master/`).
- Downtime is calculated from individual downtime events.
- Total downtime for a date + line + shift must not exceed 480 minutes.
- The initial dataset covers one month.
- The initial dataset is synthetic.
- The dataset will contain intentionally injected anomalies.

## To Validate

- Production and scrap quantities are measured in units/pieces.
- Scrap quantity cannot exceed production quantity.
- The synthetic dataset can reasonably represent operational behavior.
- The application will initially be used locally by a single user.
- The selected KPIs accurately represent the initial business problem.

---

# 17. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Inconsistent data | High | High | Data validation and quality reporting |
| Scope creep | High | High | Maintain explicit MVP scope |
| Incorrect KPI definitions | Medium | High | Define and document formulas before implementation |
| Overly complex dashboard | Medium | Medium | Every visualization must answer a business question |
| Overengineering | High | High | KISS; require justification for new architectural layers |
| Unrealistic synthetic data | Medium | High | Use realistic operational ranges and inject known anomalies |
| Excessive false-positive alerts | Medium | Medium | Tune thresholds and expose baseline/deviation |
| Priority score interpreted as absolute truth | Medium | Medium | Document limitations and present it as decision support |
| Short historical period | Medium | Medium | Use simple baselines and display sample size |
| Orphan downtime events | Medium | Medium | Validate date + line + shift relationships |
| Duplicate production records | Medium | High | Enforce uniqueness for date + line + shift + product |
| Downtime incorrectly attributed to a product | Medium | Medium | Product captured per event; changeover rule documented in ADR-001; orphan events reported |
| Invalid downtime duration | Medium | High | Validate values and shift duration constraints |
| Poorly defined problem impact | Medium | High | Define Priority Score components before implementation |

---

# 18. Initial Technical Direction

The MVP will initially use:

```text
Python
Pandas
SQLite
SQL
Streamlit
Matplotlib / Plotly
Git
```

The initial architecture is:

```text
CSV Files
    │
    ▼
Ingestion
    │
    ▼
Validation
    │
    ▼
Transformation
    │
    ▼
SQLite
    │
    ├───────────────┐
    ▼               ▼
KPI Engine    Anomaly Detection
    │               │
    └───────┬───────┘
            ▼
     Prioritization
            │
            ▼
       Streamlit
            │
            ▼
        Dashboard
```

The architecture should remain intentionally simple until a demonstrated requirement justifies additional complexity.

---

# 19. Project Principles

Production Insight follows these principles:

### 1. Problem First

Understand the problem before designing the solution.

### 2. Evidence Over Assumptions

Clearly distinguish confirmed facts from assumptions.

### 3. Explainability

Users must understand why the system generated a result.

### 4. Single Source of Truth

Avoid storing the same business fact in multiple places.

### 5. Simple Before Complex

Prefer the simplest solution that satisfies the requirement.

### 6. Small, Verifiable Steps

Implement and validate functionality incrementally.

### 7. Decision-Oriented Analytics

Every KPI and visualization should support understanding or decision-making.

---

# 20. Definition of Done for the MVP

The MVP is complete when:

```text
[ ] Data can be ingested
[ ] Data quality can be evaluated
[ ] Valid data is persisted
[ ] KPIs are calculated
[ ] Baselines are established
[ ] Known anomalies are detected
[ ] Alerts are explainable
[ ] Problems can be prioritized
[ ] Dashboard is usable
[ ] Results have been independently validated
[ ] Tests exist for critical logic
[ ] Documentation is complete
[ ] Project can be reproduced locally
```

---

# 21. Next Phase

The next project phase is:

> **Requirements Definition**

The first deliverable after this Project Brief is:

```text
docs/requirements.md
```

Requirements will define the specific behaviors the system must implement.

The initial requirement candidates are:

```text
REQ-001  Upload Production CSV
REQ-002  Upload Downtime CSV
REQ-003  Validate Production Records
REQ-004  Validate Downtime Records
REQ-005  Generate Data Quality Summary
REQ-006  Store Valid Records
REQ-007  Calculate Production KPIs
REQ-008  Calculate Quality KPIs
REQ-009  Calculate Downtime KPIs
REQ-010  Calculate Baselines
REQ-011  Detect Deviations
REQ-012  Generate Explainable Alerts
REQ-013  Calculate Priority Scores
REQ-014  Display Dashboard
```

Requirements must be defined and reviewed before implementation begins.

---

# 22. Final Objective

Production Insight is not intended to be the most sophisticated analytics platform possible.

Its purpose is to demonstrate the complete process of transforming an ambiguous operational problem into a working, testable, explainable technical solution.

The project should ultimately demonstrate the ability to move from:

```text
Problem
   ↓
Requirements
   ↓
Data
   ↓
Design
   ↓
Implementation
   ↓
Validation
   ↓
Decision
```

The central question remains:

> **What problem are we solving, why does it matter, how can we solve it, and how do we know the solution works?**

**Problem first.  
Data second.  
Design third.  
Code fourth.**

Never the other way around