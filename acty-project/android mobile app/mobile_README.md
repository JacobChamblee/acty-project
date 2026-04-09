# Acty Mobile Prototype

Android app + Python backend for OBD-II AI insights over home WiFi.

```
Phone (Android) ──WiFi──► FastAPI server (your PC/R7525) ──► acty_obd_*.csv files
                                    └──► anomaly detection
                                    └──► health score + alerts
```

---

## Backend setup (your Linux machine)

```bash
cd backend/

# Install dependencies
pip install fastapi uvicorn pandas numpy scikit-learn --break-system-packages

# Point at your CSV directory (defaults to home folder)
export ACTY_CSV_DIR=~/   # or wherever acty_obd_*.csv files are

# Start the server
python3 server.py
```

Server starts at `http://0.0.0.0:8765` — accessible from your phone on the same WiFi.

**Find your machine's LAN IP:**
```bash
ip addr show | grep "inet " | grep -v 127.0.0.1
# look for something like 192.168.1.xxx
```

---

## App setup (your dev machine)

### Prerequisites
```bash
# Install Node.js if not installed
sudo apt install nodejs npm

# Install Expo CLI
npm install -g expo-cli
```

### Run in development (easiest)
```bash
cd app/
npm install
npx expo start
```

This shows a QR code. On your Android phone:
1. Install **Expo Go** from the Play Store
2. Open Expo Go → scan the QR code
3. App loads on your phone instantly — no APK needed

### Before running — update your server IP
Edit `App.js` line 8:
```js
const API_BASE = "http://192.168.68.142:8765";
//                        ^^^ change to your machine's LAN IP
```

---

## Build a real APK (install directly, no Expo Go)

```bash
# Install EAS CLI
npm install -g eas-cli

# Login to Expo account (free)
eas login

# Build APK for local install (no app store)
cd app/
eas build --platform android --profile preview --local
```

This produces an `.apk` file you can transfer to your phone via USB or email and install directly.

---

## API endpoints

| Endpoint | Description |
|---|---|
| `GET /insights` | Latest session: health score, alerts, sparklines |
| `GET /sessions` | List of all captured sessions |
| `GET /sessions/{filename}` | Insights for a specific session |
| `GET /health` | Server health check |

---

## What the app shows

- **Health Score** (0–100) — composite score based on detected anomalies
- **Alerts** — warning/critical flags with human-readable explanations
  - Rule-based: coolant temp, fuel trims, battery voltage, engine load, RPM
  - ML-based: Isolation Forest pattern anomalies
- **Session Stats** — RPM, speed, coolant, load, LTFT, timing, MAF, battery
- **Sparklines** — last 60 samples of each key PID
- **Drive Profile** — % time moving vs idle, fuel level

---

## File structure

```
acty-mobile/
├── backend/
│   └── server.py          # FastAPI server
├── app/
│   ├── App.js             # Full React Native app
│   ├── app.json           # Expo config
│   └── package.json       # Dependencies
└── README.md
```
