# Acty iOS App (Skeleton)

This folder contains a Phase 1 SwiftUI/Combine skeleton for the Acty Cactus app based on the spec.

## Goals

- Core capture screen (VIN, timer, PID cards, RPM chart)
- Background BLE scanning + ELM327 command layer (ESP32-S3 BLE + future hardware)
- CSV + .sig session files in app documents
- Supabase JWT auth and upload `/upload` payload

## Setup

1. Open in Xcode 15+.
2. Add entitlements: `com.apple.developer.networking.bluetooth`, iCloud Documents if needed.
3. Add `CoreBluetooth` and `CryptoKit` frameworks.
4. Build and run.

## Notes

- iOS cannot use classic Bluetooth SPP; must use BLE with custom service on adapter.
- This skeleton mirrors the Android behavior: capture session, DTC fetch, persistent session CSV + signature file, backend sync.
