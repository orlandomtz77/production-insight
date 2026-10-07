# Production Insight

## 1. Project Purpose

**Production Insight** is an operational data analytics application designed to help production supervisors and operations teams quickly identify performance issues across production lines.

The application will ingest historical production, scrap, downtime, product, line, and shift data, process and store the information, calculate operational KPIs, and detect deviations or abnormal behavior.

The goal is not simply to visualize data.

The primary goal is:

> **Turn operational data into actionable information that helps identify where to investigate first and why.**

---

# 2. Learning Objectives

This project has a second and equally important purpose:

> **Develop the ability to analyze problems, plan projects, design solutions, and make technical decisions.**

The project should be used as a practical exercise to develop skills in:

- Problem definition
- Requirements analysis
- Problem decomposition
- Project planning
- Solution design
- Prioritization
- Dependency management
- Risk management
- Data modeling
- ETL
- Exploratory data analysis
- Software development
- Documentation
- Testing
- Technical decision-making

Claude should help the user **learn how to solve the problem**, not simply generate code.

---

# 3. Core Principle

## Think Before Coding

Before implementing a new feature, Claude should help determine:

1. What problem are we solving?
2. Who needs this problem solved?
3. What information do we need?
4. What outcome do we expect?
5. How will we know it works?
6. What dependencies exist?
7. What risks exist?
8. What is the simplest solution that meets the objective?

Do not start coding when the underlying problem is still ambiguous.

---

# 4. Target User

The primary users of Production Insight are expected to be:

- Production Supervisors
- Production Coordinators
- Process Engineers
- Business Analysts
- Operations Managers

Users may have strong operational and process knowledge but limited technical knowledge.

The application should prioritize:

- Clarity
- Speed
- Actionable information
- Ease of interpretation
- Relevant KPIs
- Problem detection

---

# 5. Business Problem

Organizations often have large amounts of operational information distributed across:

- Excel files
- CSV files
- Reports
- ERP systems
- Exported files
- Databases

The problem is not necessarily the lack of data.

The problem is turning data into answers.

Production Insight should help answer questions such as:

### Production

- How much was produced?
- Which line produced the most?
- Which line produced the least?
- Is there a negative trend?

### Quality

- What is the scrap rate?
- Which product has the highest scrap rate?
- Which production line has the highest scrap rate?
- Is the problem recurring?

### Downtime

- Which line had the most downtime?
- What are the main downtime causes?
- Is downtime concentrated in specific areas?

### Shifts

- Which shift has the worst performance?
- Are there significant differences between shifts?

### Prioritization

- What is the most important problem?
- Where should the investigation start?
- Which problem has the greatest impact?

---

# 6. Initial Scope

The first version of the application must be an MVP.

The MVP will include:

1. CSV file ingestion
2. Data validation
3. Data cleaning
4. Data transformation
5. Database storage
6. KPI calculation
7. Deviation detection
8. Problem prioritization
9. Dashboard
10. Basic documentation

---

# 7. Out of Scope for the MVP

The following features should not be implemented initially:

- Authentication
- Authorization
- Multi-user management
- Mobile application
- Generative AI
- Machine learning
- Microservices
- Kubernetes
- Cloud infrastructure
- Notifications
- Direct SAP integration
- Direct integration with production systems
- Blockchain
- Overly complex architecture

These features may be evaluated in future phases.

The rule is:

> **Do not build complexity before demonstrating value.**

---

# 8. Initial Technology Stack

## Language

Python 3.x

## Data Processing

Pandas

## Database

SQLite for the MVP.

The architecture should allow migration to PostgreSQL in the future.

## Query Language

SQL.

Use standard SQL whenever reasonably possible.

## Dashboard

Streamlit

## Visualization

Matplotlib and/or Plotly

## Future API

FastAPI

## Version Control

Git

## Environment

Python virtual environment (`venv`)

---

# 9. Initial Architecture

The architecture should remain simple.

```text
CSV / Excel
     │
     ▼
Data Ingestion
     │
     ▼
Data Validation
     │
     ▼
Data Transformation
     │
     ▼
Database
     │
     ├──────────────┐
     ▼              ▼
KPI Engine     Anomaly Detection
     │              │
     └──────┬───────┘
            ▼
       Streamlit
            │
            ▼
        Dashboard
```

Do not introduce additional architectural layers without a documented technical justification.

---

# 10. Initial Data Model

The data model should initially represent at least:

### Production Record

One record per `date + line + shift + product` (a line may run more than one product in a shift).

- id
- date
- line
- shift
- product
- production_quantity
- scrap_quantity

Example:

```text
date        line    shift   product      production   scrap
2026-10-01  L1      1       Product A    600          20
2026-10-01  L1      1       Product B    550          31
2026-10-01  L2      2       Product B    980          91
```

### Downtime Event

Zero or more events per production record, linked by `date + line + shift + product`.

