# Shared API contract

The API now targets Laura's schema. The authoritative integration notes are in [api/INTEGRATION.md](../../api/INTEGRATION.md), and routes/setup are in [api/README.md](../../api/README.md).

For prediction, use `GET /mysql/records/recent?limit=200` or `GET /mongo/records/recent?limit=200`. Both return `records` containing Datetime, PJME_MW, temperature_c, was_imputed and a backend-specific string id.

Timestamp strings preserve the cleaned CSV's naive clock labels. The model requires 168 consecutive non-imputed hourly observations. Temperature is required for database writes but is not currently a model feature.

Live verification is complete: the combined suite passed 150 tests, both databases match all 145,392 CSV records, and the real HTTP forecasting client succeeded for both backends. See `api/evidence/` and `databases/results/live_query_results.json` for executed evidence.
