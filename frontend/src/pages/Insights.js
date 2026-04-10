import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Sidebar } from './Dashboard';
import { API_BASE } from '../config';
import './Insights.css';

// ── Suggested questions ───────────────────────────────────────────────────────
const SUGGESTIONS = [
  "Summarize the key findings from this drive session.",
  "Are there any concerning patterns in the fuel trim data?",
  "How does the engine load profile look? Any signs of stress?",
  "What does the battery voltage trend indicate about charging health?",
  "Are there any signs of a vacuum leak or MAF sensor issues?",
  "How was the engine warm-up? Any signs of thermostat problems?",
  "Give me an overall health assessment of the vehicle based on this data.",
];

// ── Helpers ────────────────────────────────────────────────────────────────────
function AlertBadge({ text }) {
  const isCrit = text.startsWith('CRITICAL');
  return (
    <span className={`ins-alert-badge ${isCrit ? 'crit' : 'warn'}`}>{text}</span>
  );
}

function ModelPill({ model, selected, onClick }) {
  return (
    <button
      className={`ins-model-pill ${selected ? 'selected' : ''}`}
      onClick={() => onClick(model.name)}
    >
      <span className="ins-model-name">{model.name}</span>
      {model.size_gb > 0 && (
        <span className="ins-model-size">{model.size_gb} GB</span>
      )}
    </button>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function Insights() {
  // Sessions
  const [sessions, setSessions]     = useState([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [selectedSession, setSelectedSession] = useState(null);  // filename string

  // Models
  const [models, setModels]         = useState([]);
  const [modelsLoading, setModelsLoading] = useState(true);
  const [modelsError, setModelsError]     = useState('');
  const [selectedModel, setSelectedModel] = useState('');

  // Query
  const [question, setQuestion]     = useState('');
  const [activeSuggestion, setActiveSuggestion] = useState(null);

  // Streaming state
  const [streaming, setStreaming]   = useState(false);
  const [response, setResponse]     = useState('');
  const [sessionMeta, setSessionMeta] = useState(null);
  const [streamError, setStreamError] = useState('');
  const responseRef = useRef(null);
  const readerRef = useRef(null);

  // ── Data fetching ────────────────────────────────────────────────────────────
  useEffect(() => {
    fetch(`${API_BASE}/sessions`)
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(data => {
        const list = (data.sessions || []).filter(s => !s.error);
        setSessions(list);
        if (list.length > 0) setSelectedSession(list[0].filename);
      })
      .catch(() => setSessions([]))
      .finally(() => setSessionsLoading(false));
  }, []);

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/ollama/models`)
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(data => {
        const list = data.models || [];
        setModels(list);
        if (list.length > 0) setSelectedModel(list[0].name);
        else setModelsError('No models found on Ollama server.');
      })
      .catch(() => setModelsError('Ollama server unreachable. Make sure it is running.'))
      .finally(() => setModelsLoading(false));
  }, []);

  // Auto-scroll response as tokens arrive
  useEffect(() => {
    if (responseRef.current) {
      responseRef.current.scrollTop = responseRef.current.scrollHeight;
    }
  }, [response]);

  // ── Analyze ──────────────────────────────────────────────────────────────────
  const handleAnalyze = useCallback(async () => {
    if (!selectedModel || streaming) return;
    const q = question.trim() || SUGGESTIONS[0];

    setStreaming(true);
    setResponse('');
    setSessionMeta(null);
    setStreamError('');

    try {
      const res = await fetch(`${API_BASE}/api/v1/ollama/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_filename: selectedSession || null,
          question: q,
          model: selectedModel,
        }),
      });

      if (!res.ok) {
        const err = await res.text();
        setStreamError(`Request failed (${res.status}): ${err}`);
        setStreaming(false);
        return;
      }

      const reader = res.body.getReader();
      readerRef.current = reader;
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split('\n');
        buffer = lines.pop(); // keep incomplete last line

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const data = line.slice(6);

          if (data === '[DONE]') {
            setStreaming(false);
            return;
          }
          if (data.startsWith('[ERROR]')) {
            setStreamError(data.slice(8));
            setStreaming(false);
            return;
          }
          // First event is JSON meta
          if (data.startsWith('{')) {
            try { setSessionMeta(JSON.parse(data)); } catch (_) {}
            continue;
          }
          // Token — replace escaped newlines
          setResponse(prev => prev + data.replace(/\\n/g, '\n'));
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        setStreamError(err.message || 'Connection failed.');
      }
    } finally {
      setStreaming(false);
    }
  }, [selectedModel, selectedSession, question, streaming]);

  const handleStop = () => {
    readerRef.current?.cancel();
    setStreaming(false);
  };

  const handleSuggestion = (s, i) => {
    setQuestion(s);
    setActiveSuggestion(i);
  };

  // ── Render ───────────────────────────────────────────────────────────────────
  const canAnalyze = selectedModel && !streaming;

  return (
    <div className="dashboard-layout">
      <Sidebar />
      <main className="dashboard-main insights-main">

        {/* ── Header ── */}
        <div className="ins-header">
          <div>
            <h1 className="ins-title">🤖 AI Insights</h1>
            <p className="ins-subtitle">
              Analyze your OBD-II session data with a local Ollama model running on your inference server.
            </p>
          </div>
          {sessionMeta && (
            <div className="ins-session-badge">
              <span className="ins-session-badge-label">Analyzing</span>
              <span className="ins-session-badge-val">{sessionMeta.session}</span>
              <span className="ins-session-badge-model">via {sessionMeta.model}</span>
            </div>
          )}
        </div>

        <div className="ins-layout">

          {/* ── Left panel: config ── */}
          <aside className="ins-panel ins-config-panel">

            {/* Session picker */}
            <div className="ins-section">
              <div className="ins-section-title">Session</div>
              {sessionsLoading ? (
                <p className="ins-dim">Loading sessions…</p>
              ) : sessions.length === 0 ? (
                <p className="ins-dim">No sessions found on server.</p>
              ) : (
                <select
                  className="ins-select"
                  value={selectedSession || ''}
                  onChange={e => setSelectedSession(e.target.value)}
                >
                  {sessions.map(s => (
                    <option key={s.filename} value={s.filename}>
                      {s.session_date || s.filename}
                      {s.sample_count ? ` · ${s.sample_count} pts` : ''}
                    </option>
                  ))}
                </select>
              )}
            </div>

            {/* Model picker */}
            <div className="ins-section">
              <div className="ins-section-title">Ollama Model</div>
              {modelsLoading ? (
                <p className="ins-dim">Connecting to Ollama…</p>
              ) : modelsError ? (
                <p className="ins-error">{modelsError}</p>
              ) : (
                <div className="ins-model-list">
                  {models.map(m => (
                    <ModelPill
                      key={m.name}
                      model={m}
                      selected={selectedModel === m.name}
                      onClick={setSelectedModel}
                    />
                  ))}
                </div>
              )}
            </div>

            {/* Suggested questions */}
            <div className="ins-section">
              <div className="ins-section-title">Suggested Questions</div>
              <div className="ins-suggestions">
                {SUGGESTIONS.map((s, i) => (
                  <button
                    key={i}
                    className={`ins-suggestion ${activeSuggestion === i ? 'active' : ''}`}
                    onClick={() => handleSuggestion(s, i)}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

          </aside>

          {/* ── Right panel: query + response ── */}
          <section className="ins-panel ins-chat-panel">

            {/* Question input */}
            <div className="ins-query-box">
              <textarea
                className="ins-textarea"
                placeholder="Ask anything about this session… or pick a suggestion on the left."
                value={question}
                onChange={e => { setQuestion(e.target.value); setActiveSuggestion(null); }}
                onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleAnalyze(); }}
                rows={3}
              />
              <div className="ins-query-actions">
                <span className="ins-hint">⌘ Enter to run</span>
                {streaming ? (
                  <button className="ins-btn ins-btn-stop" onClick={handleStop}>
                    ⏹ Stop
                  </button>
                ) : (
                  <button
                    className="ins-btn ins-btn-run"
                    onClick={handleAnalyze}
                    disabled={!canAnalyze}
                  >
                    ✦ Analyze
                  </button>
                )}
              </div>
            </div>

            {/* Alerts from session meta */}
            {sessionMeta?.alerts?.length > 0 && (
              <div className="ins-alerts-row">
                {sessionMeta.alerts.map((a, i) => <AlertBadge key={i} text={a} />)}
              </div>
            )}

            {/* Response area */}
            <div className="ins-response-wrap">
              {streamError ? (
                <div className="ins-stream-error">
                  <span>⚠ {streamError}</span>
                </div>
              ) : response ? (
                <div className="ins-response" ref={responseRef}>
                  <pre className="ins-response-text">
                    {response}
                    {streaming && <span className="ins-cursor">▋</span>}
                  </pre>
                  {!streaming && (
                    <div className="ins-response-footer">
                      <span>
                        {sessionMeta?.sample_count?.toLocaleString()} samples ·{' '}
                        {sessionMeta?.duration_min ? `${sessionMeta.duration_min} min · ` : ''}
                        {sessionMeta?.model}
                      </span>
                      <button
                        className="ins-copy-btn"
                        onClick={() => navigator.clipboard.writeText(response)}
                      >
                        Copy
                      </button>
                    </div>
                  )}
                </div>
              ) : (
                <div className="ins-empty-state">
                  {streaming ? (
                    <div className="ins-loading">
                      <div className="ins-spinner"/>
                      <span>Analyzing with {selectedModel}…</span>
                    </div>
                  ) : (
                    <>
                      <div className="ins-empty-icon">🔍</div>
                      <div className="ins-empty-title">Ready to analyze</div>
                      <div className="ins-empty-sub">
                        Select a session and model, then ask a question or pick a suggestion.
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>

          </section>
        </div>
      </main>
    </div>
  );
}