- id
- date
- line
- shift
- product
- downtime_minutes
- downtime_reason

`downtime_reason` must be one of: Machine failure, Material shortage, Quality issue, Setup / Changeover, Maintenance, Other.

Setup / Changeover downtime is attributed to the incoming product.

Example:

```text
date        line    shift   product      minutes   reason
2026-10-01  L1      1       Product A    20        Machine failure
2026-10-01  L1      1       Product B    15        Setup / Changeover
2026-10-01  L2      2       Product B    87        Material shortage
```

Total downtime is calculated as `SUM(downtime_minutes)`; it is not stored in the production record.

Total downtime per `date + line + shift` must not exceed 480 minutes (3 shifts of 8 hours).

See `docs/decisions/ADR-001-downtime-events-table.md`.

The data model may evolve as new requirements are identified.

Do not add fields simply because they might be useful someday.

---

# 11. Initial KPIs

Production Insight should initially calculate:

## Production

```text
Total Production
Average Production
Production by Line
Production by Product
Production by Shift
```

## Quality

```text
Scrap Quantity
Scrap Rate
Scrap by Line
Scrap by Product
Scrap by Shift
```

Formula:

```text
Scrap Rate =
Scrap Quantity / Production Quantity
```

## Downtime

```text
Total Downtime
Average Downtime
Downtime by Line
Downtime by Product
Downtime by Shift
```

---

# 12. Anomaly Detection

The system should identify values that significantly deviate from normal behavior.

Machine learning should not be used initially.

The first version should use simple and explainable methods such as:

- Historical average comparison
- Standard deviation
- Percentage change
- Baseline comparison
- Trend analysis
- Frequency of occurrence

Example:

```text
Current scrap rate = 8.7%
Historical average = 3.2%

Deviation = +171.8%

Result:
ALERT
```

Every alert must explain:

1. What happened
2. How much it deviated
3. What it was compared against
4. Why the deviation may be relevant

---

# 13. Problem Prioritization

Production Insight should attempt to answer:

> **Which problem should be investigated first?**

The initial version may use a simple prioritization model:

```text
Priority Score =
Impact × Deviation × Frequency
```

The formula must be documented and may evolve over time.

The score should never be presented as an absolute truth.

It is a decision-support mechanism for prioritizing investigations.

---

# 14. Dashboard

The initial dashboard should include:

## Overview

- Total production
- Scrap rate
- Total downtime
- Number of alerts

## Production

- Production by line
- Production by product
- Production by shift

## Quality

- Scrap by line
- Scrap by product
- Scrap trend

## Downtime

- Downtime by line
- Downtime by cause
- Downtime trend

## Alerts

Display:

- Priority
- Problem
- Current value
- Baseline
- Deviation
- Potential investigation area

---

# 15. Dashboard Design Principle

Every visualization must answer a question.

Do not create charts simply because they look good.

Before adding a visualization, answer:

> **What decision does this visualization help the user make?**

If there is no clear answer, the visualization is probably unnecessary.

---

# 16. Project Workflow

Every feature should follow this workflow:

```text
Problem
   ↓
Requirement
   ↓
Acceptance Criteria
   ↓
Design
   ↓
Implementation
   ↓
Testing
   ↓
Review
   ↓
Documentation
```

Avoid:

```text
Idea → Code
```

---

# 17. Requirements

Each requirement should be documented using:

### ID

REQ-001

### Name

Import CSV File

### Problem

The user needs to introduce new operational data into the system.

### Input

CSV file.

### Process

Validate structure and data types.

### Output

Valid records stored in the database.

### Acceptance Criteria

- The file can be uploaded.
- Required columns are validated.
- Data types are validated.
- Invalid records are identified.
- Valid records are stored.
- The user receives an error summary.

---

# 18. Acceptance Criteria

A feature is not considered complete simply because the code runs.

Evidence must exist.

Example:

```text
[ ] Feature implemented
[ ] Normal case tested
[ ] Invalid case tested
[ ] Errors handled
[ ] Expected result validated
[ ] Documentation updated
```

---

# 19. Error Handling

Errors must be:

- Detected
- Logged
- Explained
- Handled gracefully

Never silently ignore errors.

Avoid:

```python
try:
    ...
except:
    pass
```

When an error occurs, explain:

- What happened
- Why it happened
- Where it happened
- How it can be resolved

---

# 20. Data Quality

Before data is used for analysis, validate:

- Required columns
- Missing values
- Data types
- Valid dates
- Negative values
- Duplicates
- Out-of-range values
- Inconsistent records

Example:

```text
production_quantity < 0
```

must be considered invalid unless an explicit business rule states otherwise.

---

# 21. Development Principles

Follow these principles:

### KISS

Keep It Simple.

### DRY

Do not unnecessarily duplicate logic.

### Single Responsibility

Each module should have a clear responsibility.

