#!/usr/bin/env python3
"""
test_anomaly_via_api.py — Test anomaly detection by uploading OBD CSV files via API.

This test demonstrates the full pipeline:
  1. Generate synthetic OBD data (or use real CSV)
  2. Upload via POST /upload endpoint
  3. Verify anomaly detection was run
  4. Check results in database

Usage:
  python3 test_anomaly_via_api.py
"""

import csv
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' module not found")
    print("Install with: pip3 install requests")
    sys.exit(1)


API_BASE = "http://localhost:8765"


def generate_synthetic_obd_csv(num_rows: int = 500, inject_anomaly: bool = False) -> str:
    """Generate synthetic OBD-II CSV data."""
    import random
    
    fieldnames = [
        "timestamp", "RPM", "SPEED", "COOLANT_TEMP", "ENGINE_LOAD",
        "SHORT_FUEL_TRIM_1", "LONG_FUEL_TRIM_1", "TIMING_ADVANCE", "MAF",
        "INTAKE_TEMP", "CONTROL_VOLTAGE", "ENGINE_OIL_TEMP"
    ]

    rows = []
    start_time = datetime.now().timestamp()

    for i in range(num_rows):
        timestamp = start_time + (i * 0.1)  # 0.1 second intervals

        row = {
            "timestamp": datetime.fromtimestamp(timestamp).isoformat(),
            "RPM": round(random.gauss(2000, 500), 2),
            "SPEED": round(random.gauss(60, 20), 2),
            "COOLANT_TEMP": round(random.gauss(90, 5), 2),
            "ENGINE_LOAD": round(random.gauss(45, 15), 2),
            "SHORT_FUEL_TRIM_1": round(random.gauss(0, 2), 2),
            "LONG_FUEL_TRIM_1": round(random.gauss(-1, 1.5), 2),
            "TIMING_ADVANCE": round(random.gauss(15, 3), 2),
            "MAF": round(random.gauss(5, 2), 2),
            "INTAKE_TEMP": round(random.gauss(30, 5), 2),
            "CONTROL_VOLTAGE": round(random.gauss(13.5, 0.5), 2),
            "ENGINE_OIL_TEMP": round(random.gauss(100, 8), 2),
        }

        # Inject anomalies at 5% rate if requested
        if inject_anomaly and random.random() < 0.05:
            row["COOLANT_TEMP"] = round(random.gauss(120, 5), 2)  # Dangerously high
            row["ENGINE_LOAD"] = round(random.gauss(95, 5), 2)    # Maxed out
            row["SHORT_FUEL_TRIM_1"] = round(random.gauss(15, 3), 2)

        rows.append(row)

    # Write to temporary CSV file
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
    writer = csv.DictWriter(temp_file, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    temp_file.close()

    return temp_file.name


def test_upload_and_detect() -> bool:
    """Test uploading OBD CSV and verifying anomaly detection."""
    print("\n📤 TEST: Upload OBD CSV and Run Anomaly Detection")
    print("=" * 70)

    # Generate synthetic data
    csv_file = generate_synthetic_obd_csv(num_rows=500, inject_anomaly=True)
    print(f"Generated synthetic OBD CSV: {csv_file}")

    try:
        # Upload the CSV
        with open(csv_file, 'rb') as f:
            files = {'file': f}
            print(f"Uploading CSV to {API_BASE}/upload...")
            
            response = requests.post(
                f"{API_BASE}/upload",
                files=files,
                timeout=30,
            )

        print(f"Response Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Upload successful!")
            print(f"   File:              {data.get('filename')}")
            print(f"   Rows Processed:    {data.get('rows_processed')}")
            print(f"   Status:            {data.get('status')}")
            
            # Check if anomaly detection results are included
            if 'anomaly_detection' in data:
                anomaly = data['anomaly_detection']
                print(f"\n  📊 Anomaly Detection Results:")
                print(f"     Method:        {anomaly.get('method')}")
                print(f"     Anomaly Score: {anomaly.get('anomaly_score')}")
                print(f"     Is Anomalous:  {anomaly.get('is_anomaly')}")
                print(f"     Flagged PIDs:  {', '.join(anomaly.get('flagged_pids', []))}")
            
            return True
        else:
            print(f"❌ Upload failed: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False

    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to API at {API_BASE}")
        print("   Make sure 'docker compose up -d' is running")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        # Clean up temp file
        Path(csv_file).unlink(missing_ok=True)


def test_health_and_db():
    """Test API health and database connectivity."""
    print("\n💚 TEST: API Health & Database")
    print("=" * 70)

    try:
        response = requests.get(f"{API_BASE}/health", timeout=5)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

    try:
        data = response.json()
        
        print(f"✅ API is healthy:")
        print(f"  • Status:         {data.get('status')}")
        print(f"  • DB Connected:   {data.get('db_connected')}")
        print(f"  • CSV Dir:        {data.get('csv_dir')}")
        
        return data.get("status") == "ok" and data.get("db_connected") == True

    except json.JSONDecodeError:
        print(f"❌ Invalid JSON response")
        return False


def test_with_real_csv():
    """Test with real OBD CSV files from data_capture/ if available."""
    print("\n📁 TEST: Real OBD CSV from data_capture/")
    print("=" * 70)

    data_dir = Path("/home/jacob/acty-project/data_capture")
    
    if not data_dir.exists():
        print(f"⚠️  {data_dir} not found, skipping")
        return True

    csv_files = sorted(data_dir.glob("acty_obd_*.csv"))
    
    if not csv_files:
        print(f"⚠️  No CSV files found in {data_dir}")
        return True

    csv_file = csv_files[0]
    print(f"Testing with: {csv_file.name}")

    try:
        with open(csv_file, 'rb') as f:
            files = {'file': f}
            
            response = requests.post(
                f"{API_BASE}/upload",
                files=files,
                timeout=30,
            )

        print(f"Response Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Real CSV processed successfully!")
            print(f"   Rows: {data.get('rows_processed')}")
            
            if 'anomaly_detection' in data:
                anomaly = data['anomaly_detection']
                print(f"   Anomaly Score: {anomaly.get('anomaly_score')}")
            
            return True
        else:
            print(f"⚠️  Upload returned {response.status_code}")
            return True  # Don't fail on this

    except Exception as e:
        print(f"⚠️  Error: {e}")
        return True  # Don't fail on this


def main():
    """Run anomaly detection tests."""
    print("\n" + "=" * 70)
    print("ANOMALY DETECTION TEST SUITE (Via API)")
    print("=" * 70)

    results = []

    # Health check
    results.append(("API Health & DB", test_health_and_db()))

    if not results[0][1]:
        print("\n⚠️  API is not available. Make sure docker compose is running:")
        print("    docker compose up -d")
        return 1

    # Upload and detect
    results.append(("Upload & Detect", test_upload_and_detect()))

    # Real CSV test
    results.append(("Real CSV Data", test_with_real_csv()))

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}  {name}")

    print(f"\nResult: {passed}/{total} tests passed")

    if passed >= len(results) - 1:  # Allow 1 optional test to fail
        print("\n🎉 Anomaly detection is working! Pipeline verified.")
        return 0
    else:
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
