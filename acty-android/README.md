# Acty Android App

Native Android OBD-II capture app. Connects to the VeePeak OBDCheck BLE dongle via classic Bluetooth RFCOMM (SPP), runs the ELM327 PID poll loop, writes identical CSV output to the Python capture script, and auto-syncs to acty-api over WiFi.

---

## Project Structure

```
app/src/main/java/com/acty/
├── bluetooth/
│   ├── ELM327.kt              AT command layer (port of Python ELM327 class)
│   ├── ObdCaptureService.kt   Foreground service — poll loop, CSV write, sync trigger
│   └── PidRegistry.kt         PID definitions (port of Python PID_REGISTRY)
├── data/
│   ├── CsvWriter.kt           CSV output (identical format to acty_obd_capture.py)
│   └── SyncManager.kt         Upload to acty-api, manifest deduplication
├── model/
│   └── SessionState.kt        State + event data classes
├── ui/
│   ├── MainActivity.kt
│   ├── LiveSessionFragment.kt  Live PIDs, RPM chart, VIN, timer
│   ├── SessionsFragment.kt     Session history, sync badges
│   ├── SessionViewModel.kt
│   └── PidCardView.kt          Custom PID tile widget
└── ActyApplication.kt
```

---

## Setup

### 1. Open in Android Studio

Open the `acty-android/` folder in Android Studio Hedgehog (2023.1) or newer.

### 2. Configure the acty-api upload URL

Edit `app/src/main/java/com/acty/data/SyncManager.kt`:

```kotlin
private const val UPLOAD_URL = "http://192.168.68.138:8765/upload"
```

Update to your acty-api server IP if different.

### 3. Configure the dongle MAC (optional)

The VeePeak MAC is hardcoded as the default in `SessionViewModel.kt`:

```kotlin
var targetAddress: String = "8C:DE:52:D9:7E:D1"
```

This can be made user-configurable in a Settings screen later.

### 4. Build and install

```
Build > Make Project
Run > Run 'app'
```

Minimum Android 8.0 (API 26).

---

## Permissions

| Permission                                   | Why                                |
| -------------------------------------------- | ---------------------------------- |
| `BLUETOOTH_CONNECT` / `BLUETOOTH`            | Connect to VeePeak dongle          |
| `BLUETOOTH_SCAN`                             | Discover paired devices (API 31+)  |
| `FOREGROUND_SERVICE`                         | Keep capture alive with screen off |
| `ACCESS_NETWORK_STATE` / `ACCESS_WIFI_STATE` | Detect WiFi for auto-sync          |
| `INTERNET`                                   | Upload CSVs to acty-api            |
| `WRITE_EXTERNAL_STORAGE`                     | Save CSVs (API ≤ 28)               |

---

## CSV Output

Files saved to: `/storage/emulated/0/Documents/Acty/data_capture/acty_obd_YYYYMMDD_HHMMSS.csv`

Format is **identical** to `acty_obd_capture.py` — same column names, same timestamp format, same VIN column. Existing acty-api ingest pipeline accepts these files without changes.

---

## Sync Behaviour

- On WiFi connect after a session ends, `SyncManager` uploads all pending CSVs to `acty-api /upload`
- A `.sync_manifest` file in `data_capture/` tracks synced filenames to avoid re-uploading
- Manual sync available in the Sessions tab via "Sync Now" button
- Files already on server are added to manifest without re-uploading

---

## Key Dependencies

| Library               | Use                              |
| --------------------- | -------------------------------- |
| `MPAndroidChart`      | Live RPM chart                   |
| `OkHttp 4`            | CSV + .sig upload to acty-api    |
| `kotlinx.coroutines`  | Poll loop, async sync            |
| `androidx.lifecycle`  | ViewModel, StateFlow             |
| `Material Components` | Theme, BottomNavigationView, FAB |

## Android updates (from cactus app spec)

- Added `ActyConfig` constants and Bluetooth/OBD settings.
- Data sessions include `sessionId` and `vehicleId`.
- `CsvWriter` now writes `DTC_CONFIRMED`, `DTC_PENDING`, and `prev_hash` columns plus merkle root computed in .sig creation.
- `SessionSigner` uses Android Keystore (Ed25519 on API 33+, secp256r1 on older) to sign session payloads and generate `<session>.sig` JSON.
- `SyncManager` now calls `/upload` with JSON body: `{session_id, vehicle_id, csv_b64, sig_b64}`.
- `ELM327` includes `getPendingDtcs()` (mode 07) + improved DTC parsing.

## iOS skeleton

See `../acty-ios` for the SwiftUI skeleton and implementation notes.
