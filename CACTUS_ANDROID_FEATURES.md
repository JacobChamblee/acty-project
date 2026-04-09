# CACTUS_APP_SPEC

## PURPOSE
- Mobile app for Acty platform
- Connects to OBD-II BLE adapters
- Captures telemetry → runs ML diagnostics → returns insights
- No data resale; user-owned data
- Free; primary user interface to backend

---

## CORE_MODULES
- Home: health, score, insights, issues, service, MPG
- NeedleNest: analytics dashboards + filtering
- Capture: live logging + tagging
- Sharing: export + links + anonymized opt-in
- Account: alerts, sync, storage, privacy
- About: mission, security, ML pipeline

---

## ONBOARDING
- Required: username, password, email
- Region: for anonymized fleet aggregation
- Vehicle: make, model, drivetrain
- Login: username/email + password reset

---

## HOME
- Health score (overall)
- Session score (efficiency, smoothness, thermal)
- Insights (top 3–5)
- Pending issues
- Service recommendation
- MPG (city/highway)
- Battery/charging (EV/hybrid)
- Quick capture trigger

---

## NEEDLENEST
Dashboards (date-range selectable):
- LTFT trend
- Anomaly timeline (Isolation Forest)
- Thermal profile (coolant, oil, catalyst)
- Voltage trend
- MPG over time
- Cross-session compare
- Seasonal baseline compare

---

## CAPTURE
- One-tap start
- Live gauges: RPM, coolant, STFT/LTFT, throttle (toggle)
- Real-time DTC alerts
- Tagging: highway, cold start, etc.
- Notes (free text)
- Storage:
  - P1: CSV + .sig
  - P2: .acty (CBOR/COSE)
- Export via USB/share

---

## SHARING
- Social: FB, IG, SMS, WhatsApp, Discord
- Verified PDF:
  - Ed25519 signed
  - RFC3161 timestamp
  - QR → verify endpoint
- Mechanic link:
  - time-limited, read-only, no account
- Export:
  - PDF/TXT
  - flexible date ranges
- Optional anonymized regional sharing

---

## ACCOUNT
- Alerts: DTC, LTFT, service, charging
- Threshold config
- Sync:
  - frequency: per-drive/daily/weekly
  - transport: WiFi/mobile
- Storage:
  - retention: 30d/90d/1yr/∞
- Email reports: daily→yearly
- Credentials mgmt
- Privacy dashboard
- Version info

---

## ABOUT
- Mission + privacy (user-encrypted, no brokerage)
- Security:
  - AES-256-GCM
  - Ed25519
  - RFC3161
  - hash-chain integrity
- ML pipeline:
  - anomaly → LSTM → XGBoost → RAG/FSM → LLM
- Verified report explanation

---

## DATA_SECURITY
Storage:
- P1: CSV + SHA256 + Ed25519 sig
- P2: CBOR/COSE (.acty):
  - AES-256-GCM
  - hash chain
  - Merkle root signed
  - RFC3161 anchor

Platform:
- Android: Keystore (TEE/StrongBox), Ed25519
- iOS: Secure Enclave, P-256 ECDSA, CoreBluetooth

---

## FEATURES_IN_PROGRESS

### HOME
- Session score (0–100)
- Battery health card
- Quick capture widget

### CAPTURE
- Live gauges
- Tagging
- Real-time DTC alerts
- Session notes

### VEHICLES
- Multi-vehicle support
- Vehicle profile:
  - metadata, mods, odometer
  - LTFT history, DTCs, service log
- OBD adapter mgmt:
  - per vehicle
  - rename + last seen

### INSIGHTS
- LTFT global trend
- Cross-session anomaly timeline
- Maintenance overlay
- Seasonal comparison

### SHARING
- Verified reports (signed + QR)
- Mechanic links (read-only, expiring)

### SETTINGS
- Privacy dashboard (stored/synced/shared)
- Retention policy
- Notification granularity

---

## ARCH_HINTS
- Mobile-first, offline-first storage
- Signed local data → optional sync
- ML pipeline external (Acty backend)
- BLE OBD-II ingestion layer required
- Strong cryptographic identity per device

---
