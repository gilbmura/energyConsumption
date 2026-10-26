# Task 2: Relational (MySQL) and Non-Relational (MongoDB) Database Design & Implementation

**Student / Member 3:** Laura Karangwa  
**Group Role:** Database Architect & Engineer (MySQL & MongoDB)  
**Dataset:** PJM East (PJME) Hourly Electricity Consumption (Kaggle / Rob Mulla)  
**Total Dataset Observations:** 145,362 hourly readings (2002-01-01 to 2018-08-03)  

---

## 1. Executive Summary & Deliverables Overview

This directory provides the complete implementation for **Task 2 (Design Databases: SQL and MongoDB)** of the Time Series Group Assignment:

1. **Relational Schema (MySQL)**: 3-table normalized schema in 3NF ([`mysql/schema.sql`](mysql/schema.sql)) with referential integrity, foreign key cascades, and temporal checks.
2. **Professional ERD Diagram**: Complete visual ERD ([`docs/erd_diagram.png`](docs/erd_diagram.png)) and architectural documentation ([`docs/erd.md`](docs/erd.md)).
3. **Non-Relational Schema (MongoDB)**: Hybrid Time-Series Document Collection Design ([`mongodb/collection_design.md`](mongodb/collection_design.md)) with sample documents ([`mongodb/sample_documents.json`](mongodb/sample_documents.json)) and compound indexes.
4. **Analytical Queries & Real Execution Evidence**: 3 comprehensive queries per database ([`mysql/queries.sql`](mysql/queries.sql), [`mongodb/queries.js`](mongodb/queries.js)) with full outputs and interpretations in [`results/query_execution_results.md`](results/query_execution_results.md).
5. **Team Integration Contract**: Standardized data and endpoint contract for Member 4 (API Endpoints) and Member 2 (Prediction Script) in [`docs/api_contract.md`](docs/api_contract.md).

---

## 2. Directory Structure

```text
laura_task3_pjm_databases/
├── README.md                              <- Main technical documentation & reproduction guide
├── mysql/
│   ├── schema.sql                         <- DDL scripts (3 tables: data_sources, time_dimensions, energy_readings)
│   └── queries.sql                        <- 3 analytical SQL queries
├── mongodb/
│   ├── collection_design.md               <- Collection schema, indexing strategy, & design rationale
│   ├── queries.js                         <- 3 analytical MongoDB aggregation & find queries
│   └── sample_documents.json              <- Real sample documents with base & engineered features
├── docs/
│   ├── erd.md                             <- ERD explanation and architectural justification
│   ├── erd_diagram.png                    <- High-resolution rendered ERD visual diagram
│   ├── api_contract.md                    <- Shared JSON payload contract for Members 2 & 4
│   └── evidence_checklist.md             <- Submission audit checklist
├── scripts/
│   ├── execute_queries_and_export_results.py <- Automated query execution & validation runner
│   ├── render_erd_diagram.py             <- Generates the professional ERD PNG graphic
│   └── load_csv_to_databases.py           <- Batch loader for live MySQL and MongoDB instances
└── results/
    └── query_execution_results.md         <- Real query output tables, interpretations, and cross-DB check
```

---

## 3. Relational Schema Architecture (MySQL)

The relational schema implements a normalized star-fact design adhering to **Third Normal Form (3NF)**:

| Table | Type | Role & Description | Key Constraints |
| :--- | :--- | :--- | :--- |
| **`data_sources`** | Dimension | Ingestion metadata, dataset source URL, and provider. | `source_id` (PK, Auto-inc), Unique `(dataset_name, provider)` |
| **`time_dimensions`** | Dimension | Pre-calculated calendar coordinates (`hour`, `day_of_week`, `month`, `is_weekend`). | `Datetime` (PK), Range Checks on hour/month |
| **`energy_readings`** | Fact Table | Hourly continuous demand (`PJME_MW`), timestamp FK, and source FK. | `reading_id` (PK), `Datetime` (FK, Unique), `source_id` (FK) |

### Visual ERD
Refer to [`docs/erd_diagram.png`](docs/erd_diagram.png) for the visual representation.

---

## 4. MongoDB Collection Architecture

- **Database:** `pjme_energy`
- **Collection:** `energy_observations`
- **Pattern:** Hybrid Time-Series Document Model. Denormalizes hourly demand with calendar coordinates and prior sequential lag features (`lag_1`, `lag_24`, `lag_168`, `rolling_mean_24`, `rolling_mean_168`).
- **Indexes:**
  - `{ Datetime: 1 }` (Unique): Enforces strict temporal ordering and single-record uniqueness.
  - `{ Datetime: 1, PJME_MW: 1 }`: Covered query index for date range lookups.
  - `{ hour: 1 }`: Accelerates diurnal profile aggregations.

---

## 5. Analytical Queries & Results Summary

Detailed tables, execution logs, and interpretations are documented in [`results/query_execution_results.md`](results/query_execution_results.md).

### Query 1: Top 10 Peak Demand Days
- **Objective:** Detect historic grid stress and peak capacity requirements.
- **Top Date:** **2006-08-02** with an average demand of **52,229.83 MW** and single-hour peak of **62,009.00 MW**.
- **Results Match:** Identical across MySQL and MongoDB to 2 decimal places.

### Query 2: Diurnal Hourly Demand Profile
- **Objective:** Analyze the 24-hour load curve for off-peak base load vs. evening peak ramp-up.
- **Off-Peak Minimum:** Hour **04:00** (average **25,414.92 MW**).
- **Evening Peak:** Hours **18:00 - 19:00** (average **36,426.63 MW**).

### Query 3: Date-Range Slicing (Jan 1 - Jan 8, 2018)
- **Objective:** Rapidly extract an exact chronological window for API delivery and model inference.
- **Returned Records:** Exactly **168 observations** (7 days × 24 hours).

---

## 6. How to Reproduce All Results

1. **Prerequisites**: Python 3.9+ with `pandas` and `matplotlib` installed.
2. **Execute Queries & Generate Evidence Report**:
   ```bash
   python scripts/execute_queries_and_export_results.py
   ```
3. **Re-render ERD Visual Diagram**:
   ```bash
   python scripts/render_erd_diagram.py
   ```
4. **Inspect Generated Deliverables**:
   - Query execution report: [`results/query_execution_results.md`](results/query_execution_results.md)
   - Real sample documents: [`mongodb/sample_documents.json`](mongodb/sample_documents.json)
   - ERD graphic: [`docs/erd_diagram.png`](docs/erd_diagram.png)

---

## 7. Recommended 4 Git Commits for Member 3

To satisfy the rubric criterion for individual technical contributions (minimum 4 meaningful commits):

```bash
# Commit 1
git add mysql/schema.sql docs/erd.md docs/erd_diagram.png
git commit -m "feat(mysql): implement 3NF relational schema and architectural ERD"

# Commit 2
git add mongodb/collection_design.md mongodb/sample_documents.json
git commit -m "feat(mongodb): design hybrid time-series collection and sample document schema"

# Commit 3
git add mysql/queries.sql mongodb/queries.js scripts/execute_queries_and_export_results.py
git commit -m "feat(db-queries): implement analytical SQL queries and MongoDB aggregation pipelines"

# Commit 4
git add results/query_execution_results.md docs/api_contract.md README.md
git commit -m "docs(task2): document real query execution evidence and team API integration contract"
```
