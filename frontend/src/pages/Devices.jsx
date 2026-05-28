import { useCallback, useEffect, useState } from 'react';
import { api } from '../lib/api.js';
import Modal from '../components/Modal.jsx';
import { Field, PageHeader, formatTime } from '../components/ui.jsx';

export default function Devices() {
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ name: '', location: '' });
  const [revealed, setRevealed] = useState({});
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get('/api/devices/');
      setDevices(data.results || []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const create = async () => {
    setSaving(true);
    try {
      await api.post('/api/devices/', form);
      setCreating(false);
      setForm({ name: '', location: '' });
      load();
    } finally {
      setSaving(false);
    }
  };

  const regenerate = async (d) => {
    if (!window.confirm(`Regenerate key for ${d.name}? The old key stops working immediately.`)) return;
    await api.post(`/api/devices/${d.id}/regenerate_key/`);
    load();
  };

  const copyKey = (key) => navigator.clipboard?.writeText(key);

  return (
    <>
      <PageHeader
        kicker="Hardware"
        title="Gate Devices"
        actions={<button className="btn btn-primary" onClick={() => setCreating(true)}>+ Add Device</button>}
      />

      <section className="page-section">
        <div className="panel">
          {loading ? (
            <div className="empty-state">Loading…</div>
          ) : devices.length ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Location</th>
                    <th>Status</th>
                    <th>Last seen</th>
                    <th>API key</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {devices.map((d) => (
                    <tr key={d.id}>
                      <td><strong>{d.name}</strong></td>
                      <td>{d.location || '—'}</td>
                      <td>
                        <span className={`badge ${d.is_online ? 'good' : 'neutral'}`}>
                          {d.is_online ? 'online' : 'offline'}
                        </span>
                      </td>
                      <td>{formatTime(d.last_seen)}</td>
                      <td className="key-cell">
                        <code>{revealed[d.id] ? d.api_key : '••••••••••••••••'}</code>
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => setRevealed((r) => ({ ...r, [d.id]: !r[d.id] }))}
                        >
                          {revealed[d.id] ? 'Hide' : 'Show'}
                        </button>
                        <button className="btn btn-secondary btn-sm" onClick={() => copyKey(d.api_key)}>Copy</button>
                      </td>
                      <td>
                        <button className="btn btn-secondary btn-sm danger" onClick={() => regenerate(d)}>
                          Regenerate
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="empty-state">No devices registered. Add one to get an API key for your ESP32.</div>
          )}
        </div>
      </section>

      {creating ? (
        <Modal
          title="Add Gate Device"
          onClose={() => setCreating(false)}
          footer={
            <>
              <button className="btn btn-secondary" onClick={() => setCreating(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={create} disabled={saving || !form.name}>
                {saving ? 'Saving…' : 'Create'}
              </button>
            </>
          }
        >
          <Field label="Name">
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Main Gate Camera" />
          </Field>
          <Field label="Location">
            <input value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} placeholder="Front entrance" />
          </Field>
          <p className="muted-copy">A unique API key is generated automatically — copy it into your firmware config.</p>
        </Modal>
      ) : null}
    </>
  );
}
