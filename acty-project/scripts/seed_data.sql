-- seed_data.sql
-- Realistic GR86 FA24 OBD session data for Grafana dashboard development
-- Run with: docker exec -i acty-postgres psql -U acty -d acty < scripts/seed_data.sql

-- ── Vehicle ───────────────────────────────────────────────────────────────────
INSERT INTO vehicles (vehicle_id, make, model, year, engine, vin_hash) VALUES
  ('gr86-jacob-001', 'Toyota', 'GR86', 2022, 'FA24 2.4L NA', 'sha256:a3f8b2c1d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1')
ON CONFLICT (vehicle_id) DO NOTHING;

-- ── Sessions ──────────────────────────────────────────────────────────────────
INSERT INTO sessions (
  vehicle_id, filename, session_date, session_time, duration_min, sample_count,
  avg_rpm, max_rpm, avg_speed_kmh, max_speed_kmh,
  avg_coolant_c, max_coolant_c, avg_engine_load,
  ltft_b1, stft_b1, avg_timing, avg_maf,
  pct_time_moving, fuel_level_pct, battery_v, health_score,
  created_at
) VALUES
  -- Session 1: Cold start + neighborhood drive
  ('gr86-jacob-001', 'acty_obd_20260312_191256.csv', '2026-03-12', '19:12:56',
   8.2, 984, 1820, 4200, 28.4, 72.0, 72.3, 88.0, 34.2,
   1.6, -2.3, 12.4, 14.2, 61.2, 78.0, 14.2, 95,
   '2026-03-12 19:12:56+00'),

  -- Session 2: Short warmup run
  ('gr86-jacob-001', 'acty_obd_20260312_191549.csv', '2026-03-12', '19:15:49',
   3.1, 372, 1340, 2800, 18.2, 48.0, 65.1, 82.0, 28.6,
   2.1, -1.8, 10.2, 9.8, 42.0, 77.5, 14.1, 98,
   '2026-03-12 19:15:49+00'),

  -- Session 3: First neighborhood drive (good data)
  ('gr86-jacob-001', 'acty_obd_20260312_191726_firstdrive_neighborhood.csv', '2026-03-12', '19:17:26',
   22.4, 2688, 2240, 5800, 42.6, 88.0, 87.4, 95.0, 48.3,
   1.4, -3.1, 14.8, 18.6, 78.4, 76.0, 14.0, 88,
   '2026-03-12 19:17:26+00'),

  -- Session 4: Evening highway run
  ('gr86-jacob-001', 'acty_obd_20260312_200202.csv', '2026-03-12', '20:02:02',
   31.6, 3792, 3120, 6200, 86.4, 142.0, 91.2, 98.0, 72.4,
   0.8, -4.2, 18.2, 28.4, 92.8, 74.0, 13.9, 72,
   '2026-03-12 20:02:02+00'),

  -- Session 5: Morning commute
  ('gr86-jacob-001', 'acty_obd_20260313_073412.csv', '2026-03-13', '07:34:12',
   18.2, 2184, 2680, 4800, 54.2, 96.0, 84.6, 92.0, 56.8,
   1.2, -2.8, 13.6, 16.2, 82.4, 73.0, 14.1, 91,
   '2026-03-13 07:34:12+00'),

  -- Session 6: Track day warm-up laps (elevated temps)
  ('gr86-jacob-001', 'acty_obd_20260313_140822.csv', '2026-03-13', '14:08:22',
   44.8, 5376, 4820, 7200, 92.4, 168.0, 98.4, 108.0, 84.6,
   -0.4, -5.8, 22.4, 42.8, 96.4, 68.0, 13.8, 48,
   '2026-03-13 14:08:22+00'),

  -- Session 7: Post-track cooldown
  ('gr86-jacob-001', 'acty_obd_20260313_155634.csv', '2026-03-13', '15:56:34',
   12.4, 1488, 1620, 2400, 22.4, 48.0, 94.2, 102.0, 32.4,
   1.8, -2.4, 11.2, 11.4, 48.2, 67.5, 13.9, 78,
   '2026-03-13 15:56:34+00'),

  -- Session 8: Today — normal commute
  ('gr86-jacob-001', 'acty_obd_20260314_081204.csv', '2026-03-14', '08:12:04',
   24.6, 2952, 2480, 5200, 58.4, 104.0, 86.2, 94.0, 58.4,
   1.6, -3.2, 14.2, 17.8, 84.2, 66.0, 14.0, 86,
   '2026-03-14 08:12:04+00')
