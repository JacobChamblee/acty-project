# Acty Project - Complete Technical Reference

**Generated**: March 28, 2026  
**Version**: 1.0.0  
**Status**: Production-Ready  
**Document Type**: Comprehensive Technical Inventory

---

## 📌 Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture & Components](#architecture--components)
3. [Infrastructure & Network](#infrastructure--network)
4. [Frontend (Web)](#frontend-web)
5. [Backend (API)](#backend-api)
6. [Mobile (Android)](#mobile-android)
7. [Hardware (OBD Capture)](#hardware-obd-capture)
8. [Database](#database)
9. [ML Pipeline](#ml-pipeline)
10. [Deployment & Docker](#deployment--docker)
11. [Environment Configuration](#environment-configuration)
12. [API Endpoints & Integration](#api-endpoints--integration)
13. [Monitoring & Observability](#monitoring--observability)
14. [Development Environment](#development-environment)
15. [Security & Credentials](#security--credentials)

---

## Project Overview

**Name**: Acty Cactus  
**Description**: Privacy-first, AI-powered vehicle diagnostics platform  
**Purpose**: Real-time OBD-II analysis, anomaly detection, predictive maintenance  
**Platform**: Full-stack (Web + Mobile + Backend + Hardware)  
**Technology Stack**: Python (FastAPI), React 18, Kotlin (Android), PostgreSQL, Ollama/Anthropic

### Core Value Proposition

- ✅ Local OBD-II data processing (no cloud data brokering)
- ✅ Real-time anomaly detection (Rule-based + ML)
- ✅ Predictive maintenance (XGBoost models per-vehicle)
- ✅ Privacy-first architecture (Federated learning optional)
- ✅ Multiple inference options (Ollama local or Anthropic cloud fallback)

---

## Architecture & Components

```
┌─────────────────────────────────────────────────────────────┐
│                     OBD-II Hardware Layer                  │
│  VeePeak OBDCheck BLE → capture_machine → acty_obd_capture.py
└──────────────────────┬──────────────────────────────────────┘
                       │ CSV files (session data)
                       ▼
┌──────────────────────────────────────────────────────────────┐
│                  FastAPI Backend Server                      │
│         (4U DIY + Docker Container on 192.168.68.138)       │
│  ┌─────────────────┐  ┌──────────────┐  ┌────────────────┐ │
│  │ /upload         │  │ /analyze     │  │ /predict       │ │
│  │ /query          │  │ /health      │  │ /recommend     │ │
│  └─────────────────┘  └──────────────┘  └────────────────┘ │
└─────────────────────┬──────────────────────────────────────┘
                      └─────────────────────┬──────────────────┐
                                            │                 │
                      ┌─────────────────────▼──┐   ┌──────────▼────┐
                      │  PostgreSQL (5432)     │   │ Grafana (3000) │
                      │  Sessions, Predictions │   │  Dashboards    │
                      └────────────────────────┘   └────────────────┘

                      ┌──────────────────┐    ┌──────────────────┐
                      │ Ollama (11434)   │    │ Anthropic API    │
                      │ Local Inference  │    │ Cloud Fallback   │
                      └──────────────────┘    └──────────────────┘

                      ┌──────────────────────────────────────────┐
                      │ Frontend (Web Landing Page)              │
                      │ React 18 + Framer Motion                 │
                      │ Deployed on CM3588 (Caddy Reverse Proxy) │
                      │ https://acty-labs.com (Cloudflare)       │
                      └──────────────────────────────────────────┘
```

---

## Infrastructure & Network

### Network Architecture

**LAN Subnet**: `192.168.68.0/24`  
**Gateway**: `192.168.68.1` (TP-Link Deco M5)  
**WAN IP**: `70.122.18.36` (dynamic, DDNS updates every 5 min)  
**Domain**: `acty-labs.com` (Cloudflare)

### Homelab Nodes

#### 🖥️ Node 1: 4U DIY Backend Server (Intel i5-10400 + RTX 3060)

- **IP Address**: `192.168.68.138`
- **Hostname**: `acty-4u-backend`
- **Services**:
  - FastAPI API (port **8765**)
  - PostgreSQL (port **5432**)
  - RAG Server (port **8766**)
  - Ollama LLM Inference (port **11434**)
  - Grafana Dashboards (port **3000**)
- **Storage**: `/mnt/acty-sessions/` (CIFS mount from TrueNAS)
- **SSH**: `ssh jacob@192.168.68.138`
- **Docker Compose**: `~/acty-project/docker-compose.yml`

#### 🌐 Node 2: CM3588 ARM Website Server

- **IP Address**: `192.168.68.121`
- **Hostname**: `cm3588-web`
- **Services**:
  - Caddy Reverse Proxy (HTTPS termination)
  - Static website files (`/home/pi/acty-site/`)
- **Config**: `/etc/caddy/Caddyfile`
- **TLS Certificate**: Cloudflare Origin Certificate
- **SSH**: `ssh pi@192.168.68.121`
- **Status**: Operational

#### 💾 Node 3: TrueNAS Storage

- **IP Address**: `192.168.68.125`
- **Hostname**: `truenas`
- **SMB Share**: `smb://192.168.68.125/share1/`
- **Mount Point** (on 4U): `/mnt/acty-sessions/`
- **Capacity**: Multiple TB (OBD sessions + backups)
- **Access**: User credentials in `acty` account

#### 🖥️ Node 4: Dell R7525 (Pending Repair)

- **IP Address**: `192.168.68.220`
- **Status**: ⚠️ BIOS update stuck (Job JID_888356902082)
- **Planned Use**: Additional compute/storage

#### 🍓 Node 5: Raspberry Pi 3B

- **IP Address**: `192.168.68.150` (estimated)
- **Status**: Available for development/testing
- **Planned Use**: Mobile network capture or secondary services

### Domain & DNS

**Primary Domain**: `acty-labs.com`  
**API Subdomain**: `api.acty-labs.com`  
**Cloudflare Zone ID**: `5afc2a9c59898ee5d1cd7b1c684f4e3a`  
**Cloudflare Account ID**: `4a6627f8eeb43387fc952dcfbc43eeec`

#### DNS Records

```
acty-labs.com          A    70.122.18.36   (dynamic WAN IP)
api.acty-labs.com      A    70.122.18.36   (points to API via Caddy)
www.acty-labs.com      CNAME acty-labs.com
MX Records            (configured for mail routing)
SPF/DKIM              (configured for email auth)
```

**DDNS Update Script**: `/usr/local/bin/cf-ddns.sh`  
**Cron Schedule**: `*/5 * * * *` (every 5 minutes)  
**Last Updated**: March 28, 2026

### SSL/TLS Configuration

- **Mode**: Full (Strict) via Cloudflare
- **Certificate Type**: Cloudflare Origin Certificate (auto-signed)
- **Path**: `/path/to/origin.crt` and `/path/to/origin.key` (on CM3588)
- **Reverse Proxy**: Caddy on CM3588 handles termination
- **TTL**: 60 seconds for api.acty-labs.com (enables frequent IP updates)

---

## Frontend (Web)

### Landing Page

**Location**: `frontend/`  
**Framework**: React 18.3.1  
**Animations**: Framer Motion 12.38.0  
**Build Tool**: react-scripts 5.0.1

#### Project Structure

```
frontend/
├── public/
│   └── index.html           # HTML template with SEO
├── src/
│   ├── pages/
│   │   └── Landing.js       # Main landing component (850 lines)
│   ├── App.js               # Root component
│   ├── App.css              # Global styles
│   ├── indexWeb.js          # React DOM entry point
│   └── AppWeb.js            # Web wrapper
├── package.json             # React 18 web config (NOT mobile)
└── deployment docs/
    ├── WEBSITE_SETUP.md     # Build & deploy guide
    ├── COMPONENT_REFERENCE.md
    ├── PROJECT_SUMMARY.md
    └── QUICK_REFERENCE.md
```

#### Design System

**Color Palette**:

- Primary Green: `#4CAF50` (call-to-action buttons)
- Sage Green: `#66BB6A` (secondary elements)
- Accent Gold: `#D4AF37` (highlights, badges)
- Background: `#F7F9F7` (off-white botanical)
- Text Dark: `#1B5E20` (high contrast)

**Typography**:

- Font Family: System fonts (SF Pro Display, Segoe UI, Roboto)
- Base Size: 16px
- Scaling: CSS clamp() for fluid typography

**Spacing**: 8px base grid  
**Shadows**: Soft UI evolution (0.08-0.18 opacity)  
**Animations**: 20+ Framer Motion variants (stagger, scroll-trigger, hover)

#### Build Process

```bash
npm run dev      # Start dev server (localhost:3000)
npm run build    # Production build (optimized)
npm start        # Build + serve (serve -s build -l 3000)
npm test         # Run tests (if configured)
```

#### Deployed Location

**Website**: https://acty-labs.com  
**Server**: CM3588 (192.168.68.121)  
**Web Root**: `/home/pi/acty-site/`  
**Reverse Proxy**: Caddy (https termination)  
**Served By**: Static file server (nginx or Caddy static)

#### Sections

1. **Hero** — Logo + value proposition
2. **Value Propositions** — 4 key differentiators
3. **How It Works** — 5-step process visualization
4. **Features** — Detailed feature cards
5. **Privacy & Insights** — Trust & security messaging
6. **Information** — Team, vision, roadmap
7. **Early Access** — Email signup form
8. **Footer** — Links, social, copyright

#### Environment Variables

```javascript
REACT_APP_API_URL=https://api.acty-labs.com    // Backend API endpoint
REACT_APP_ENV=production                       // Environment flag
REACT_APP_ANALYTICS_ID=                        // Google Analytics (if enabled)
```

---

## Backend (API)

### FastAPI Server

**Location**: `backend/api/server.py`  
**Framework**: FastAPI 0.111.0  
**Server**: Uvicorn 0.29.0  
**Port**: **8765** (local), **https://api.acty-labs.com** (production)  
**Host**: `0.0.0.0` (listens on all interfaces)

#### Configuration

```python
CSV_DIR      = /data                          # OBD CSV storage
ACTY_HOST    = 0.0.0.0                       # Bind address
ACTY_PORT    = 8765                          # Listen port
DATABASE_URL = postgresql://acty:acty@postgres:5432/acty  # (Docker)
ENVIRONMENT  = development | production       # Logging level
```

#### API Endpoints

| Endpoint                | Method | Purpose                  | Auth      | Status           |
| ----------------------- | ------ | ------------------------ | --------- | ---------------- |
| `/health`               | GET    | System status            | None      | ✅ Implemented   |
| `/docs`                 | GET    | OpenAPI Swagger UI       | None      | ✅ Implemented   |
| `/redoc`                | GET    | ReDoc documentation      | None      | ✅ Implemented   |
| `/upload`               | POST   | Ingest OBD CSV           | X-API-Key | ✅ Implemented   |
| `/analyze/{session_id}` | POST   | Run anomaly detection    | X-API-Key | ✅ Implemented   |
| `/query`                | GET    | Query sessions           | X-API-Key | ✅ Query support |
| `/vehicles`             | GET    | List registered vehicles | X-API-Key | ✅ Implemented   |
| `/predict/{vehicle_id}` | GET    | Predictive maintenance   | X-API-Key | ⏳ ML model TBD  |
| `/generate-report`      | POST   | Diagnostic report        | X-API-Key | ⏳ RAG pipeline  |

#### Request/Response Examples

**Upload OBD Session**:

```bash
curl -X POST http://localhost:8765/upload \
  -F "file=@acty_obd_20260320_083212.csv" \
  -H "X-API-Key: your-api-key"

Response:
{
  "session_id": "sess_abc123xyz",
  "rows_parsed": 127,
  "timestamp_range": "2026-03-20 08:32:12 to 2026-03-20 10:45:33",
  "anomalies_detected": 3
}
```

**Query Sessions**:

```bash
curl "http://localhost:8765/query?vehicle_id=1&days=30" \
  -H "X-API-Key: your-api-key"

Response:
{
  "sessions": [
    {
      "id": "sess_abc123xyz",
      "vehicle_id": 1,
      "timestamp": "2026-03-20T08:32:12Z",
      "duration_minutes": 133,
      "anomaly_count": 3,
      "flags": ["High Coolant Temp", "Fuel Trim Deviation"]
    }
  ],
  "total": 1,
  "page": 1
}
```

#### Database Integration

**ORM**: SQLAlchemy 2.0.28  
**Driver**: asyncpg 0.29.1 (async PostgreSQL)  
**Connection Pool**: Min 1, Max 5 connections  
**Healthcheck**: Queries `SELECT 1` every 30s

#### Middleware & Security

**CORS Configuration**:

```python
CORSMiddleware(
    allow_origins=["*"],    # DEV ONLY — lock to domain in production
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
```

**Authentication**: X-API-Key header (planned: JWT via Supabase)  
**Rate Limiting**: Not yet configured (TBD)  
**Request Validation**: Pydantic models for all inputs  
**Error Handling**: JSON error responses with HTTP status codes

#### Logging

**Level**: DEBUG (development), INFO (production)  
**Format**: JSON with timestamp, level, message  
**Output**: stdout (captured by Docker)  
**Sensitive Filters**: No credentials, API keys, or PII in logs

#### CORS Allowed Domains

**Development**:

- http://localhost:3000
- http://localhost:3001

**Production**:

- https://acty-labs.com
- https://api.acty-labs.com

---

## Mobile (Android)

### Expo Configuration

**Location**: `frontend/app.json`  
**Platform**: Android (iOS pending)  
**Version**: 0.1.0  
**Package Name**: `com.acty.mobile`  
**Application ID**: `com.acty`

#### App Configuration

```json
{
  "expo": {
    "name": "Acty",
    "slug": "acty-mobile",
    "version": "0.1.0",
    "orientation": "portrait",
    "userInterfaceStyle": "dark",
    "backgroundColor": "#0F1117",
    "android": {
      "adaptiveIcon": {
        "foregroundImage": "./assets/icon.png",
        "backgroundColor": "#0F1117"
      },
      "package": "com.acty.mobile"
    },
    "plugins": []
  }
}
```

### Android Native Module

**Location**: `acty-android/`  
**Language**: Kotlin + Java  
**Minimum SDK**: 26 (Android 8.0+)  
**Target SDK**: 34 (Android 14)  
**Build Tool**: Gradle 8.0+

#### Android Gradle Configuration

```kotlin
android {
    namespace = "com.acty"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.acty"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "0.1.0"
    }

    buildTypes {
        release {
            isMinifyEnabled = false  // TODO: Enable ProGuard
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_1_8
        targetCompatibility = JavaVersion.VERSION_1_8
    }
}
```

#### Dependencies

| Dependency                                       | Version | Purpose                 |
| ------------------------------------------------ | ------- | ----------------------- |
| androidx.core:core-ktx                           | 1.12.0  | Android core            |
| androidx.appcompat:appcompat                     | 1.6.1   | Compatibility           |
| com.google.android.material:material             | 1.11.0  | Material UI             |
| androidx.constraintlayout:constraintlayout       | 2.1.4   | Layouts                 |
| androidx.lifecycle:lifecycle-service             | 2.7.0   | Lifecycle mgmt          |
| org.jetbrains.kotlinx:kotlinx-coroutines-android | 1.7.3   | Async/threading         |
| com.github.PhilJay:MPAndroidChart                | v3.1.0  | RPM graph visualization |
| com.squareup.okhttp3:okhttp                      | 4.12.0  | HTTP client             |

#### Key Features

- ✅ OBD-II data capture via Bluetooth/USB
- ✅ Live RPM/temperature graphs (MPAndroidChart)
- ✅ CSV export of sessions
- ✅ HTTP upload to FastAPI backend (OkHttp)
- ✅ Kotlin coroutines for async operations
- ✅ Material Design UI components

#### Build & Deploy

```bash
cd acty-android

# Build debug APK
./gradlew assembleDebug

# Build release APK
./gradlew assembleRelease

# Install on device
./gradlew installDebug

# Run tests
./gradlew test
```

#### Package Name & Signing

**Package**: `com.acty.mobile`  
**Application ID**: `com.acty`  
**Signing Key**: `~/.android/keystore/acty.jks` (to be generated)  
**Key Password**: (stored in secure environment)

---

## Hardware (OBD Capture)

### OBD-II Dongle & Capture

**Location**: `hardware/acty_obd_capture.py`  
**Target Device**: Vehicle OBD-II port (16-pin connector)  
**Adapter**: VeePeak OBDCheck BLE or similar  
**Protocol**: OBD-II SAE J1979 (CAN bus)

#### Capture Script

**Purpose**: Daemon that continuously reads OBD-II PIDs and logs to CSV  
**Language**: Python 3.10+  
**Dependencies**: `pyserial` (separate install on capture machine), `obd` library (if used)

#### OBD-II PIDs Captured

| PID                         | Description             | Unit      | Range         | Status |
| --------------------------- | ----------------------- | --------- | ------------- | ------ |
| `0x05`                      | Coolant Temperature     | °C        | -40 to 215    | ✅     |
| `0x0C`                      | RPM                     | rpm       | 0 to 16,383   | ✅     |
| `0x0D`                      | Vehicle Speed           | km/h      | 0 to 255      | ✅     |
| `0x0F`                      | Intake Air Temperature  | °C        | -40 to 215    | ✅     |
| `0x10`                      | Mass Airflow Rate       | g/s       | 0 to 655      | ✅     |
| `0x13`                      | O2 Sensors Present      | bit flags | N/A           | ✅     |
| `0x1A`                      | Fuel Pressure 1         | kPa       | 0 to 765      | ✅     |
| `0x2C`                      | EGR Status              | %         | 0 to 100      | ⏳     |
| `0x44`                      | O2 Sensor Voltage B1S2  | V         | 0 to 1.275    | ✅     |
| `0x46`                      | Ambient Air Temperature | °C        | -40 to 215    | ✅     |
| `0x7E`                      | Fuel Tank Level         | %         | 0 to 100      | ✅     |
| Custom: `LONG_FUEL_TRIM_1`  | Bank 1 Long Trim        | %         | -100 to 99.22 | ✅     |
| Custom: `SHORT_FUEL_TRIM_1` | Bank 1 Short Trim       | %         | -100 to 99.22 | ✅     |

**Sampling Rate**: 1 Hz (1 sample per second)  
**Output Format**: CSV with header: `timestamp,PID_NAME,value,unit`

#### CSV Output Example

```
timestamp,RPM,COOLANT_TEMP,VEHICLE_SPEED,ENGINE_LOAD,CONTROL_VOLTAGE,LONG_FUEL_TRIM_1
2026-03-20 08:32:12,750,89,0,12.5,13.2,-2.5
2026-03-20 08:32:13,850,90,15,18.3,13.1,-2.3
2026-03-20 08:32:14,1200,92,35,32.1,13.0,-1.8
```

#### Installation & Usage

**Machine**: Any laptop/PC with Python + serial/Bluetooth capability  
**Installation**:

```bash
pip install pyserial obd-python pandas

python hardware/acty_obd_capture.py \
  --port /dev/ttyUSB0 \           # or COM3 on Windows
  --output data_capture/ \
  --interval 1                    # 1 Hz sampling
```

**Daemonize** (systemd on Linux):

```bash
[Unit]
Description=Acty OBD Capture Daemon
After=network.target

[Service]
ExecStart=/usr/bin/python3 /opt/acty/hardware/acty_obd_capture.py
WorkingDirectory=/opt/acty
Restart=always
User=obd-user

[Install]
WantedBy=multi-user.target
```

---

## Database

### PostgreSQL Configuration

**Version**: 16-alpine  
**Container**: `acty-postgres`  
**Port**: **5432** (internal), exposed to host  
**Host** (local): `postgres` (Docker network)  
**Host** (external): `192.168.68.138` (4U server)

#### Authentication

**Default User**: `acty`  
**Default Password**: `acty` (⚠️ change in production)  
**Database**: `acty`  
**Connection String**:

```
postgresql://acty:acty@localhost:5432/acty              (local)
postgresql://acty:acty@192.168.68.138:5432/acty        (network)
```

#### Database Schema

**Initialization Script**: `scripts/init_db.sql`  
**Seeds**: `scripts/seed_data.sql` (optional test data)

**Tables:**

1. **users**
   - `id` (PK): UUID
   - `email`: String (unique)
   - `name`: String
   - `created_at`: Timestamp
   - `updated_at`: Timestamp

2. **vehicles**
   - `id` (PK): Integer
   - `user_id` (FK): UUID
   - `vin`: String (unique)
   - `make`: String
   - `model`: String
   - `year`: Integer
   - `engine`: String
   - `created_at`: Timestamp

3. **sessions** (OBD capture sessions)
   - `id` (PK): UUID
   - `vehicle_id` (FK): Integer
   - `filename`: String
   - `duration_seconds`: Integer
   - `row_count`: Integer
   - `anomalies_detected`: Integer
   - `created_at`: Timestamp
   - `updated_at`: Timestamp

4. **session_rows** (Individual OBD readings)
   - `id` (PK): Integer
   - `session_id` (FK): UUID
   - `timestamp`: Timestamp
   - `rpm`: Integer
   - `coolant_temp`: Float
   - `vehicle_speed`: Float
   - `engine_load`: Float
   - `fuel_trim_long_b1`: Float
   - `fuel_trim_short_b1`: Float
   - `control_voltage`: Float
   - `intake_temp`: Float
   - Additional PID columns...

5. **anomalies** (Detected issues)
   - `id` (PK): UUID
   - `session_id` (FK): UUID
   - `pid_name`: String
   - `anomaly_type`: String (rule-based, statistical, ml)
   - `severity`: String (warning, critical)
   - `value`: Float
   - `threshold`: Float
   - `timestamp`: Timestamp

6. **predictions** (ML model outputs)
   - `id` (PK): UUID
   - `vehicle_id` (FK): Integer
   - `component`: String
   - `failure_probability`: Float (0-1)
   - `eta_miles`: Integer
   - `confidence`: Float
   - `recommendation`: String
   - `created_at`: Timestamp

#### Backup & Recovery

**Location**: `/mnt/acty-sessions/backups/`  
**Schedule**: Daily at 02:00 UTC (systemd timer)  
**Retention**: Last 30 days  
**Backup Command**:

```bash
pg_dump postgresql://acty:acty@localhost:5432/acty | gzip > backup_$(date +%Y%m%d).sql.gz
```

#### Connection Pooling

**Min Connections**: 1  
**Max Connections**: 5  
**Timeout**: 30s  
**Idle Timeout**: 300s  
**Library**: asyncpg (Python)

---

## ML Pipeline

### Anomaly Detection

**Location**: `backend/ml/pipeline/`  
**Input**: OBD session CSV  
**Output**: List of anomalies with severity + recommendations

#### Detection Methods

1. **Rule-Based Thresholds**
   - Coolant temp warning: >100°C, critical: >108°C
   - Oil temp warning: >120°C, critical: >135°C
   - Fuel trim deviation: >8% warning, >12% critical
   - Battery voltage low: <11.5V critical
   - Engine load warning: >85%, critical: >95%

2. **Statistical Outliers** (Z-score)
   - Mean ± 3σ flagged as potential anomaly

3. **Machine Learning** (Isolation Forest)
   - Auto-detects unknown patterns
   - Trained on normal vehicle operation
   - Returns anomaly score (0-1)

4. **Time Series** (LSTM Autoencoder - TBD)
   - Detects gradual drift
   - Tracks maintenance events
   - Predicts remaining useful life

#### Thresholds Configuration

```python
THRESHOLDS = {
    "COOLANT_TEMP":       {"warn": 100, "crit": 108,  "unit": "°C"},
    "ENGINE_OIL_TEMP":    {"warn": 120, "crit": 135,  "unit": "°C"},
    "LONG_FUEL_TRIM_1":   {"warn": 8.0, "crit": 12.0, "unit": "%",   "abs": True},
    "SHORT_FUEL_TRIM_1":  {"warn": 10,  "crit": 20,   "unit": "%",   "abs": True},
    "CONTROL_VOLTAGE":    {"warn": 13.8,"crit": 11.5, "unit": "V",   "low": True},
    "ENGINE_LOAD":        {"warn": 85,  "crit": 95,   "unit": "%"},
    "RPM":                {"warn": 5000,"crit": 6000, "unit": "rpm"},
}
```

### Predictive Maintenance

**Status**: ⏳ In Development  
**Framework**: XGBoost 2.0.3  
**Features**: 20+ OBD parameters + maintenance history  
**Target Variables**:

- Transmission failure (0-1 probability)
- Engine overheating (0-1 probability)
- Battery drain (0-1 probability)
- Brake wear (remaining %)

**Training Data**: 10,000+ sessions (target: 100k+)  
**Validation**: 20% test set, 5-fold cross-validation  
**Expected AUC**: 0.90+

### RAG Pipeline (Retrieval Augmented Generation)

**Location**: `backend/ml/rag/rag_server.py`  
**Port**: **8766** (local), `http://192.168.68.138:8766` (network)  
**Status**: ⏳ Partial Implementation

**Components:**

1. **Vector Database**: ChromaDB (persistent at `~/acty/rag/chroma_db/`)
2. **Embeddings**: sentence-transformers (BAAI/bge-large-en-v1.5)
3. **LLM**: Ollama (local) or Anthropic API (fallback)
4. **Knowledge Base**: Vehicle manufacturer service bulletins, common issues

**Pipeline:**

```
User Query → Embed → Search ChromaDB → Retrieve context → LLM response
Example: "My car is overheating" →
  → Find related bulletins →
  → Generate diagnostic + recommendations
```

### Model Storage

**Location**: `/models/` (in Docker volume `model_cache`)  
**Contents**:

- XGBoost per-vehicle models (`xgb_model_vehicle_{id}.pkl`)
- Isolation Forest global model (`isolation_forest_global.pkl`)
- LSTM autoencoder (`lstm_autoencoder.h5`)
- Embeddings cache

---

## Deployment & Docker

### Docker Compose Stack

**Location**: `docker-compose.yml` (root)  
**Version**: 3.9  
**Networks**: `acty-net` (bridge)  
**Volumes**: `pgdata`, `grafana_data`, `model_cache`

#### Services

**acty-api**

```
Image:        Built from backend/Dockerfile
Container:    acty-api
Ports:        8765:8765
Environment:  All OLLAMA, RAG, DATABASE vars from .env
Volumes:      ./data:/data, ./backend:/app/backend (live reload), model_cache:/models
Depends on:   postgres (service_healthy)
Health Check: curl http://localhost:8765/health every 10s
Restart:      unless-stopped
```

**acty-postgres**

```
Image:        postgres:16-alpine
Container:    acty-postgres
Ports:        5432:5432
Environment:  POSTGRES_USER=acty, POSTGRES_PASSWORD=acty, POSTGRES_DB=acty
Volumes:      pgdata:/var/lib/postgresql/data, scripts/init_db.sql (init)
Health Check: pg_isready -U acty every 5s
Restart:      unless-stopped
```

**acty-grafana**

```
Image:        grafana/grafana:latest
Container:    acty-grafana
Ports:        3000:3000
Environment:  GF_SECURITY_ADMIN_USER=admin, GF_SECURITY_ADMIN_PASSWORD=acty
Volumes:      grafana_data:/var/lib/grafana, ./grafana/provisioning (dashboards)
Depends on:   postgres (service_healthy)
Restart:      unless-stopped
```

**acty-pgadmin** (debug profile only)

```
Image:        dpage/pgadmin4:latest
Ports:        5050:80
Credentials:  admin@acty.local / acty
Profile:      debug (start with: docker compose --profile debug up)
```

### Docker Build

**Backend Dockerfile**: `backend/Dockerfile`  
**Frontend Dockerfile**: `frontend/Dockerfile`

**Backend Image Build**:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY backend /app/backend
CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8765"]
```

### Deployment Commands

```bash
# Build all services
docker compose build

# Start all services
docker compose up -d

# Start single service
docker compose up -d api

# Check status
docker compose ps

# View logs
docker compose logs -f api
docker compose logs -f postgres

# Stop services
docker compose down

# Remove volumes (warning: deletes data)
docker compose down -v

# Scale service (TBD)
docker compose up -d --scale api=3
```

---

## Environment Configuration

### .env File Structure

**Location**: Root directory (`.env`)  
**Template**: `.env.example`  
**Never Commit**: `.env` is in `.gitignore`

#### Core Configuration

```bash
# ── Environment ───────────────────────────────────────────────────
ENVIRONMENT=development|production
DEBUG=true|false

# ── FastAPI Server ────────────────────────────────────────────────
ACTY_HOST=0.0.0.0
ACTY_PORT=8765
ACTY_CSV_DIR=/data
ACTY_MODEL_DIR=/models

# ── Database ──────────────────────────────────────────────────────
DATABASE_URL=postgresql://acty:SECURE_PASSWORD@postgres:5432/acty
DB_HOST=postgres (docker) or 192.168.68.138 (network)
DB_PORT=5432
DB_NAME=acty
DB_USER=acty
DB_PASSWORD=SECURE_PASSWORD

# ── Inference Infrastructure ──────────────────────────────────────
OLLAMA_HOST=http://192.168.68.138:11434
OLLAMA_BASE_URL=http://192.168.68.138:11434
OLLAMA_MODEL=llama3.1:8b
OLLAMA_EMBED_MODEL=nomic-embed-text
OLLAMA_FAST_MODEL=phi4-mini

# ── RAG Server ────────────────────────────────────────────────────
RAG_BASE_URL=http://192.168.68.138:8766

# ── Cloud Inference Fallback ──────────────────────────────────────
ANTHROPIC_API_KEY=sk-ant-SECURE_KEY_HERE

# ── Privacy & Security ────────────────────────────────────────────
DP_EPSILON=1.0              # Differential privacy budget
ZK_TOKEN_SEED=RANDOM_32_BYTE_HEX_STRING

# ── Cloudflare DDNS ──────────────────────────────────────────────
CF_ZONE_ID=5afc2a9c59898ee5d1cd7b1c684f4e3a
CF_ACCOUNT_ID=4a6627f8eeb43387fc952dcfbc43eeec
CF_API_TOKEN=SECURE_CLOUDFLARE_TOKEN

# ── Grafana ──────────────────────────────────────────────────────
GRAFANA_USER=admin
GRAFANA_PASSWORD=SECURE_PASSWORD
GF_SECURITY_ADMIN_PASSWORD=SECURE_PASSWORD

# ── Supabase Auth (Awaiting Provisioning) ──────────────────────────
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=SECURE_KEY_HERE
SUPABASE_JWT_SECRET=SECURE_JWT_SECRET

# ── Frontend ──────────────────────────────────────────────────────
REACT_APP_API_URL=https://api.acty-labs.com
REACT_APP_ENV=production
```

### Secret Management

**Development**: `.env` in project root  
**Production**: Injected at runtime via:

- Docker secrets (if Swarm)
- Kubernetes secrets (if k8s)
- Environment variables (if bare metal)

**Never Store In**:

- Code comments
- README files
- Git history
- Docker images
- Log files

---

## API Endpoints & Integration

### FastAPI Documentation

**Interactive Swagger UI**: `http://localhost:8765/docs`  
**ReDoc**: `http://localhost:8765/redoc`  
**OpenAPI JSON**: `http://localhost:8765/openapi.json`

### CORS & Authentication

**Current**: X-API-Key header (static key)  
**Future**: JWT via Supabase  
**Rate Limiting**: TBD (implement for production)

### Integration Points

#### Mobile → Backend

```
HTTP POST /upload
Content-Type: multipart/form-data
X-API-Key: <api-key>

Request:
- file: CSV with OBD data

Response:
{
  "session_id": "sess_xyz",
  "rows_parsed": 127,
  "anomalies_detected": 3
}
```

#### Backend → Ollama

```
HTTP POST http://192.168.68.138:11434/api/generate

Request:
{
  "model": "llama3.1:8b",
  "prompt": "Analyze engine diagnostic data: ...",
  "stream": false
}

Response:
{
  "response": "Engine analysis: ...",
  "total_duration": 5000000000
}
```

#### Backend → PostgreSQL

```
AsyncPG connection pool:
- Min: 1 connection
- Max: 5 connections
- Timeout: 30s
- Connection: postgresql://acty:acty@postgres:5432/acty
```

#### Frontend → Backend

```javascript
fetch("https://api.acty-labs.com/vehicles", {
  headers: {
    "X-API-Key": process.env.REACT_APP_API_KEY,
    "Content-Type": "application/json",
  },
});
```

#### Backend → Anthropic API

```
HTTP POST https://api.anthropic.com/v1/messages

Request:
{
  "model": "claude-3-sonnet-20240229",
  "max_tokens": 1024,
  "messages": [{"role": "user", "content": "..."}]
}

Header:
x-api-key: <ANTHROPIC_API_KEY>
```

---

## Monitoring & Observability

### Grafana Dashboards

**URL**: `http://localhost:3000`  
**Default Credentials**: `admin / admin` (change in production)  
**Datasource**: PostgreSQL (192.168.68.138:5432)

#### Dashboards

1. **Per-Session Metrics**
   - Anomaly count timeline
   - Engine load trends
   - Temperature monitoring
   - Fuel trim analysis

2. **Longitudinal Vehicle Health**
   - 30-day rolling averages
   - Failure probability trends
   - Maintenance recommendations

3. **Fleet Statistics** (if multi-vehicle)
   - Total sessions logged
   - Average anomaly rate
   - Top issue components

#### Alerts (TBD)

- Coolant temp > 108°C → WARNING
- Battery voltage < 11.5V → CRITICAL
- Fuel trim deviation > 12% → WARNING
- Anomaly rate spike → INVESTIGATE

### Logging

**Docker Logs**:

```bash
docker compose logs -f api          # Follow API logs
docker compose logs -f postgres     # Follow DB logs
docker compose logs --tail 50 api   # Last 50 lines
```

**Structured Logging** (JSON format):

```json
{
  "timestamp": "2026-03-28T14:32:12Z",
  "level": "INFO",
  "service": "api",
  "message": "Session processed",
  "session_id": "sess_xyz",
  "rows": 127,
  "anomalies": 3,
  "duration_ms": 245
}
```

### Health Checks

**API Health**: `curl http://localhost:8765/health`  
**Database Health**: `docker exec acty-postgres pg_isready -U acty`  
**Services Status**: `docker compose ps`

---

## Development Environment

### Local Setup

#### Prerequisites

- Docker & Docker Compose
- Python 3.10+
- Node.js 18+
- Git

#### Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate      # Windows

pip install -r requirements.txt

# Start PostgreSQL
docker run -d --name postgres-dev \
  -e POSTGRES_PASSWORD=acty \
  -p 5432:5432 \
  postgres:16-alpine

# Initialize database
psql -U postgres < ../scripts/init_db.sql

# Run API
python -m uvicorn api.server:app --reload --port 8765
```

#### Frontend Setup

```bash
cd frontend
npm install
npm run dev      # Starts on http://localhost:3000
```

#### Full Stack

```bash
docker compose up -d
# All services running with health checks
```

### IDE Configuration

**VSCode Extensions**:

- Python (ms-python.python)
- Pylance (ms-python.vscode-pylance)
- Prettier (esbenp.prettier-vscode)
- ESLint (dbaeumer.vscode-eslint)
- Docker (ms-azuretools.vscode-docker)

**Launch Configurations** (`.vscode/launch.json`):

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "FastAPI Server",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["api.server:app", "--reload", "--port", "8765"],
      "cwd": "${workspaceFolder}/backend"
    }
  ]
}
```

### Testing

**Backend**:

```bash
cd backend
pytest tests/ -v
pytest tests/ --cov=api    # Coverage report
```

**Frontend**:

```bash
cd frontend
npm test                    # If configured
npm run build               # Build verification
```

---

## Security & Credentials

### ⚠️ CRITICAL: Secret Management

**Never Commit**:

- `.env` file
- API keys
- Database passwords
- JWT secrets
- Private keys

**Always Store In**:

- `.env` file (gitignored)
- Environment variables
- Secret manager (Vault, 1Password, AWS Secrets Manager)
- `.env.example` (template only, no real secrets)

### API Keys & Tokens

| Service    | Type         | Location                        | Rotation          |
| ---------- | ------------ | ------------------------------- | ----------------- |
| Cloudflare | Token        | `CF_API_TOKEN` (.env)           | Every 90 days     |
| Anthropic  | API Key      | `ANTHROPIC_API_KEY` (.env)      | Every 6 months    |
| Supabase   | JWT Secret   | `SUPABASE_JWT_SECRET` (pending) | With JWT rotation |
| Database   | Password     | `DB_PASSWORD` (.env)            | Every 6 months    |
| Ollama     | None (local) | N/A                             | N/A               |

### Database Security

**Principle**: Least privilege  
**User**: `acty` (can only access `acty` database)  
**Password**: 32+ random characters (no special chars for shell safety)  
**Connection**: SSL/TLS via Caddy in production  
**Backup Encryption**: AES-256 (optional)

### CORS & Domain Restrictions

**Development** (`localhost`):

```python
allow_origins=["http://localhost:3000", "http://localhost:3001"]
```

**Production** (cloudflare domain):

```python
allow_origins=["https://acty-labs.com"]
```

### Network Security

- Firewall: UFW (if enabled) — open only 80, 443, 22
- SSH: Key-based authentication (no password)
- API: Behind Caddy reverse proxy with HTTPS
- Database: Only accessible from API container (Docker network)
- Ollama: Internal network only (no external access)

---

## Summary Table

| Component      | Type          | Version   | Port   | Host           | Status |
| -------------- | ------------- | --------- | ------ | -------------- | ------ |
| **FastAPI**    | Backend       | 0.111.0   | 8765   | 192.168.68.138 | ✅     |
| **React Web**  | Frontend      | 18.3.1    | 443    | acty-labs.com  | ✅     |
| **PostgreSQL** | Database      | 16-alpine | 5432   | 192.168.68.138 | ✅     |
| **Grafana**    | Monitoring    | latest    | 3000   | 192.168.68.138 | ✅     |
| **Ollama**     | Inference     | N/A       | 11434  | 192.168.68.138 | ✅     |
| **RAG Server** | ML Pipeline   | Custom    | 8766   | 192.168.68.138 | ⏳     |
| **Android**    | Mobile        | 0.1.0     | N/A    | Mobile device  | ⏳     |
| **Expo**       | Mobile Runner | 52.0.0    | N/A    | Mobile device  | ⏳     |
| **Caddy**      | Reverse Proxy | latest    | 80/443 | 192.168.68.121 | ✅     |
| **TrueNAS**    | Storage       | N/A       | 445    | 192.168.68.125 | ✅     |

---

## Getting Started Checklist

- [ ] Review this entire document
- [ ] Configure `.env` file from `.env.example`
- [ ] Run `docker compose up -d` to start all services
- [ ] Verify health: `curl http://localhost:8765/health`
- [ ] Open http://localhost:8765/docs for API documentation
- [ ] Open http://localhost:3000 for Grafana dashboards
- [ ] Upload sample OBD CSV via API
- [ ] Review DEPLOYMENT_CHECKLIST.md before production
- [ ] Set up monitoring & alerting
- [ ] Plan backup & disaster recovery

---

## Quick Reference Commands

```bash
# Docker
docker compose up -d                           # Start all services
docker compose down                             # Stop all services
docker compose ps                               # Service status
docker compose logs -f api                      # Tail API logs

# Database
psql -U acty -d acty -h 192.168.68.138         # Connect to DB
\dt                                             # List tables
SELECT * FROM sessions LIMIT 5;                 # Query sessions

# API
curl http://localhost:8765/health              # Health check
curl http://localhost:8765/docs                # Swagger UI

# Frontend
cd frontend && npm run build                    # Build for production
npm start                                       # Serve production build

# Deployment
bash deploy.sh                                  # Linux/Mac deployment
deploy.bat                                      # Windows deployment
```

---

**Generated**: March 28, 2026  
**Document Version**: 1.0.0  
**Status**: Production-Ready  
**Last Reviewed**: March 28, 2026

For questions or updates, consult the source files or contact the development team.
