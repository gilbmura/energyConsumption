CREATE DATABASE IF NOT EXISTS pjme_energy CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE pjme_energy;

-- 1. Data Sources Dimension Table (Provenance & Licensing)
CREATE TABLE IF NOT EXISTS data_sources (
  source_id INT AUTO_INCREMENT PRIMARY KEY,
  dataset_name VARCHAR(150) NOT NULL,
  provider VARCHAR(150) NOT NULL,
  source_url VARCHAR(500),
  description TEXT,
  UNIQUE KEY uq_dataset_provider (dataset_name, provider)
);

-- 2. Time Dimensions Table (De-aggregated calendar coordinates)
CREATE TABLE IF NOT EXISTS time_dimensions (
  Datetime DATETIME NOT NULL PRIMARY KEY,
  hour TINYINT UNSIGNED NOT NULL,
  day_of_week TINYINT UNSIGNED NOT NULL,
  month TINYINT UNSIGNED NOT NULL,
  is_weekend BOOLEAN NOT NULL,
  CHECK (hour BETWEEN 0 AND 23),
  CHECK (day_of_week BETWEEN 0 AND 6),
  CHECK (month BETWEEN 1 AND 12)
);

-- 3. Energy Readings Fact Table (Multivariate: Demand + Weather + Data Quality)
CREATE TABLE IF NOT EXISTS energy_readings (
  reading_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  Datetime DATETIME NOT NULL UNIQUE,
  PJME_MW DOUBLE NOT NULL,
  temperature_c DOUBLE NOT NULL,
  was_imputed BOOLEAN NOT NULL DEFAULT 0,
  source_id INT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_reading_time FOREIGN KEY (Datetime) REFERENCES time_dimensions(Datetime)
    ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_reading_source FOREIGN KEY (source_id) REFERENCES data_sources(source_id)
    ON UPDATE CASCADE ON DELETE RESTRICT,
  INDEX idx_readings_demand (PJME_MW),
  INDEX idx_readings_temp (temperature_c),
  INDEX idx_readings_imputed (was_imputed)
);

-- Ingestion Source Metadata Initial Insert
INSERT INTO data_sources (dataset_name, provider, source_url, description)
VALUES ('Hourly Energy Consumption - PJME (Cleaned Multivariate)', 'Kaggle collection by Rob Mulla & Group Preprocessing',
 'https://www.kaggle.com/datasets/robikscube/hourly-energy-consumption',
 'Hourly PJM East demand with external temperature (temperature_c) and imputation audit flag (was_imputed).')
ON DUPLICATE KEY UPDATE source_url=VALUES(source_url), description=VALUES(description);
