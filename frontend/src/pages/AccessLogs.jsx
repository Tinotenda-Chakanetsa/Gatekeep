import { useCallback, useEffect, useState } from 'react';
import { api } from '../lib/api.js';
import { DecisionBadge, PageHeader, formatScore, formatTime } from '../components/ui.jsx';

const FILTERS = [
  { value: '', label: 'All' },
  { value: 'granted', label: 'Granted' },
  { value: 'denied', label: 'Denied' },
  { value: 'no_plate', label: 'No plate' },
];

export default function AccessLogs() {
  const [logs, setLogs] = useState([]);
  const [count, setCount] = useState(0);
  const [next, setNext] = useState(null);
  const [decision, setDecision] = useState('');
  const [loading, setLoading] = useState(true);
  const [preview, setPreview] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get(`/api/access-logs/?decision=${decision}`);
      setLogs(data.results || []);
      setNext(data.next);
      setCount(data.count || 0);
    } finally {
      setLoading(false);
    }
  }, [decision]);

  useEffect(() => {
    load();
  }, [load]);

  const loadMore = async () => {
    if (!next) return;
    setLoading(true);
    try {
      // DRF returns an absolute `next` URL; keep only path+query so it routes through the proxy.
      const rel = next.replace(/^https?:\/\/[^/]+/, '');
      const data = await api.get(rel);
      setLogs((prev) => [...prev, ...(data.results || [])]);
      setNext(data.next);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <PageHeader kicker="Audit" title="Access Logs" />

      <section className="page-section">
        <div className="panel">
          <div className="toolbar">
            <div className="filter-pills">
              {FILTERS.map((f) => (
                <button
                  key={f.value}
                  className={`pill ${decision === f.value ? 'active' : ''}`}
                  onClick={() => setDecision(f.value)}
                >
                  {f.label}
                </button>
              ))}
            </div>
            <span className="muted-copy">{count} total events</span>
          </div>

          {logs.length ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Capture</th>
                    <th>Read text</th>
                    <th>Plate</th>
                    <th>Owner</th>
                    <th>OCR</th>
                    <th>Direction</th>
                    <th>Decision</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map((log) => (
                    <tr key={log.id}>
                      <td>{formatTime(log.created_at)}</td>
                      <td>
                        {log.image_url ? (
                          <img
                            src={log.image_url}
                            alt="capture"
                            className="thumb clickable"
                            onClick={() => setPreview(log.image_url)}
                          />
                        ) : (
                          <span className="muted-copy">—</span>
                        )}
                      </td>
                      <td className="mono-cell">{log.raw_text || '—'}</td>
                      <td><strong>{log.normalized_plate || '—'}</strong></td>
                      <td>{log.owner_name || '—'}</td>
                      <td>{formatScore(log.ocr_confidence)}</td>
                      <td>{log.direction}</td>
                      <td><DecisionBadge decision={log.decision} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="empty-state">{loading ? 'Loading…' : 'No events match this filter.'}</div>
          )}

          {next ? (
            <div className="action-row" style={{ marginTop: 16 }}>
              <button className="btn btn-secondary" onClick={loadMore} disabled={loading}>
                {loading ? 'Loading…' : 'Load more'}
              </button>
            </div>
          ) : null}
        </div>
      </section>

      {preview ? (
        <div className="modal-backdrop" onMouseDown={() => setPreview(null)}>
          <img src={preview} alt="capture full" className="preview-full" onMouseDown={(e) => e.stopPropagation()} />
        </div>
      ) : null}
    </>
  );
}