ON CONFLICT DO NOTHING;

-- ── Alerts ────────────────────────────────────────────────────────────────────
INSERT INTO alerts (session_id, vehicle_id, pid, label, severity, value, unit, message, created_at)
SELECT
  s.id, 'gr86-jacob-001',
  'COOLANT_TEMP', 'Coolant Temp', 'critical', 108.0, '°C',
  'Coolant temperature averaging 108.0°C — critically high, stop soon.',
  '2026-03-13 14:08:22+00'
FROM sessions s WHERE s.filename = 'acty_obd_20260313_140822.csv';

INSERT INTO alerts (session_id, vehicle_id, pid, label, severity, value, unit, message, created_at)
SELECT
  s.id, 'gr86-jacob-001',
  'ENGINE_OIL_TEMP', 'Oil Temp', 'warning', 124.0, '°C',
  'Oil temperature at 124.0°C — elevated, check oil level.',
  '2026-03-13 14:08:22+00'
FROM sessions s WHERE s.filename = 'acty_obd_20260313_140822.csv';

INSERT INTO alerts (session_id, vehicle_id, pid, label, severity, value, unit, message, created_at)
SELECT
  s.id, 'gr86-jacob-001',
  'RPM', 'RPM', 'warning', 5200.0, 'rpm',
  'RPM averaging 5200 — high RPM sustained.',
  '2026-03-13 14:08:22+00'
FROM sessions s WHERE s.filename = 'acty_obd_20260313_140822.csv';

INSERT INTO alerts (session_id, vehicle_id, pid, label, severity, value, unit, message, created_at)
SELECT
  s.id, 'gr86-jacob-001',
  'COOLANT_TEMP', 'Coolant Temp', 'warning', 102.0, '°C',
  'Coolant temperature averaging 102.0°C — running warm, monitor closely.',
  '2026-03-13 15:56:34+00'
FROM sessions s WHERE s.filename = 'acty_obd_20260313_155634.csv';

-- ── Anomaly Results ───────────────────────────────────────────────────────────
INSERT INTO anomaly_results (session_id, vehicle_id, method, anomaly_score, is_anomaly, flagged_pids, details, created_at)
SELECT
  s.id, 'gr86-jacob-001',
  'isolation_forest', 0.82, true,
  ARRAY['COOLANT_TEMP', 'ENGINE_OIL_TEMP', 'RPM'],
  '{"n_anomalies": 268, "anomaly_rate": 4.98, "total_samples": 5376}'::jsonb,
  '2026-03-13 14:08:22+00'
FROM sessions s WHERE s.filename = 'acty_obd_20260313_140822.csv';

INSERT INTO anomaly_results (session_id, vehicle_id, method, anomaly_score, is_anomaly, flagged_pids, details, created_at)
SELECT
  s.id, 'gr86-jacob-001',
  'lstm_autoencoder', 0.76, true,
  ARRAY['COOLANT_TEMP', 'ENGINE_LOAD', 'TIMING_ADVANCE'],
  '{"n_anomalies": 201, "anomaly_rate": 3.74, "total_samples": 5376}'::jsonb,
  '2026-03-13 14:08:22+00'
FROM sessions s WHERE s.filename = 'acty_obd_20260313_140822.csv';

-- Normal session anomaly result
INSERT INTO anomaly_results (session_id, vehicle_id, method, anomaly_score, is_anomaly, flagged_pids, details, created_at)
SELECT
  s.id, 'gr86-jacob-001',
  'isolation_forest', 0.12, false,
  ARRAY[]::text[],
  '{"n_anomalies": 12, "anomaly_rate": 0.44, "total_samples": 2688}'::jsonb,
  '2026-03-12 19:17:26+00'
FROM sessions s WHERE s.filename = 'acty_obd_20260312_191726_firstdrive_neighborhood.csv';

