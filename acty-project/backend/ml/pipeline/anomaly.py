"""
anomaly.py — Stage 2: Anomaly Detection
Isolation Forest (statistical) + LSTM Autoencoder (temporal patterns)
Consumes normalized OBD DataFrame, returns scored anomaly results.
"""

import numpy as np
import pandas as pd
from typing import Optional
from dataclasses import dataclass, field

# ── result dataclass ──────────────────────────────────────────────────────────
@dataclass
class AnomalyResult:
    method:        str
    anomaly_score: float          # 0.0 (normal) → 1.0 (highly anomalous)
    is_anomaly:    bool
    flagged_pids:  list[str]      # PIDs that contributed most to the anomaly
    details:       dict = field(default_factory=dict)


# ── PID columns used for anomaly detection ────────────────────────────────────
ANOMALY_PIDS = [
    "RPM",
    "SPEED",
    "COOLANT_TEMP",
    "ENGINE_LOAD",
    "SHORT_FUEL_TRIM_1",
    "LONG_FUEL_TRIM_1",
    "TIMING_ADVANCE",
    "MAF",
    "INTAKE_TEMP",
    "CONTROL_VOLTAGE",
    "ENGINE_OIL_TEMP",
]

# ── Isolation Forest ──────────────────────────────────────────────────────────
def run_isolation_forest(
    df: pd.DataFrame,
    contamination: float = 0.05,
    min_samples: int = 50,
) -> Optional[AnomalyResult]:
    """
    Fit Isolation Forest on numeric PID columns.
    Returns AnomalyResult or None if insufficient data.
    """
    try:
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        print("[anomaly] scikit-learn not available, skipping Isolation Forest")
        return None

    # Select available PID columns with enough non-null values
    cols = [c for c in ANOMALY_PIDS if c in df.columns and df[c].notna().sum() >= min_samples]
    if len(cols) < 3 or len(df) < min_samples:
        return None

    X = df[cols].fillna(df[cols].median())

    # Standardize
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Fit + score
    clf = IsolationForest(
        contamination=contamination,
        n_estimators=200,
        random_state=42,
        n_jobs=-1,
    )
    labels = clf.fit_predict(X_scaled)           # -1 = anomaly, 1 = normal
    scores = clf.decision_function(X_scaled)     # more negative = more anomalous

    n_anomalies  = (labels == -1).sum()
    anomaly_rate = n_anomalies / len(df)

    # Identify which PIDs drift most in anomalous rows
    anomalous_rows = df[cols][labels == -1]
    normal_rows    = df[cols][labels == 1]
    flagged_pids   = []
    if not anomalous_rows.empty and not normal_rows.empty:
        drift = (anomalous_rows.mean() - normal_rows.mean()).abs()
        flagged_pids = drift.nlargest(3).index.tolist()

    # Normalize anomaly score 0→1
    raw_min, raw_max = scores.min(), scores.max()
    if raw_max != raw_min:
        normalized = 1.0 - (scores - raw_min) / (raw_max - raw_min)
    else:
        normalized = np.zeros(len(scores))
    mean_score = float(normalized[labels == -1].mean()) if n_anomalies > 0 else 0.0

    return AnomalyResult(
        method        = "isolation_forest",
        anomaly_score = round(mean_score, 4),
        is_anomaly    = anomaly_rate > contamination,
        flagged_pids  = flagged_pids,
        details       = {
            "n_anomalies":   int(n_anomalies),
            "anomaly_rate":  round(float(anomaly_rate) * 100, 2),
            "total_samples": len(df),
            "pids_used":     cols,
        }
    )


