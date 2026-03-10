import numpy as np
import pandas as pd
from typing import Dict, List
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import MinMaxScaler

# PyTorch is optional — falls back gracefully if not installed
try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


# ── LSTM Autoencoder ────────────────────────────────────────────────────────

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

model = LSTMAutoencoder(input_size=input_size).to(device)
tensor = torch.FloatTensor(sequences).to(device)

class LSTMAutoencoder(nn.Module):
    def __init__(self, input_size: int, hidden_size: int = 32, num_layers: int = 1):
        super().__init__()
        self.encoder = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
        self.decoder = nn.LSTM(hidden_size, input_size, num_layers, batch_first=True)

    def forward(self, x):
        # x: (batch, seq_len, input_size)
        encoded, (h, c) = self.encoder(x)
        # Repeat the last hidden state across the sequence length for decoding
        repeated = h[-1].unsqueeze(1).repeat(1, x.size(1), 1)
        decoded, _ = self.decoder(repeated)
        return decoded


def _lstm_reconstruction_errors(sequences: np.ndarray) -> np.ndarray:
    """
    Train a lightweight LSTM autoencoder on the provided sequences and return
    per-sequence mean squared reconstruction error.
    sequences shape: (n_sequences, seq_len, n_features)
    """
    input_size = sequences.shape[2]
    model = LSTMAutoencoder(input_size=input_size)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.MSELoss()

    tensor = torch.FloatTensor(sequences)

    model.train()
    for _ in range(30):  # lightweight training — enough for anomaly scoring
        optimizer.zero_grad()
        output = model(tensor)
        loss = loss_fn(output, tensor)
        loss.backward()
        optimizer.step()

    model.eval()
    with torch.no_grad():
        output = model(tensor)
        errors = ((output - tensor) ** 2).mean(dim=(1, 2)).numpy()

    return errors


def _make_sequences(arr: np.ndarray, seq_len: int = 30) -> np.ndarray:
    """Slide a window over a 2D array to produce 3D sequences."""
    sequences = []
    for i in range(len(arr) - seq_len):
        sequences.append(arr[i : i + seq_len])
    return np.array(sequences)


# ── Public API ───────────────────────────────────────────────────────────────

def detect_anomalies(df: pd.DataFrame, features: Dict) -> List[Dict]:
    """
    Run anomaly detection on a single trip DataFrame.

    Uses:
      - Isolation Forest  →  point anomalies across all available signals
      - LSTM Autoencoder  →  sequential / temporal anomalies (requires PyTorch)

    Returns a list of event dicts in the same format as rules.py.
    """
    events = []

    # Signals we care about — use whichever are present
    candidate_cols = [
        'RPM', 'THROTTLE_POS', 'THROTTLE', 'ENGINE_LOAD',
        'COOLANT_TEMP', 'MAF', 'KNOCK_RETARD', 'LTFT',
    ]
    signal_cols = [c for c in candidate_cols if c in df.columns]

    if len(signal_cols) < 2 or len(df) < 50:
        return events  # not enough data to be meaningful

    signal_df = df[signal_cols].fillna(method='ffill').fillna(0)

    scaler = MinMaxScaler()
    scaled = scaler.fit_transform(signal_df)

    # ── Isolation Forest ────────────────────────────────────────────────────
    iso = IsolationForest(contamination=0.05, random_state=42, n_estimators=100)
    iso_labels = iso.fit_predict(scaled)          # -1 = anomaly, 1 = normal
    iso_scores = iso.decision_function(scaled)    # lower = more anomalous

    anomaly_mask = iso_labels == -1
    anomaly_pct = anomaly_mask.mean() * 100

    if anomaly_pct > 3.0:
        # Find which signals contributed most to anomalies
        anomalous_df = signal_df[anomaly_mask]
        normal_df    = signal_df[~anomaly_mask]

        deviating_signals = []
        for col in signal_cols:
            if anomalous_df[col].mean() > normal_df[col].mean() * 1.15:
                deviating_signals.append(col)

        confidence = min(92, 60 + anomaly_pct * 2)
        evidence = (
            f'{anomaly_pct:.1f}% of samples flagged as anomalous by Isolation Forest'
        )
        if deviating_signals:
            evidence += f'. Elevated signals: {", ".join(deviating_signals)}'

        events.append({
            'type': 'multivariate_anomaly_detected',
            'severity': 'medium' if anomaly_pct > 8 else 'low',
            'confidence': round(confidence, 1),
            'evidence': evidence,
            'meta': {
                'method': 'isolation_forest',
                'anomaly_pct': round(anomaly_pct, 2),
                'deviating_signals': deviating_signals,
            }
        })

    # Coolant anomaly specifically — high value for Acty reports
    if 'COOLANT_TEMP' in df.columns:
        coolant_idx = signal_cols.index('COOLANT_TEMP')
        coolant_anomalies = anomaly_mask & (scaled[:, coolant_idx] > 0.75)
        if coolant_anomalies.sum() > 5:
            events.append({
                'type': 'coolant_thermal_anomaly',
                'severity': 'high',
                'confidence': 80.0,
                'evidence': (
                    f'Coolant temperature behaved anomalously in '
                    f'{coolant_anomalies.sum()} samples during high-signal periods'
                ),
                'meta': {'method': 'isolation_forest'}
            })

    # ── LSTM Autoencoder ────────────────────────────────────────────────────
    if TORCH_AVAILABLE and len(df) >= 80:
        seq_len = 30
        sequences = _make_sequences(scaled, seq_len=seq_len)

        if len(sequences) >= 10:
            recon_errors = _lstm_reconstruction_errors(sequences)
            threshold = np.percentile(recon_errors, 95)
            high_error_pct = (recon_errors > threshold).mean() * 100

            # Only flag if the top-5% errors are meaningfully worse than median
            if recon_errors.max() > recon_errors.median() * 2.5:
                worst_window_start = int(np.argmax(recon_errors))
                events.append({
                    'type': 'sequential_behavior_anomaly',
                    'severity': 'medium',
                    'confidence': min(88, 65 + high_error_pct),
                    'evidence': (
                        f'LSTM autoencoder detected unusual sequential signal pattern '
                        f'near sample {worst_window_start * 1} '
                        f'(reconstruction error {recon_errors.max():.4f} vs median {np.median(recon_errors):.4f})'
                    ),
                    'meta': {
                        'method': 'lstm_autoencoder',
                        'worst_window_start': worst_window_start,
                        'max_recon_error': round(float(recon_errors.max()), 4),
                        'median_recon_error': round(float(np.median(recon_errors)), 4),
                    }
                })

    return events