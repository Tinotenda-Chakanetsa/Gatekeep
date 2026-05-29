import { useCallback, useEffect, useRef, useState } from 'react';
import { api, mediaUrl } from '../lib/api.js';
import { DecisionBadge, PageHeader, formatTime } from '../components/ui.jsx';

function MetricCard({ label, value, hint, tone = 'neutral' }) {
  return (
    <div className={`panel metric-card tone-${tone}`}>
      <span className="metric-label">{label}</span>
      <strong className="metric-value">{value}</strong>
      {hint ? <span className="metric-hint">{hint}</span> : null}
    </div>
  );
}

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [logs, setLogs] = useState([]);
  const [devices, setDevices] = useState([]);
  const [selectedDevice, setSelectedDevice] = useState('');
  const [opening, setOpening] = useState(false);
  const [notice, setNotice] = useState('');
  const lastLogId = useRef(0);

  const refresh = useCallback(async () => {
    try {
      const [statsData, logsData] = await Promise.all([
        api.get('/api/stats/'),
        api.get('/api/access-logs/?'),
      ]);
      setStats(statsData);
      const results = logsData.results || [];
      setLogs(results.slice(0, 12));
      if (results[0]?.id) lastLogId.current = results[0].id;
    } catch {
      /* transient: keep last good values */
    }
  }, []);

  useEffect(() => {
    refresh();
    api.get('/api/devices/').then((d) => {
      const list = d.results || [];
      setDevices(list);
      if (list[0]) setSelectedDevice(String(list[0].id));
    }).catch(() => setDevices([]));
    const timer = setInterval(refresh, 4000);
    return () => clearInterval(timer);
  }, [refresh]);

  const onManualOpen = async () => {
    setOpening(true);
    setNotice('');
    try {
      await api.post('/api/gate/open/', selectedDevice ? { device: Number(selectedDevice) } : {});
      setNotice('Gate open command issued.');
      refresh();
    } catch (err) {
      setNotice(err.message || 'Failed to open gate.');
    } finally {
      setOpening(false);
    }
  };

  return (
    <>
      <PageHeader
        kicker="Overview"
        title="Gate Control Dashboard"
        actions={
          <div className="manual-open">
            {devices.length > 0 ? (
              <select value={selectedDevice} onChange={(e) => setSelectedDevice(e.target.value)}>
                {devices.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} {d.is_online ? '· online' : '· offline'}
                  </option>
                ))}
              </select>
            ) : null}
            <button className="btn btn-primary open-gate-btn" onClick={onManualOpen} disabled={opening}>
              {opening ? 'Opening…' : 'Open Gate'}
            </button>
          </div>
        }
      />

      {notice ? <div className="page-section"><div className="alert">{notice}</div></div> : null}

      <section className="metrics-grid">
        <MetricCard label="Registered Vehicles" value={stats?.vehicles ?? '—'} hint="Active vehicles" tone="neutral" />
        <MetricCard
          label="Granted Today"
          value={stats?.today_granted ?? '—'}
          hint="Successful entries"
          tone="good"
        />
        <MetricCard label="Denied Today" value={stats?.today_denied ?? '—'} hint="Unrecognised plates" tone="bad" />
        <MetricCard
          label="Devices Online"
          value={stats ? `${stats.devices_online}/${stats.devices_total}` : '—'}
          hint="Gate cameras reporting"
          tone={stats?.devices_online ? 'good' : 'warn'}
        />
      </section>

      <section className="content-grid">
        <section className="panel table-panel span-2">
          <div className="section-heading">
            <div>
              <span className="panel-kicker">Live</span>
              <h2>Recent Gate Events</h2>
            </div>
            <span className="muted-copy">Auto-refreshes every 4s</span>
          </div>
          {logs.length ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Capture</th>
                    <th>Plate</th>
                    <th>Owner</th>
                    <th>Decision</th>
                    <th>Source</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map((log) => (
                    <tr key={log.id} className={log.id === lastLogId.current ? 'row-fresh' : ''}>
                      <td>{formatTime(log.created_at)}</td>
                      <td>
                        {log.image_url ? (
                          <img src={mediaUrl(log.image_url)} alt="capture" className="thumb" />
                        ) : (
                          <span className="muted-copy">—</span>
                        )}
                      </td>
                      <td>
                        <strong>{log.normalized_plate || log.raw_text || '—'}</strong>
                      </td>
                      <td>{log.owner_name || '—'}</td>
                      <td>
                        <DecisionBadge decision={log.decision} />
                      </td>
                      <td>{log.source}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="empty-state">No gate events yet. Trigger a capture to see live activity.</div>
          )}
        </section>
      </section>
    </>
  );
}
