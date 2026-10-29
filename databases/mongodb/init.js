// Shared development bootstrap. CSV clock labels are carried by BSON dates unchanged.
const energyDb = db.getSiblingDB("pjme_energy");
energyDb.energy_observations.createIndex({Datetime: 1}, {unique: true, name: "uniq_datetime"});
energyDb.energy_observations.createIndex({Datetime: 1, PJME_MW: 1}, {name: "compound_datetime_demand"});
energyDb.energy_observations.createIndex({hour: 1}, {name: "idx_hour"});
energyDb.energy_observations.createIndex({temperature_c: 1}, {name: "idx_temperature"});
