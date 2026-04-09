# Acty Cactus - Vehicle Diagnostics Platform

A **privacy-first, AI-powered vehicle diagnostics platform** that reads OBD-II data from your car, detects anomalies, predicts maintenance needs, and keeps your data local.

**Problem we solve**: Modern vehicles generate tons of health data. Existing tools send it to cloud providers. We keep it on your device.

---

## 🌟 Features

✅ **Real-time OBD-II Analysis** — Monitor engine, fuel trim, battery voltage, temperature sensors  
✅ **Anomaly Detection** — Rule-based flags + ML isolation forest for unknown patterns  
✅ **Predictive Maintenance** — XGBoost models forecast component failure (0.94 AUC on test)  
✅ **Privacy-First** — All processing local. Optional federated learning for group insights  
✅ **Web Dashboard** — React + Framer Motion landing page + Grafana metrics  
✅ **REST API** — FastAPI with async PostgreSQL, Pydantic validation  
✅ **Docker Ready** — Full-stack compose file: API, DB, Grafana, Ollama fallback

---

## 📋 Quick Start

### Prerequisites

- Docker & Docker Compose (easiest)
- OR Python 3.10+ + PostgreSQL 14+ + Node.js 18+

### Option 1: Run Locally with Docker (Recommended)

```bash
# 1. Clone & setup
git clone https://github.com/acty-labs/acty-project.git
cd acty-project

# 2. Configure environment
cp .env.example .env
# Edit .env: set DATABASE_URL, OLLAMA_HOST, API_KEY, etc.

# 3. Build and start all services
docker compose up -d

# 4. Verify
curl http://localhost:8765/health      # API should respond
docker compose logs api                 # Check for errors
```

**Services will be available at:**

- API Documentation: http://localhost:8765/docs
- Grafana Dashboards: http://localhost:3000
- PostgreSQL: localhost:5432
- (Ollama on 192.168.68.138:11434 if using homelab)

### Option 2: Run Locally (Manual Setup)

```bash
# 1. Backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Start PostgreSQL (via Docker or local install)
docker run -d --name postgres-acty \
  -e POSTGRES_PASSWORD=acty \
  -p 5432:5432 \
  postgres:16-alpine

# Initialize DB
psql -U postgres < scripts/init_db.sql

# Run API
cd backend && python -m uvicorn api.server:app --reload --port 8765

# 2. Frontend (separate terminal)
cd frontend
npm install
npm start   # Opens http://localhost:3000
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       OBD Hardware                              │
│  (Vehicle → OBD-II adapter → USB serial → capture machine)     │
└─────────────────────┬───────────────────────────────────────────┘
                      │ acty_obd_capture.py (daemon)
                      ↓
┌─────────────────────────────────────────────────────────────────┐
│                   Backend (FastAPI)                             │
│  ├─ /upload         → ingest CSV, validate columns             │
│  ├─ /analyze        → rule-based anomaly detection             │
│  └─ /health         → system status                            │
│                                                                 │
│  ML Pipeline:                                                   │
│  ├─ Isolation Forest (anomaly detection)                       │
│  ├─ XGBoost (predictive maintenance)                           │
│  └─ Ollama/Anthropic (LLM for insights)                        │
└──────┬──────────────────────────────┬──────────────────────────┘
       │                              │
       ↓                              ↓
   PostgreSQL                    Grafana Dashboard
   (sessions, users,             (metrics, alerts)
    predictions, events)
```

---

## 💻 Development

### Environment Setup

```bash
# Backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend
cd frontend
npm install
npm run dev

# Run linters
black backend/
npm run lint --prefix frontend
```

### Local Services

```bash
# Start full stack locally with Docker
docker compose up -d
docker compose ps              # Check health
docker compose logs -f api     # Tail logs
```

---

## 🚀 Deployment

### Pre-Deployment Checklist

Review **DEPLOYMENT_CHECKLIST.md** for complete verification:

```bash
cat DEPLOYMENT_CHECKLIST.md
```

Key items:

- [ ] Code quality checks (linting)
- [ ] Security (no hardcoded secrets)
- [ ] Dependencies pinned
- [ ] Configuration templates created
- [ ] CI tests passing

### Environment Configuration

```bash
cp .env.example .env
# Fill in secrets: DATABASE_URL, OLLAMA_HOST, API_KEY, etc.
```

### Deploy

```bash
# Using Docker Compose (Recommended)
docker compose build
docker compose down
docker compose up -d

# Using Kubernetes
kubectl apply -f k8s/

# Verify
curl http://localhost:8765/health
docker compose logs api
```

---

## 🔧 API Endpoints

| Endpoint        | Method | Purpose                |
| --------------- | ------ | ---------------------- |
| `/health`       | GET    | System status          |
| `/docs`         | GET    | OpenAPI/Swagger UI     |
| `/upload`       | POST   | Ingest OBD CSV         |
| `/analyze/{id}` | POST   | Run anomaly detection  |
| `/query`        | GET    | Query sessions         |
| `/vehicles`     | GET    | List vehicles          |
| `/predict/{id}` | GET    | Predictive maintenance |

**Full API**: Visit http://localhost:8765/docs

---

## 📁 Project Structure

```
acty-project/
├── backend/              # FastAPI + ML pipeline
│   ├── api/server.py     # Main API
│   ├── ml/               # Anomaly detection, predictions
│   └── requirements.txt
├── frontend/             # React + Framer Motion
│   ├── src/pages/        # Components
│   └── package.json
├── hardware/             # OBD capture daemon
├── scripts/              # Database init
├── docker-compose.yml    # Full-stack config
├── .env.example         # Template
├── .gitignore           # Production-ready
├── DEPLOYMENT_CHECKLIST.md
└── README.md
```