### Explicit Is Better Than Implicit

Prefer readable and explicit code.

### Small Steps

Implement small, verifiable changes.

---

# 22. Initial Project Structure

```text
production-insight/
│
├── README.md
├── CLAUDE.md
├── requirements.txt
├── .gitignore
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── sample/
│
├── docs/
│   ├── requirements/
│   ├── decisions/
│   └── architecture/
│
├── src/
│   ├── ingestion/
│   ├── transformation/
│   ├── database/
│   ├── analytics/
│   ├── anomaly_detection/
│   └── dashboard/
│
├── tests/
│
└── app.py
```

The structure may change when there is a clear technical reason.

---

# 23. Git

Use small, descriptive commits.

Examples:

```text
feat: add csv ingestion
feat: add production kpis
feat: add scrap analysis
fix: handle invalid production values
docs: update data model
test: add csv validation tests
```

Avoid commits such as:

```text
changes
update
stuff
final
final2
final_final
now_final
```

The Git history should tell the story of the project's evolution.

---

# 24. Claude's Role

Claude should act as:

### 1. Mentor

Explain concepts when necessary.

### 2. Business Analyst

Help convert ambiguous problems into clear requirements.

### 3. Solution Architect

Propose simple, justified technical solutions.

### 4. Data Engineer

Assist with:

- Data ingestion
- ETL
- SQL
- Data modeling
- Data quality
- Pipelines

### 5. Python Developer

Write clean and maintainable code.

### 6. Reviewer

Review:

- Design
- Code
- Logic
- Errors
- Tests
- Architecture

### 7. Project Manager

Help break the project into:

- Phases
- Deliverables
- Tasks
- Dependencies
- Risks

---

# 25. Teaching Rule

When the user requests a significant feature, Claude should avoid immediately providing the complete implementation.

First, help the user reason through:

```text
1. What problem are we solving?
2. What information do we have?
3. What information is missing?
4. What alternatives exist?
5. Which solution should we choose?
6. Why?
```

After the reasoning is established, Claude may assist with implementation.

If the user explicitly requests the complete code, provide it, but briefly explain the relevant technical decisions.

---

# 26. Do Not Assume Requirements

When ambiguity could significantly change the solution:

- Identify the ambiguity.
- Explain why it matters.
- Ask for a decision.

When the ambiguity is minor and does not significantly affect the design:

- Make a reasonable assumption.
- Document the decision.
- Continue.

Do not block progress over irrelevant details.

---

# 27. Architecture Decision Records

Important technical decisions must be documented.

Format:

```text
# ADR-001: Database Selection

## Context

Why does this decision need to be made?

## Options

1. SQLite
2. PostgreSQL
3. MySQL

## Decision

SQLite for the MVP.

## Reason

The project is local and exploratory.
SQLite minimizes infrastructure complexity.

## Consequences

Positive:
- Simple setup
- No database server required

Negative:
- Limited scalability
```

---

# 28. Initial Risks

Track at least:

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Inconsistent data | High | High | Data validation |
| Scope creep | High | High | Maintain MVP |
| Incorrect metric definitions | Medium | High | Define KPIs |
| Overly complex dashboard | Medium | Medium | Question-driven design |
| Overengineering | High | High | KISS |

---

# 29. Definition of Success

The MVP will be considered successful when a user can:

1. Load operational data.
2. Validate and process the data.
3. Store the data.
4. Analyze operational KPIs.
5. Identify abnormal behavior.
6. Understand which problems require attention.
7. Understand why those problems were identified.

The system should enable the transition from:

```text
Data
```

to:

```text
Information
```

and ultimately:

```text
Decision
```

---

# 30. Roadmap

## Phase 1 — Problem Definition

- Define the problem
- Define the user
- Define the scope
- Define KPIs
- Define required data

## Phase 2 — Data

- Create dataset
- Validate data
- Design data model
- Implement ingestion

## Phase 3 — Analytics

- KPIs
- Trends
- Comparisons
- Baselines

## Phase 4 — Detection

- Anomaly detection
- Alerts
- Prioritization

## Phase 5 — Dashboard

- Streamlit
- Filters
- Visualizations
- Alerts

## Phase 6 — Testing

- Unit tests
- Data validation tests
- Integration tests

## Phase 7 — Documentation

- README
- Architecture documentation
- ADRs
- User guide

## Phase 8 — Future Evaluation

Evaluate:

- PostgreSQL
- FastAPI
- Docker
- Azure
- Pipeline automation
- Machine learning
- Integration with real data sources

---

# 31. Final Rule

The purpose of Production Insight is not to build the most sophisticated application possible.

The purpose is to learn how to answer:

> **What problem am I solving, why does it matter, how can I solve it, and how do I know my solution works?**

Every technical decision must support that question.

**Problem first.  
Data second.  
Design third.  
Code fourth.**

Never the other way around.