# MongoDB observation contract

Author: Laura Karangwa. Integrated with Gilbert's API and Tifare's forecasting client.

Database: `pjme_energy`. Collection: `energy_observations`.

Each document contains ObjectId `_id`, BSON datetime `Datetime`, numeric `PJME_MW` and `temperature_c`, boolean `was_imputed`, calendar fields `hour`, `day_of_week`, `month`, `is_weekend`, and source label `PJME_clean`.

The API accepts four public fields and creates calendar fields automatically. PUT updates these fields and preserves unrelated metadata and source information. Temperature is non-null to match MySQL.

## Time and uniqueness

A unique `Datetime` index enforces one observation per PJME hour. Additional indexes cover Datetime/demand, hour and temperature. `init.js` provisions fresh databases; the Python initializer also accepts equivalent existing indexes with different names.

Source timestamps are naive local clock labels. PyMongo/BSON carries these datetime values without converting the original labels. API JSON omits offsets. BSON's UTC representation does not establish the source's real timezone. Coordinate any future timezone migration across both databases and the model.

## Derived features

Calendar fields are maintained by the loader and API. Lag and rolling-average fields from the original sample design are historical caches, not authoritative model inputs: changing an observation can invalidate later observations' features.

The integrated loader no longer creates these caches and removes them on reloaded documents. The API removes old caches on the document it updates, never serves cached lag fields, and does not claim to refresh all later documents. Tifare's shared feature function computes every lag and rolling mean from current observed history. The remaining legacy fields in an existing collection can be ignored or removed in an explicit migration.

## JSON examples

`sample_documents.json` contains ordinary JSON examples derived from the cleaned CSV, with naive ISO timestamp strings. These examples document the data; the loader converts timestamps to Python datetime objects before PyMongo writes BSON dates. Do not import the strings directly and expect BSON date-range queries to work.
