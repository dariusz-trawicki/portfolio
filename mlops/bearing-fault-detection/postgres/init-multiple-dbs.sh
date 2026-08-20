#!/bin/bash
# Creates separate databases in the same Postgres instance for:
# - MLflow (backend store: experiments, runs, model registry)
# - Airflow (metadata DB)
# - feature_store (our feature store: the `features` table)
set -e

create_db() {
	local db=$1
	echo "Creating database: $db"
	psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
		SELECT 'CREATE DATABASE $db' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$db')\gexec
EOSQL
}

create_db "mlflow"
create_db "airflow"
create_db "feature_store"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "feature_store" <<-'EOSQL'
	CREATE TABLE IF NOT EXISTS features (
		id BIGSERIAL PRIMARY KEY,
		event_ts TIMESTAMPTZ NOT NULL DEFAULT now(),
		sensor_id TEXT NOT NULL,
		shaft_rpm DOUBLE PRECISION NOT NULL,
		fault_type TEXT,              -- label only available in simulation (ground truth)
		t_mean DOUBLE PRECISION, t_std DOUBLE PRECISION, t_rms DOUBLE PRECISION,
		t_kurtosis DOUBLE PRECISION, t_skewness DOUBLE PRECISION,
		t_peak_to_peak DOUBLE PRECISION, t_crest_factor DOUBLE PRECISION, t_shape_factor DOUBLE PRECISION,
		f_dominant_freq DOUBLE PRECISION, f_spectral_centroid DOUBLE PRECISION,
		f_spectral_energy DOUBLE PRECISION, f_spectral_entropy DOUBLE PRECISION,
		env_amp_bpfo DOUBLE PRECISION, env_amp_bpfi DOUBLE PRECISION,
		env_amp_bsf DOUBLE PRECISION, env_amp_ftf DOUBLE PRECISION
	);
	CREATE INDEX IF NOT EXISTS idx_features_event_ts ON features (event_ts);

	CREATE TABLE IF NOT EXISTS predictions (
		id BIGSERIAL PRIMARY KEY,
		event_ts TIMESTAMPTZ NOT NULL DEFAULT now(),
		sensor_id TEXT NOT NULL,
		is_anomaly BOOLEAN NOT NULL,
		predicted_fault_type TEXT,
		confidence DOUBLE PRECISION,
		model_version TEXT
	);
EOSQL

echo "Database initialization complete."