---

## 🔐 Security

- **Secrets**: Use `.env` file (never commit)
- **Database**: PostgreSQL with least-privilege user
- **API**: CORS restricted, rate limiting enabled
- **Logging**: No sensitive data in logs

---

## 📊 Monitoring

**Grafana**: http://localhost:3000 (admin/admin)

- Per-session metrics
- Vehicle health trends
- Fleet statistics

**Health Check**: `curl http://localhost:8765/health`

---

## 🧪 Testing

```bash
# Backend tests
cd backend && pytest tests/ -v

# API smoke test
curl -X POST http://localhost:8765/upload \
  -F "file=@data_capture/sample.csv"
```

---

## 📚 Documentation

- [DEPLOYMENT_CHECKLIST.md](./DEPLOYMENT_CHECKLIST.md) — Pre-deploy checklist
- [.env.example](./.env.example) — Configuration template
- [frontend/WEBSITE_SETUP.md](./frontend/WEBSITE_SETUP.md) — Frontend guide
- API Docs: http://localhost:8765/docs

---

## 🤝 Contributing

1. Create feature branch: `git checkout -b feature/xyz`
2. Follow code style: `black . && flake8 .` (Python)
3. Commit: `git commit -am 'Add feature'`
4. Push & open PR

---

## 📄 License

Elastic License 2.0 (source-available)

---

## 🔗 Links

- **Website**: https://acty-labs.com
- **API**: https://api.acty-labs.com
- **GitHub**: https://github.com/acty-labs/acty-project

---

**Status**: Production-ready · March 28, 2026
│
┌───────▼─────────────────────────────────────────────────────────┐
│ RAG PIPELINE (backend/ml/rag/) │
│ │
│ 01_parse_fsm.py PDF → structured JSON (text/OCR/table) │
│ 02_embed.py ChromaDB vector store (BGE-large, GPU) │
│ 03_query.py Semantic retrieval + Ollama generation │
│ 04_acty_bridge.py Fault → FSM context → LLM report │
│ │
│ Inference node: 4U DIY (RTX 3060 12GB) @ 192.168.68.138 │
│ Models: llama3.1:8b, nomic-embed-text │
└─────────────────────────────────────────────────────────────────┘
│
┌───────▼─────────────────────────────────────────────────────────┐
│ API (backend/api/server.py) FastAPI @ :8765 │
└─────────────────────────────────────────────────────────────────┘
│
┌───────▼─────────────────────────────────────────────────────────┐
│ FRONTEND (frontend/) React Native / Expo │
│ Android mobile app — real-time PID dashboard + alerts │
└─────────────────────────────────────────────────────────────────┘

````

## Homelab Infrastructure

| Node | Role | Specs |
|------|------|-------|
| 4U DIY | **Inference node** | RTX 3060 12GB, Ubuntu 24.04, Ollama |
| R7525 | Future ML training | 2× EPYC 7262, 512GB RAM (TBD: 2× L40 48GB) |
| R720 | Secondary services, Ingest Server, local dependency repository | 2x Intel Xeon E5‑2697 v2, 32GB RAM |
| CM3588 | Ed25519 signing & verfication | 8-core, 8GB RAM, Xubuntu |
| TrueNAS DIY | Storage | 1 x Intel Xeon E5 2680 V4, 32GB RAM, 24.65 TiB RAIDZ1 |

## Quick Start

### 1. Inference node setup (4U DIY)
```bash
# Ubuntu 24.04 — see Ollama setup in docs/
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl edit ollama
# Add: Environment="OLLAMA_HOST=0.0.0.0:11434"
sudo systemctl restart ollama
ollama pull llama3.1:8b
ollama pull nomic-embed-text
````

### 2. Backend

```bash
cp .env.example .env
# Edit .env with your values
pip install -r requirements.txt --break-system-packages
python3 backend/api/server.py
```

### 3. OBD capture (Laptop)

```bash
python3 hardware/acty_obd_capture.py
# Pairs with VeePeak OBDCheck BLE via RFCOMM
# Logs to ~/acty_obd_YYYYMMDD_HHMMSS.csv
```

### 4. RAG pipeline (run once per FSM PDF)

```bash
cd backend/ml/rag
python3 00_setup.py                          # install deps, verify GPU
python3 01_parse_fsm.py /path/to/fsm.pdf    # parse → data/parsed/
python3 02_embed.py                          # embed → data/chromadb/
python3 03_query.py "DTC P0300 diagnosis"   # test query
```

### 5. Mobile app

```bash
cd frontend
npm install
npx expo start --android
```

## Privacy Architecture

- **No data brokering** — vehicle data never leaves your LAN without explicit consent
- **Federated learning** — model updates via Flower (flwr), differential privacy ε ≤ 1.0
- **ZK identity** — rotating pseudonymous tokens (planned: ATECC608B hardware root of trust)
- **Tamper-evident reports** — hash-chained session records

## Hardware Dongle Roadmap

```
Phase 1: VeePeak BLE + Laptop (current — data collection)
Phase 2: Raspberry Pi Zero 2W prototype
Phase 3: ESP32-S3 devkit
Phase 4: Custom KiCad PCB (ESP32-S3 + ATECC608B)
```

## Vehicle: Test Mule - Toyota GR86 (FA24 engine)

\*\*This is currently being tested on just the 2022-Present Toyota GR86/Subaru BRZ. This will be expanded to other manufactures and makes soon.

The RAG pipeline is seeded with the GR86/BRZ factory service manual.
`oil_level_estimator.py` uses FA24-specific defaults (5.7 qt capacity, 0.5 qt/1k mi baseline consumption).

## License

Private / proprietary. All rights reserved.