-- ── Maintenance Predictions ───────────────────────────────────────────────────
INSERT INTO maintenance_predictions (
  session_id, vehicle_id, target, label,
  health_score, stress_score, severity, confidence,
  contributing_pids, recommendation, created_at
)
SELECT
  s.id, 'gr86-jacob-001',
  'cooling_system_stress', 'Cooling System Stress',
  0.18, 0.82, 'critical', 0.88,
  ARRAY['COOLANT_TEMP', 'ENGINE_LOAD', 'RPM'],
  'Cooling system under critical stress. Inspect thermostat, water pump, and radiator immediately.',
  '2026-03-13 14:08:22+00'
FROM sessions s WHERE s.filename = 'acty_obd_20260313_140822.csv';

INSERT INTO maintenance_predictions (
  session_id, vehicle_id, target, label,
  health_score, stress_score, severity, confidence,
  contributing_pids, recommendation, created_at
)
SELECT
  s.id, 'gr86-jacob-001',
  'oil_degradation', 'Oil Degradation',
  0.32, 0.68, 'warning', 0.82,
  ARRAY['ENGINE_OIL_TEMP', 'ENGINE_LOAD', 'RPM'],
  'Oil showing elevated thermal stress. Consider oil change if approaching interval.',
  '2026-03-13 14:08:22+00'
FROM sessions s WHERE s.filename = 'acty_obd_20260313_140822.csv';

INSERT INTO maintenance_predictions (
  session_id, vehicle_id, target, label,
  health_score, stress_score, severity, confidence,
  contributing_pids, recommendation, created_at
)
SELECT
  s.id, 'gr86-jacob-001',
  'cooling_system_stress', 'Cooling System Stress',
  0.88, 0.12, 'normal', 0.92,
  ARRAY['COOLANT_TEMP', 'ENGINE_LOAD'],
  'No action required. Continue monitoring.',
  '2026-03-14 08:12:04+00'
FROM sessions s WHERE s.filename = 'acty_obd_20260314_081204.csv';

INSERT INTO maintenance_predictions (
  session_id, vehicle_id, target, label,
  health_score, stress_score, severity, confidence,
  contributing_pids, recommendation, created_at
)
SELECT
  s.id, 'gr86-jacob-001',
  'oil_degradation', 'Oil Degradation',
  0.76, 0.24, 'normal', 0.88,
  ARRAY['ENGINE_OIL_TEMP', 'RPM'],
  'No action required. Continue monitoring.',
  '2026-03-14 08:12:04+00'
FROM sessions s WHERE s.filename = 'acty_obd_20260314_081204.csv';

-- ── Diagnostic Report ─────────────────────────────────────────────────────────
INSERT INTO diagnostic_reports (
  session_id, vehicle_id, dtc_codes, anomaly_count,
  rag_query, rag_grounded, report_text, model_used, created_at
)
SELECT
  s.id, 'gr86-jacob-001',
  ARRAY['P0217']::text[], 3,
  'Toyota GR86 FA24 P0217 cooling system overtemperature diagnosis procedure',
  true,
  E'1. PRIMARY FAULT ASSESSMENT\nEngine coolant overtemperature condition detected (P0217). Coolant reached 108°C during extended high-load operation.\n\n2. LIKELY ROOT CAUSE\nSustained track-day high-RPM operation pushed cooling system beyond normal capacity. Thermostat and water pump operation should be verified per FSM Section CO-12.\n\n3. SEVERITY: High\n\n4. RECOMMENDED IMMEDIATE ACTION\nAllow engine to cool completely. Check coolant level and inspect for leaks. Verify thermostat operation before next track session.\n\n5. ESTIMATED REPAIR COMPLEXITY: Shop',
  'llama3.1:8b',
  '2026-03-13 14:08:22+00'
FROM sessions s WHERE s.filename = 'acty_obd_20260313_140822.csv';

SELECT 'Seed complete.' AS status;
SELECT COUNT(*) AS sessions   FROM sessions;
SELECT COUNT(*) AS alerts     FROM alerts;
SELECT COUNT(*) AS anomalies  FROM anomaly_results;
SELECT COUNT(*) AS predictions FROM maintenance_predictions;
SELECT COUNT(*) AS reports    FROM diagnostic_reports;
