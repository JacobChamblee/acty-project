# Acty — OBD-II AI Diagnostics Platform

> Hardware-first vehicle intelligence. Local inference. Zero data brokering.

Acty is an OBD-II dongle + software platform that provides AI-powered vehicle diagnostics, predictive maintenance, and tamper-evident health reporting — all running on your own hardware.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  HARDWARE LAYER                                                 │
│  VeePeak OBDCheck BLE ──► acty_obd_capture.py (IoT/Laptop)      │
│                                 │ CSV logs                      │
└─────────────────────────────────┼───────────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────┐
│  ML PIPELINE  (backend/ml/pipeline/)                            │
│                                                                 │
│  obd_normalize.py        CSV ingest + PID normalization         │
│       │                                                         │
│  oil_change_detector.py  Multi-signal oil change detection      │
│  oil_level_estimator.py  Probabilistic oil level estimation     │
│  oil_interval_advisor.py Severity-weighted change intervals     │
│  battery_health.py       12V battery + alternator health        │
│  maintenance_tracker.py  Brakes, tires, trans fluid, etc.       │
│       │                                                         │
│  [anomaly.py]     ← Isolation Forest + LSTM autoencoder         │
│  [predictive.py]  ← XGBoost/RF per-vehicle models  (TODO)       │
│       │                                                         │
└───────┼─────────────────────────────────────────────────────────┘
        │
┌───────▼─────────────────────────────────────────────────────────┐
│  RAG PIPELINE  (backend/ml/rag/)                                │
│                                                                 │
│  01_parse_fsm.py   PDF → structured JSON (text/OCR/table)       │
│  02_embed.py       ChromaDB vector store (BGE-large, GPU)       │
│  03_query.py       Semantic retrieval + Ollama generation       │
│  04_acty_bridge.py Fault → FSM context → LLM report             │
│                                                                 │
│  Inference node: 4U DIY (RTX 3060 12GB) @ 192.168.68.138        │
│  Models: llama3.1:8b, nomic-embed-text                          │
└─────────────────────────────────────────────────────────────────┘
        │
┌───────▼─────────────────────────────────────────────────────────┐
│  API  (backend/api/server.py)   FastAPI @ :8765                 │
└─────────────────────────────────────────────────────────────────┘
        │
┌───────▼─────────────────────────────────────────────────────────┐
│  FRONTEND  (frontend/)  React Native / Expo                     │
│  Android mobile app — real-time PID dashboard + alerts          │
└─────────────────────────────────────────────────────────────────┘
```

## Homelab Infrastructure

| Node | Role | Specs |
|------|------|-------|
| 4U DIY | **Inference node** | RTX 3060 12GB, Ubuntu 24.04, Ollama |
| R7525 | Future ML training | 2× EPYC 7262, 512GB RAM (TBD: 2× L40 48GB) |
| R720 | Secondary services | - |
| CM3588 | Home server | 8-core, 8GB RAM, Xubuntu |
| TrueNAS DIY | Storage | - |

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
```

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

**This is currently being tested on just the 2022-Present Toyota GR86/Subaru BRZ. This will be expanded to other manufactures and makes soon.

The RAG pipeline is seeded with the GR86/BRZ factory service manual.
`oil_level_estimator.py` uses FA24-specific defaults (5.7 qt capacity, 0.5 qt/1k mi baseline consumption).

## License

Private / proprietary. All rights reserved.
