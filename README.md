# Acty

**Your vehicle's data, owned by you.**

Acty is an OBD-II hardware + software platform that permanently logs vehicle data, encrypts it on-device, and gives owners full control over what gets shared — and with whom. Unlike telematics systems that silently funnel your driving data to insurers or automakers, Acty puts you in the driver's seat.

---

## What It Does

- **Continuous logging** — The Acty dongle plugs into your OBD-II port and passively records vehicle signals across every trip
- **Owner-controlled encryption** — Data is encrypted and owner-controlled; no third party can access it without your explicit consent
- **Tamper-evident health reports** — Generate verifiable vehicle history reports for lenders, dealers, or buyers
- **Local AI insights** — On-device analysis surfaces maintenance alerts, trip summaries, and anomalies without sending raw data to the cloud
- **Voluntary data sharing** — Opt in to share anonymized data with lenders, automakers, or researchers — on your terms

---

## OBD Data Logging

- **OBDLink MX+** - Best developer option
- Bluetooth BLE + classic
- Very high PID polling rate
- Supports all OBD-II protocols
- Good SDK documentation

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React, TypeScript, Vite, Tailwind CSS |
| Backend | Python |
| Tooling | ESLint, PostCSS |

---

## Project Structure

```
acty-project/
├── src/
│   ├── components/
│   │   ├── DiagnosticCards.tsx   # Vehicle fault & health display
│   │   ├── ReportStream.tsx      # Live / historical report view
│   │   ├── SignalCharts.tsx      # OBD-II signal visualization
│   │   ├── TripSidebar.tsx       # Trip history navigation
│   │   └── UploadPanel.tsx       # Dongle data upload interface
│   ├── App.tsx
│   └── main.tsx
├── backend/                      # Python API & data processing
└── index.html
```

---

## Pipeline Architecture

The backend pipeline maps to a layered analytics architecture, separating deterministic diagnostics from AI interpretation. Rules detect mechanical truths, ML detects unknown patterns, and the LLM only explains results.

| File | Pipeline Layer |
|---|---|
| `backend/pipeline/ingest.py` | Layer 1 — Data Ingestion |
| `backend/pipeline/signal.py` | Layer 2 — Signal Processing |
| `backend/pipeline/features.py` | Layer 3 — Feature Engineering |
| `backend/pipeline/rules.py` | Layer 4 — Rule-Based Diagnostics |
| `backend/pipeline/trends.py` | Layer 5 — Trend Analysis |
| `backend/pipeline/llm_report.py` | Layer 6 — Insight Generation (LLM) |

```
OBD Logger → Ingest → Signal Processing → Feature Engineering
                                                    │
                                      ┌─────────────┴─────────────┐
                                 Rule Engine               ML Models
                                      └─────────────┬─────────────┘
                                                     │
                                           Insight Aggregator
                                                     │
                                             LLM Report Generator
                                                     │
                                          Human-Readable Report
```

---

## Getting Started

### Prerequisites

- Node.js 18+
- Python 3.10+

### Frontend

```bash
npm install
npm run dev
```

### Backend

```bash
cd backend
pip install -r requirements.txt
python main.py
```

---

## Roadmap

- [ ] Hardware dongle firmware
- [ ] End-to-end encryption pipeline
- [ ] Verified report generation & signing
- [ ] Mobile companion app
- [ ] Voluntary data marketplace

---

## Philosophy

Acty's business model is built on hardware sales and verified reports — not data brokering. We believe vehicle data is personal data, and personal data belongs to the person.

---

## License
