USE pjme_energy;

-- 1. Top ten dates by average electricity demand (Grid Peak Load Stress)
SELECT DATE(r.Datetime) AS demand_date, 
       ROUND(AVG(r.PJME_MW), 2) AS avg_demand_mw,
       ROUND(MAX(r.PJME_MW), 2) AS peak_demand_mw, 
       ROUND(AVG(r.temperature_c), 2) AS avg_temp_c,
       COUNT(*) AS hourly_readings
FROM energy_readings r 
GROUP BY DATE(r.Datetime)
ORDER BY avg_demand_mw DESC 
LIMIT 10;

-- 2. Diurnal demand profile by hour of day (24-Hour Load Curve)
SELECT t.hour, 
       ROUND(AVG(r.PJME_MW), 2) AS avg_demand_mw,
       ROUND(MIN(r.PJME_MW), 2) AS min_demand_mw, 
       ROUND(MAX(r.PJME_MW), 2) AS max_demand_mw,
       ROUND(AVG(r.temperature_c), 2) AS avg_temp_c,
       COUNT(*) AS observations
FROM energy_readings r 
JOIN time_dimensions t ON t.Datetime = r.Datetime
GROUP BY t.hour 
ORDER BY t.hour;

-- 3. Observations for a chosen date range (One Week Slice: Jan 1 - Jan 8, 2018)
SELECT r.Datetime, r.PJME_MW, r.temperature_c, r.was_imputed, t.hour, t.day_of_week, t.month, t.is_weekend
FROM energy_readings r 
JOIN time_dimensions t ON t.Datetime = r.Datetime
WHERE r.Datetime >= '2018-01-01 00:00:00' AND r.Datetime < '2018-01-08 00:00:00'
ORDER BY r.Datetime;

-- 4. Multivariate Analysis: Demand vs Temperature Brackets (Weather Correlation)
SELECT 
    CASE 
        WHEN r.temperature_c < 0 THEN '1. Freezing (< 0°C)'
        WHEN r.temperature_c BETWEEN 0 AND 15 THEN '2. Cold (0-15°C)'
        WHEN r.temperature_c BETWEEN 15 AND 25 THEN '3. Mild (15-25°C)'
        ELSE '4. Hot (> 25°C)'
    END AS temp_category,
    ROUND(AVG(r.PJME_MW), 2) AS avg_demand_mw,
    ROUND(MAX(r.PJME_MW), 2) AS peak_demand_mw,
    COUNT(*) AS observations
FROM energy_readings r
GROUP BY temp_category
ORDER BY temp_category;
