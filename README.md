# Acty

**Your vehicle's data, owned by you.**

Acty.ai is an automotive technology data platform powered by OBD-II hardware device and an AI-driven software suite. The device continuously logs diagnostic and performance data — including trouble codes, mileage, system readiness, and hybrid battery metrics, creating a tamper-evident operational history for the life of the vehicle.

The companion software pairs directly with the device to do more than record. Using deep learning and predictive analytics, it continuously evaluates vehicle performance data to surface maintenance recommendations before problems develop. Identifying degradation patterns, flagging anomalies, and estimating service intervals based on how the vehicle is actually being driven, not just manufacturer schedules.

All raw data remains encrypted and owner-controlled. Owners may optionally share verified insights to unlock better loan terms, more accurate trade-in valuations, or contribute anonymized data to manufacturers — on their terms, not the platform's. When it's time to sell, the software generates a verified diagnostic report revealing the vehicle's full history, including cleared codes and unresolved issues, giving buyers a transparent picture that the used-car market has never had.

Acty.ai's goal is straightforward: give drivers the software intelligence to stay ahead of their vehicle's health, and full ownership of the data that makes it possible.

---

## What It Does

- **Continuous logging** — The Acty dongle plugs into your OBD-II port and passively records vehicle signals across every trip
- **Owner-controlled encryption** — Data is encrypted and owner-controlled; no third party can access it without your explicit consent
- **Tamper-evident health reports** — Generate verifiable vehicle history reports for lenders, dealers, or buyers
- **Local AI insights** — On-device analysis surfaces maintenance alerts, trip summaries, and anomalies without sending raw data to the cloud
- **Voluntary data sharing** — Opt in to share anonymized data with lenders, automakers, or researchers — on your terms

---

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

MIT