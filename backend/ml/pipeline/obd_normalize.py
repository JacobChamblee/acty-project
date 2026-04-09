"""
obd_normalize.py
----------------
Load OBD-II telemetry CSV logs sampled at 10 Hz and normalize PID columns.

Expected CSV format
-------------------
timestamp,RPM,SPEED,THROTTLE_POS,ENGINE_LOAD,COOLANT_TEMP,MAF,INTAKE_TEMP,...
0.0,800,0,12.5,20.3,85,3.21,28,...
0.1,820,0,12.7,20.5,85,3.25,28,...
...

- timestamp  : seconds since logging start (float)
- All other columns are treated as PIDs unless excluded explicitly.

Output
------
Returns a DataFrame whose PID columns are min-max normalised to [0, 1].
Optionally writes a *_normalized.csv next to the input file.

Usage
-----
    python obd_normalize.py data/trip_001.csv
    python obd_normalize.py data/trip_001.csv --output trip_normalized.csv
    python obd_normalize.py data/trip_001.csv --no-save
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ── OBD-II PID physical ranges ────────────────────────────────────────────────
# If a PID is listed here its known physical min/max is used for normalisation
# instead of the observed min/max in the file.  Add / adjust as needed.
KNOWN_PID_RANGES: dict[str, tuple[float, float]] = {
    "RPM":           (0,    8000),
    "SPEED":         (0,    255),    # km/h (SAE J1979 max)
    "THROTTLE_POS":  (0,    100),    # %
    "ENGINE_LOAD":   (0,    100),    # %
    "COOLANT_TEMP":  (-40,  215),    # °C
    "INTAKE_TEMP":   (-40,  215),    # °C
    "MAF":           (0,    655.35), # g/s
    "FUEL_PRESSURE": (0,    765),    # kPa
    "O2_VOLTAGE":    (0,    1.275),  # V
    "SHORT_FUEL_TRIM":(-100, 99.2), # %
    "LONG_FUEL_TRIM": (-100, 99.2), # %
    "TIMING_ADVANCE": (-64,  63.5),  # °
    "FUEL_LEVEL":    (0,    100),    # %
    "BAROMETRIC_PRESSURE": (0, 255), # kPa
    "CATALYST_TEMP": (-40, 6513.5),  # °C
    "CONTROL_MODULE_VOLTAGE": (0, 65.535), # V
    "ABSOLUTE_LOAD": (0, 25700),     # %
    "COMMANDED_EQUIV_RATIO": (0, 2), # λ
    "RELATIVE_THROTTLE_POS": (0, 100),
    "AMBIENT_AIR_TEMP": (-40, 215),  # °C
    "THROTTLE_ACTUATOR": (0, 100),   # %
    "ENGINE_RUN_TIME": (0, 65535),   # s
    "DISTANCE_W_MIL": (0, 65535),    # km
    "DISTANCE_SINCE_DTC_CLEAR": (0, 65535), # km
    "EVAP_VAPOR_PRESSURE": (-8192, 8192),   # Pa
    "FUEL_INJECTION_TIMING": (-210.00, 301.992), # °
    "ENGINE_FUEL_RATE": (0, 3212.75), # L/h
}

# Columns that are never PID channels
NON_PID_COLUMNS = {"timestamp", "datetime", "time", "index", "session_id",
                   "vehicle_id", "vin", "dtc", "freeze_frame"}


# ── Core functions ────────────────────────────────────────────────────────────

def load_obd_csv(path: str | Path, sample_rate_hz: float = 10.0) -> pd.DataFrame:
    """Load an OBD telemetry CSV and validate basic structure."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    df = pd.read_csv(path)

    # Normalise column names: strip whitespace, uppercase
    df.columns = [c.strip().upper() for c in df.columns]

    # Ensure a timestamp column exists; synthesise one if absent
    if "TIMESTAMP" not in df.columns:
        print("[warn] No TIMESTAMP column found — synthesising from sample rate.")
        df.insert(0, "TIMESTAMP", np.arange(len(df)) / sample_rate_hz)

    df["TIMESTAMP"] = pd.to_numeric(df["TIMESTAMP"], errors="coerce")

    # Validate expected cadence (warn only — don't abort)
    if len(df) > 1:
        median_dt = np.median(np.diff(df["TIMESTAMP"].dropna().values))
        expected_dt = 1.0 / sample_rate_hz
        if abs(median_dt - expected_dt) > expected_dt * 0.25:
            print(
                f"[warn] Median sample interval {median_dt:.4f}s differs from "
                f"expected {expected_dt:.4f}s for {sample_rate_hz} Hz."
            )

    print(f"[info] Loaded {len(df):,} rows × {len(df.columns)} columns from {path.name}")
    return df


