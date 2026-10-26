"""Load PJME_hourly.csv to MySQL and MongoDB. Configure env vars first."""
import os
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, text
from pymongo import MongoClient, UpdateOne

CSV = Path(os.getenv('PJME_CSV', 'PJME_hourly.csv'))
MYSQL_URL = os.getenv('MYSQL_URL')  # e.g. mysql+pymysql://user:pass@localhost:3306/pjme_energy
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017')
BATCH = 1000

if not MYSQL_URL:
    raise RuntimeError('Set MYSQL_URL to a connection URL ending in /pjme_energy')
if not CSV.exists():
    raise FileNotFoundError(f'Cannot find {CSV}; download PJME_hourly.csv first.')

df = pd.read_csv(CSV)
if not {'Datetime', 'PJME_MW'}.issubset(df.columns):
    raise ValueError(f'Expected Datetime and PJME_MW; found {list(df.columns)}')
df = df[['Datetime', 'PJME_MW']].copy()
df['Datetime'] = pd.to_datetime(df['Datetime'], errors='coerce')
df['PJME_MW'] = pd.to_numeric(df['PJME_MW'], errors='coerce')
df = df.dropna(subset=['Datetime', 'PJME_MW']).drop_duplicates('Datetime').sort_values('Datetime')
df['hour'] = df.Datetime.dt.hour
df['day_of_week'] = df.Datetime.dt.dayofweek  # Monday=0
df['month'] = df.Datetime.dt.month
df['is_weekend'] = df.day_of_week >= 5
for col, shift in [('lag_1', 1), ('lag_24', 24), ('lag_168', 168)]:
    df[col] = df.PJME_MW.shift(shift)
df['rolling_mean_24'] = df.PJME_MW.shift(1).rolling(24).mean()
df['rolling_mean_168'] = df.PJME_MW.shift(1).rolling(168).mean()

engine = create_engine(MYSQL_URL, pool_pre_ping=True)
with engine.begin() as c:
    c.execute(text('''CREATE TABLE IF NOT EXISTS data_sources (
      source_id INT AUTO_INCREMENT PRIMARY KEY, dataset_name VARCHAR(150) NOT NULL,
      provider VARCHAR(150) NOT NULL, source_url VARCHAR(500), description TEXT,
      UNIQUE KEY uq_dataset_provider (dataset_name, provider))'''))
    c.execute(text('''CREATE TABLE IF NOT EXISTS time_dimensions (
      Datetime DATETIME PRIMARY KEY, hour TINYINT UNSIGNED NOT NULL,
      day_of_week TINYINT UNSIGNED NOT NULL, month TINYINT UNSIGNED NOT NULL,
      is_weekend BOOLEAN NOT NULL)'''))
    c.execute(text('''CREATE TABLE IF NOT EXISTS energy_readings (
      reading_id BIGINT AUTO_INCREMENT PRIMARY KEY, Datetime DATETIME NOT NULL UNIQUE,
      PJME_MW DOUBLE NOT NULL, source_id INT NOT NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (Datetime) REFERENCES time_dimensions(Datetime) ON DELETE CASCADE,
      FOREIGN KEY (source_id) REFERENCES data_sources(source_id), INDEX idx_readings_demand (PJME_MW))'''))
    c.execute(text('''INSERT INTO data_sources(dataset_name,provider,source_url,description)
      VALUES(:n,:p,:u,:d) ON DUPLICATE KEY UPDATE source_url=VALUES(source_url),description=VALUES(description)'''),
      {'n':'Hourly Energy Consumption - PJME','p':'Kaggle collection by Rob Mulla',
       'u':'https://www.kaggle.com/datasets/robikscube/hourly-energy-consumption',
       'd':'Hourly PJM East demand; original fields Datetime and PJME_MW.'})
    sid = c.execute(text('SELECT source_id FROM data_sources WHERE dataset_name=:n AND provider=:p'),
      {'n':'Hourly Energy Consumption - PJME','p':'Kaggle collection by Rob Mulla'}).scalar_one()
    for start in range(0, len(df), BATCH):
        part = df.iloc[start:start+BATCH]
        dims = [{'Datetime':r.Datetime.to_pydatetime(),'hour':int(r.hour),'day_of_week':int(r.day_of_week),
                 'month':int(r.month),'is_weekend':bool(r.is_weekend)} for r in part.itertuples()]
        c.execute(text('''INSERT INTO time_dimensions(Datetime,hour,day_of_week,month,is_weekend)
          VALUES(:Datetime,:hour,:day_of_week,:month,:is_weekend)
          ON DUPLICATE KEY UPDATE hour=VALUES(hour),day_of_week=VALUES(day_of_week),month=VALUES(month),is_weekend=VALUES(is_weekend)'''), dims)
        vals = [{'Datetime':r.Datetime.to_pydatetime(),'PJME_MW':float(r.PJME_MW),'source_id':int(sid)} for r in part.itertuples()]
        c.execute(text('''INSERT INTO energy_readings(Datetime,PJME_MW,source_id)
          VALUES(:Datetime,:PJME_MW,:source_id) ON DUPLICATE KEY UPDATE PJME_MW=VALUES(PJME_MW),source_id=VALUES(source_id)'''), vals)

client = MongoClient(MONGO_URI)
coll = client['pjme_energy']['energy_observations']
coll.create_index('Datetime', unique=True)
coll.create_index([('Datetime',1),('PJME_MW',1)])
coll.create_index('hour')
for start in range(0, len(df), BATCH):
    part = df.iloc[start:start+BATCH]
    ops = []
    for r in part.itertuples():
        doc = {'Datetime':r.Datetime.to_pydatetime(),'PJME_MW':float(r.PJME_MW),'hour':int(r.hour),
               'day_of_week':int(r.day_of_week),'month':int(r.month),'is_weekend':bool(r.is_weekend),
               'source':'PJME_hourly'}
        for f in ['lag_1','lag_24','lag_168','rolling_mean_24','rolling_mean_168']:
            v = getattr(r, f)
            doc[f] = None if pd.isna(v) else float(v)
        ops.append(UpdateOne({'Datetime':doc['Datetime']},{'$set':doc},upsert=True))
    if ops:
        coll.bulk_write(ops, ordered=False)
with engine.connect() as c:
    print('MySQL energy_readings:', c.execute(text('SELECT COUNT(*) FROM energy_readings')).scalar_one())
    print('MySQL time_dimensions:', c.execute(text('SELECT COUNT(*) FROM time_dimensions')).scalar_one())
print('MongoDB energy_observations:', coll.count_documents({}))
print('Loader finished. Execute the query files and save actual results/screenshots.')
