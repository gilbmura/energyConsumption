# MongoDB Collection Design: Multivariate Time-Series Energy & Weather Observations

**Author / Member 3:** Laura Karangwa  
**Database:** `pjme_energy`  
**Collection:** `energy_observations`  
**Target Workload:** High-throughput multivariate ingestion, weather correlation aggregations, and fast chronological range lookups for forecasting models.

---

## 1. Architectural Philosophy: Document Model for Time Series

In contrast to relational databases that enforce normalization across multiple tables via foreign keys (3NF), document databases achieve maximum read efficiency for time-series workloads through **denormalization and locality of reference**.

### Design Pattern: Hybrid Observation Document
For this implementation, we utilize the **Hybrid Time-Series Document Pattern**, where each document corresponds to an hourly observation and contains:
1. **Core Measurement:** The raw grid demand observation (`PJME_MW`).
2. **External Weather Observation:** Ambient temperature in Celsius (`temperature_c`).
3. **Data Quality Audit:** Imputation flag (`was_imputed`) indicating if the observation was cleaned or interpolated.
4. **Temporal Anchor:** A native BSON `Date` object (`Datetime`).
5. **De-aggregated Dimensions:** Temporal calendar coordinates (`hour`, `day_of_week`, `month`, `is_weekend`).
6. **Pre-computed Sequential Features:** Short-term and seasonal lag features (`lag_1`, `lag_24`, `lag_168`, `rolling_mean_24`, `rolling_mean_168`).

**Why this pattern?**
- **Single-I/O Retrieval:** An API request for a date range (Task 3) or a prediction script requesting a historical window (Task 4) retrieves all necessary feature inputs in a single query without complex `JOIN` operations.
- **Multivariate Schema Support:** Easily correlates demand and weather signals without separate join overhead.

---

## 2. Document Schema & Data Types

```javascript
{
  "_id": ObjectId("665f1a9b2c3d4e5f6a7b8c9d"),
  "Datetime": ISODate("2018-01-01T00:00:00.000Z"),  // BSON Date (UTC / standard reference)
  "PJME_MW": 39928.0,                               // Double (continuous demand in MW)
  "temperature_c": -12.1,                           // Double (ambient temperature in °C)
  "was_imputed": false,                             // Boolean (data cleaning audit flag)
  "hour": 0,                                        // Int32 (0 - 23)
  "day_of_week": 0,                                 // Int32 (0=Monday, ..., 6=Sunday)
  "month": 1,                                       // Int32 (1 - 12)
  "is_weekend": false,                              // Boolean (true / false)
  "source": "PJME_clean",                           // String (provenance identifier)
  "lag_1": 39500.0,                                 // Double or null (1-hour lag)
  "lag_24": 34100.0,                                // Double or null (24-hour lag)
  "lag_168": 32800.0,                               // Double or null (1-week lag)
  "rolling_mean_24": 35210.4,                       // Double or null (24-hour prior rolling mean)
  "rolling_mean_168": 33940.8                       // Double or null (168-hour prior rolling mean)
}
```

---

## 3. Indexing Strategy

| Index Name | Keys | Purpose | Complexity |
| :--- | :--- | :--- | :--- |
| **`uniq_datetime`** | `{ Datetime: 1 }` (Unique) | Enforces temporal uniqueness and guarantees chronological sorting. | $O(\log N)$ |
| **`compound_datetime_demand`** | `{ Datetime: 1, PJME_MW: 1 }` | Covered query optimization for date-range slicing. | $O(\log N)$ |
| **`idx_hour`** | `{ hour: 1 }` | Optimizes diurnal profile aggregation pipelines ($O(1)$ index scan per hour). | $O(\log N)$ |
| **`idx_temperature`** | `{ temperature_c: 1 }` | Accelerates temperature-bracketed weather filtering. | $O(\log N)$ |

---

## 4. Sample Document Representation
A complete set of verified sample documents drawn directly from the PJM East dataset is persisted in [`sample_documents.json`](sample_documents.json).