def identify_pid_columns(df: pd.DataFrame) -> list[str]:
    """Return column names that look like PID channels."""
    pid_cols = []
    for col in df.columns:
        if col.upper() in NON_PID_COLUMNS:
            continue
        if col.upper() == "TIMESTAMP":
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            pid_cols.append(col)
        else:
            print(f"[skip] Non-numeric column '{col}' — skipping normalisation.")
    return pid_cols


def normalize_pid_columns(
    df: pd.DataFrame,
    pid_cols: list[str],
    use_known_ranges: bool = True,
    clip: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Min-max normalise PID columns to [0, 1].

    Parameters
    ----------
    df              : input DataFrame (not modified in place)
    pid_cols        : list of column names to normalise
    use_known_ranges: use KNOWN_PID_RANGES where available
    clip            : clip values to [0, 1] after scaling (handles out-of-range readings)

    Returns
    -------
    norm_df   : copy of df with normalised PID columns
    scaler_df : DataFrame documenting the min/max used for each PID
    """
    norm_df = df.copy()
    scaler_records = []

    for col in pid_cols:
        series = pd.to_numeric(df[col], errors="coerce")

        if use_known_ranges and col.upper() in KNOWN_PID_RANGES:
            lo, hi = KNOWN_PID_RANGES[col.upper()]
            source = "known_range"
        else:
            lo = float(series.min())
            hi = float(series.max())
            source = "observed"

        denom = hi - lo
        if denom == 0:
            print(f"[warn] '{col}' has zero range (constant value {lo}). Setting to 0.")
            norm_df[col] = 0.0
            hi = lo  # keep record consistent
        else:
            normalised = (series - lo) / denom
            if clip:
                normalised = normalised.clip(0.0, 1.0)
            norm_df[col] = normalised

        scaler_records.append({
            "pid":    col,
            "min":    lo,
            "max":    hi,
            "source": source,
            "n_null": int(series.isna().sum()),
        })

    scaler_df = pd.DataFrame(scaler_records).set_index("pid")
    return norm_df, scaler_df


def print_summary(scaler_df: pd.DataFrame) -> None:
    """Pretty-print normalisation summary."""
    print("\n── Normalisation summary ─────────────────────────────────────────")
    print(f"{'PID':<30} {'MIN':>10} {'MAX':>10} {'SOURCE':<14} {'NULLS':>6}")
    print("─" * 72)
    for pid, row in scaler_df.iterrows():
        print(
            f"{pid:<30} {row['min']:>10.3f} {row['max']:>10.3f} "
            f"{row['source']:<14} {row['n_null']:>6}"
        )
    print("─" * 72)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load and normalise OBD-II telemetry CSV logs."
    )
    parser.add_argument("input", help="Path to the input CSV file.")
    parser.add_argument(
        "--output", "-o", default=None,
        help="Path for the normalised output CSV. "
             "Defaults to <input>_normalized.csv in the same directory.",
    )
    parser.add_argument(
        "--no-save", action="store_true",
        help="Do not write output CSV (dry run / library use).",
    )
    parser.add_argument(
        "--sample-rate", type=float, default=10.0,
        help="Expected sample rate in Hz (default: 10).",
    )
    parser.add_argument(
        "--observed-ranges", action="store_true",
        help="Always use observed min/max, ignoring KNOWN_PID_RANGES.",
    )
    parser.add_argument(
        "--no-clip", action="store_true",
        help="Do not clip values outside [0, 1].",
    )
    args = parser.parse_args()

    # Load
    df = load_obd_csv(args.input, sample_rate_hz=args.sample_rate)

    # Identify PIDs
    pid_cols = identify_pid_columns(df)
    print(f"[info] {len(pid_cols)} PID column(s) identified: {pid_cols}")

    if not pid_cols:
        print("[error] No numeric PID columns found. Nothing to normalise.")
        sys.exit(1)

    # Normalise
    norm_df, scaler_df = normalize_pid_columns(
        df,
        pid_cols,
        use_known_ranges=not args.observed_ranges,
        clip=not args.no_clip,
    )

    # Summary
    print_summary(scaler_df)

    # Save
    if not args.no_save:
        input_path = Path(args.input)
        output_path = (
            Path(args.output)
            if args.output
            else input_path.with_stem(input_path.stem + "_normalized")
        )
        norm_df.to_csv(output_path, index=False)
        print(f"\n[info] Saved normalised CSV → {output_path}")


if __name__ == "__main__":
    main()
