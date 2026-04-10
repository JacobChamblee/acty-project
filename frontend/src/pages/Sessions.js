import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sidebar } from './Dashboard';
import { API_BASE } from '../config';
import './Sessions.css';

// ── Sessions page ─────────────────────────────────────────────────────────────
export default function Sessions() {
  const navigate = useNavigate();
  const [sessions, setSessions]     = useState([]);
  const [loading, setLoading]       = useState(true);
  const [uploading, setUploading]   = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [uploadOk, setUploadOk]     = useState('');

  const loadSessions = useCallback(() => {
    setLoading(true);
    fetch(`${API_BASE}/sessions`)
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(data => setSessions(data.sessions || []))
      .catch(() => setSessions([]))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { loadSessions(); }, [loadSessions]);

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadError('');
    setUploadOk('');
    const form = new FormData();
    form.append('file', file);
    try {
      const res = await fetch(`${API_BASE}/upload`, { method: 'POST', body: form });
      if (!res.ok) {
        const text = await res.text();
        setUploadError(`Upload failed (${res.status}): ${text.slice(0, 200)}`);
      } else {
        setUploadOk(`${file.name} uploaded successfully.`);
        loadSessions();
      }
    } catch (err) {
      setUploadError(err.message || 'Network error during upload.');
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const goInsights = (filename, e) => {
    e?.stopPropagation();
    navigate(`/insights?session=${encodeURIComponent(filename)}`);
  };

  const good = sessions.filter(s => !s.error);
  const bad  = sessions.filter(s => s.error);

  return (
    <div className="dashboard-layout">
      <Sidebar />
      <main className="dashboard-main">

        {/* Header */}
        <div className="ses-header">
          <div>
            <h1 className="ses-title">Sessions</h1>
            <p className="ses-sub">
              {loading ? 'Loading…' : `${good.length} drive session${good.length !== 1 ? 's' : ''} on server`}
            </p>
          </div>
          <div className="ses-header-actions">
            <label className={`btn btn-primary btn-sm ses-upload-btn${uploading ? ' disabled' : ''}`}>
              {uploading ? (
                <><span className="ses-spinner"/> Uploading…</>
              ) : (
                <>⬆ Upload CSV</>
              )}
              <input
                type="file"
                accept=".csv"
                style={{ display: 'none' }}
                onChange={handleUpload}
                disabled={uploading}
              />
            </label>
          </div>
        </div>

        {uploadError && <div className="ses-banner ses-banner-err">⚠ {uploadError}</div>}
        {uploadOk    && <div className="ses-banner ses-banner-ok">✓ {uploadOk}</div>}

        {/* Table */}
        <div className="ses-wrap">
          {loading ? (
            <div className="ses-state">
              <div className="ses-spinner-lg"/>
              <span>Loading sessions…</span>
            </div>
          ) : good.length === 0 ? (
            <div className="ses-state">
              <div className="ses-empty-icon">📂</div>
              <h3>No sessions yet</h3>
              <p>
                Upload a CSV exported from your OBD-II adapter, or sync from the Android app over WiFi.
              </p>
              <label className="btn btn-primary" style={{ cursor: 'pointer', marginTop: '0.5rem' }}>
                ⬆ Upload CSV
                <input type="file" accept=".csv" style={{ display: 'none' }} onChange={handleUpload} disabled={uploading}/>
              </label>
            </div>
          ) : (
            <table className="ses-table">
              <thead>
                <tr>
                  <th>Session</th>
                  <th>Date</th>
                  <th>Duration</th>
                  <th>Samples</th>
                  <th>Health</th>
                  <th>LTFT B1</th>
                  <th/>
                </tr>
              </thead>
              <tbody>
                {good.map(s => {
                  const ltft = s.ltft_b1 ?? s.avg_ltft_b1;
                  const health = s.health_score;
                  const label = s.filename
                    .replace(/^acty_obd_/, '')
                    .replace(/_[a-f0-9]{8}(-[a-f0-9]{4}){3}-[a-f0-9]{12}\.csv$/, '')
                    .replace(/\.csv$/, '');
                  return (
                    <tr
                      key={s.filename}
                      className="ses-row"
                      onClick={() => goInsights(s.filename)}
                      title="Click to analyze in AI Insights"
                    >
                      <td><span className="ses-id">{label}</span></td>
                      <td className="ses-dim">{s.session_date || '—'}</td>
                      <td className="ses-dim">
                        {s.duration_min != null ? `${s.duration_min} min` : '—'}
                      </td>
                      <td className="ses-dim">
                        {s.sample_count != null ? s.sample_count.toLocaleString() : '—'}
                      </td>
                      <td>
                        {health != null ? (
                          <span
                            className="ses-score"
                            style={{
                              color: health >= 75 ? '#10B981'
                                   : health >= 55 ? '#F59E0B'
                                   : '#EF4444',
                            }}
                          >
                            {health}
                          </span>
                        ) : '—'}
                      </td>
                      <td>
                        {ltft != null ? (
                          <span style={{ color: Math.abs(ltft) > 8 ? '#EF4444' : '#475569', fontWeight: 600 }}>
                            {ltft > 0 ? '+' : ''}{Number(ltft).toFixed(1)}%
                          </span>
                        ) : '—'}
                      </td>
                      <td>
                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={e => goInsights(s.filename, e)}
                        >
                          Analyze →
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}

          {bad.length > 0 && (
            <div className="ses-parse-err">
              {bad.length} session{bad.length > 1 ? 's' : ''} could not be parsed.
            </div>
          )}
        </div>

      </main>
    </div>
  );
}
