// Run in mongosh after: use pjme_energy
const observations = db.energy_observations;
observations.createIndex({Datetime: 1}, {unique: true});
observations.createIndex({Datetime: 1, PJME_MW: 1});
observations.createIndex({hour: 1});
observations.createIndex({temperature_c: 1});

// 1. Top ten dates by average electricity demand with weather summary
observations.aggregate([
  {
    $group: {
      _id: { $dateToString: { format: "%Y-%m-%d", date: "$Datetime" } },
      avg_demand_mw: { $avg: "$PJME_MW" },
      peak_demand_mw: { $max: "$PJME_MW" },
      avg_temp_c: { $avg: "$temperature_c" },
      hourly_readings: { $sum: 1 }
    }
  },
  { $sort: { avg_demand_mw: -1 } },
  { $limit: 10 }
]);

// 2. Diurnal demand and temperature profile by hour of day
observations.aggregate([
  {
    $group: {
      _id: "$hour",
      avg_demand_mw: { $avg: "$PJME_MW" },
      min_demand_mw: { $min: "$PJME_MW" },
      max_demand_mw: { $max: "$PJME_MW" },
      avg_temp_c: { $avg: "$temperature_c" },
      observations: { $sum: 1 }
    }
  },
  { $sort: { _id: 1 } }
]);

// 3. Date range query (Jan 1, 2018 to Jan 8, 2018)
observations.find(
  {
    Datetime: {
      $gte: ISODate("2018-01-01T00:00:00Z"),
      $lt: ISODate("2018-01-08T00:00:00Z")
    }
  },
  {
    _id: 0,
    Datetime: 1,
    PJME_MW: 1,
    temperature_c: 1,
    was_imputed: 1,
    hour: 1,
    day_of_week: 1,
    month: 1,
    is_weekend: 1
  }
).sort({ Datetime: 1 });

// 4. Multivariate Analysis: Demand by Temperature Category
observations.aggregate([
  {
    $project: {
      PJME_MW: 1,
      temp_category: {
        $switch: {
          branches: [
            { case: { $lt: ["$temperature_c", 0] }, then: "1. Freezing (< 0°C)" },
            { case: { $lte: ["$temperature_c", 15] }, then: "2. Cold (0-15°C)" },
            { case: { $lte: ["$temperature_c", 25] }, then: "3. Mild (15-25°C)" }
          ],
          default: "4. Hot (> 25°C)"
        }
      }
    }
  },
  {
    $group: {
      _id: "$temp_category",
      avg_demand_mw: { $avg: "$PJME_MW" },
      peak_demand_mw: { $max: "$PJME_MW" },
      observations: { $sum: 1 }
    }
  },
  { $sort: { _id: 1 } }
]);