# ── LSTM Autoencoder ──────────────────────────────────────────────────────────
def run_lstm_autoencoder(
    df: pd.DataFrame,
    sequence_len: int = 30,
    epochs: int = 10,
    threshold_percentile: float = 95.0,
    min_samples: int = 100,
) -> Optional[AnomalyResult]:
    """
    Train a lightweight LSTM autoencoder on PID time series.
    High reconstruction error → temporal anomaly.
    Returns AnomalyResult or None if insufficient data.
    """
    try:
        import torch
        import torch.nn as nn
        from torch.utils.data import DataLoader, TensorDataset
    except ImportError:
        print("[anomaly] PyTorch not available, skipping LSTM autoencoder")
        return None

    cols = [c for c in ANOMALY_PIDS if c in df.columns and df[c].notna().sum() >= min_samples]
    if len(cols) < 3 or len(df) < min_samples:
        return None

    # ── Prepare sequences ─────────────────────────────────────────────────────
    data = df[cols].fillna(df[cols].median()).values.astype(np.float32)

    # Min-max normalize per column
    col_min = data.min(axis=0)
    col_max = data.max(axis=0)
    col_range = np.where(col_max - col_min == 0, 1, col_max - col_min)
    data = (data - col_min) / col_range

    sequences = np.array([
        data[i:i + sequence_len]
        for i in range(len(data) - sequence_len)
    ])

    if len(sequences) < 10:
        return None

    X = torch.tensor(sequences)
    loader = DataLoader(TensorDataset(X), batch_size=32, shuffle=True)

    # ── Model ─────────────────────────────────────────────────────────────────
    class LSTMAutoencoder(nn.Module):
        def __init__(self, n_features: int, hidden: int = 32):
            super().__init__()
            self.encoder = nn.LSTM(n_features, hidden, batch_first=True)
            self.decoder = nn.LSTM(hidden, n_features, batch_first=True)

        def forward(self, x):
            _, (h, _) = self.encoder(x)
            # Repeat hidden state across sequence length for decoding
            h_repeated = h.squeeze(0).unsqueeze(1).repeat(1, x.size(1), 1)
            out, _ = self.decoder(h_repeated)
            return out

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model  = LSTMAutoencoder(n_features=len(cols)).to(device)
    opt    = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.MSELoss()

    # ── Train ─────────────────────────────────────────────────────────────────
    model.train()
    for _ in range(epochs):
        for (batch,) in loader:
            batch = batch.to(device)
            opt.zero_grad()
            recon = model(batch)
            loss  = loss_fn(recon, batch)
            loss.backward()
            opt.step()

    # ── Score all sequences ───────────────────────────────────────────────────
    model.eval()
    reconstruction_errors = []
    with torch.no_grad():
        for (batch,) in DataLoader(TensorDataset(X), batch_size=64):
            batch = batch.to(device)
            recon = model(batch)
            err   = ((recon - batch) ** 2).mean(dim=(1, 2))
            reconstruction_errors.extend(err.cpu().numpy().tolist())

    errors    = np.array(reconstruction_errors)
    threshold = np.percentile(errors, threshold_percentile)
    anomalous = errors > threshold
    n_anomalies  = anomalous.sum()
    anomaly_rate = n_anomalies / len(errors)

    # PIDs with highest mean reconstruction error in anomalous sequences
    anomalous_seqs = sequences[anomalous]
    normal_seqs    = sequences[~anomalous]
    flagged_pids   = []
    if len(anomalous_seqs) > 0 and len(normal_seqs) > 0:
        pid_err = np.abs(anomalous_seqs.mean(axis=(0, 1)) - normal_seqs.mean(axis=(0, 1)))
        top_idx = pid_err.argsort()[-3:][::-1]
        flagged_pids = [cols[i] for i in top_idx]

    mean_score = float(errors[anomalous].mean() / (threshold + 1e-9)) if n_anomalies > 0 else 0.0
    mean_score = min(round(mean_score, 4), 1.0)

    return AnomalyResult(
        method        = "lstm_autoencoder",
        anomaly_score = mean_score,
        is_anomaly    = anomaly_rate > 0.05,
        flagged_pids  = flagged_pids,
        details       = {
            "n_anomalies":        int(n_anomalies),
            "anomaly_rate":       round(float(anomaly_rate) * 100, 2),
            "threshold":          round(float(threshold), 6),
            "mean_recon_error":   round(float(errors.mean()), 6),
            "sequence_len":       sequence_len,
            "pids_used":          cols,
            "device":             str(device),
        }
    )


# ── Combined runner ───────────────────────────────────────────────────────────
def run_anomaly_detection(
    df: pd.DataFrame,
    use_lstm: bool = True,
) -> dict:
    """
    Run all anomaly detectors and return combined results.
    Called by the Acty pipeline after obd_normalize.

    Returns:
        {
            "isolation_forest": AnomalyResult | None,
            "lstm_autoencoder": AnomalyResult | None,
            "combined_score":   float,
            "is_anomaly":       bool,
            "flagged_pids":     list[str],
        }
    """
    if_result   = run_isolation_forest(df)
    lstm_result = run_lstm_autoencoder(df) if use_lstm else None

    # Combine scores — weight IF more heavily if LSTM unavailable
    scores = []
    if if_result:
        scores.append(if_result.anomaly_score * 0.6)
    if lstm_result:
        scores.append(lstm_result.anomaly_score * 0.4)

    combined_score = round(sum(scores), 4) if scores else 0.0
    is_anomaly     = any([
        if_result.is_anomaly   if if_result   else False,
        lstm_result.is_anomaly if lstm_result else False,
    ])

    # Union of flagged PIDs from both methods
    flagged = list(set(
        (if_result.flagged_pids   if if_result   else []) +
        (lstm_result.flagged_pids if lstm_result else [])
    ))

    return {
        "isolation_forest": if_result,
        "lstm_autoencoder": lstm_result,
        "combined_score":   combined_score,
        "is_anomaly":       is_anomaly,
        "flagged_pids":     flagged,
    }
