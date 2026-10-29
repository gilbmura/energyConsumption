"""PyMongo equivalents of Laura's four checked-in analytical queries."""

from datetime import datetime

NAMES = ("daily_peaks", "hourly_profile", "date_range", "temperature_profile")


def mongo_queries():
    return {
        "daily_peaks": [
            {
                "$group": {
                    "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$Datetime"}},
                    "avg_demand_mw": {"$avg": "$PJME_MW"},
                    "peak_demand_mw": {"$max": "$PJME_MW"},
                    "avg_temp_c": {"$avg": "$temperature_c"},
                    "hourly_readings": {"$sum": 1},
                }
            },
            {"$sort": {"avg_demand_mw": -1, "_id": 1}},
            {"$limit": 10},
        ],
        "hourly_profile": [
            {
                "$group": {
                    "_id": "$hour",
                    "avg_demand_mw": {"$avg": "$PJME_MW"},
                    "min_demand_mw": {"$min": "$PJME_MW"},
                    "max_demand_mw": {"$max": "$PJME_MW"},
                    "avg_temp_c": {"$avg": "$temperature_c"},
                    "observations": {"$sum": 1},
                }
            },
            {"$sort": {"_id": 1}},
        ],
        "date_range": [
            {
                "$match": {
                    "Datetime": {
                        "$gte": datetime(2018, 1, 1),
                        "$lt": datetime(2018, 1, 8),
                    }
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "Datetime": 1,
                    "PJME_MW": 1,
                    "temperature_c": 1,
                    "was_imputed": 1,
                    "hour": 1,
                    "day_of_week": 1,
                    "month": 1,
                    "is_weekend": 1,
                }
            },
            {"$sort": {"Datetime": 1}},
        ],
        "temperature_profile": [
            {
                "$project": {
                    "PJME_MW": 1,
                    "temp_category": {
                        "$switch": {
                            "branches": [
                                {
                                    "case": {"$lt": ["$temperature_c", 0]},
                                    "then": "1. Freezing (< 0°C)",
                                },
                                {
                                    "case": {"$lte": ["$temperature_c", 15]},
                                    "then": "2. Cold (0-15°C)",
                                },
                                {
                                    "case": {"$lte": ["$temperature_c", 25]},
                                    "then": "3. Mild (15-25°C)",
                                },
                            ],
                            "default": "4. Hot (> 25°C)",
                        }
                    },
                }
            },
            {
                "$group": {
                    "_id": "$temp_category",
                    "avg_demand_mw": {"$avg": "$PJME_MW"},
                    "peak_demand_mw": {"$max": "$PJME_MW"},
                    "observations": {"$sum": 1},
                }
            },
            {"$sort": {"_id": 1}},
        ],
    }
