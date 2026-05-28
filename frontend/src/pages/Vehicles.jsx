import { useCallback, useEffect, useState } from 'react';
import { api } from '../lib/api.js';
import { useAuth } from '../auth/AuthContext.jsx';
import Modal from '../components/Modal.jsx';
import { Field, PageHeader, formatTime } from '../components/ui.jsx';

const EMPTY = { owner: '', display_plate: '', make: '', model: '', color: '', is_active: true };

export default function Vehicles() {
  const { isAdmin } = useAuth();
  const [vehicles, setVehicles] = useState([]);
  const [people, setPeople] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null); // null | {} (new) | vehicle
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get(`/api/vehicles/?search=${encodeURIComponent(search)}`);
      setVehicles(data.results || []);
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    api.get('/api/people/').then((d) => setPeople(d.results || [])).catch(() => {});
  }, []);

  const openNew = () => {
    setForm({ ...EMPTY, owner: people[0]?.id || '' });
    setError('');
    setEditing({});
  };
  const openEdit = (v) => {
    setForm({
      owner: v.owner,
      display_plate: v.display_plate,
      make: v.make,
      model: v.model,
      color: v.color,
      is_active: v.is_active,
    });
    setError('');
    setEditing(v);
  };

  const save = async () => {
    setSaving(true);
    setError('');
    try {
      const payload = { ...form, owner: Number(form.owner) };
      if (editing.id) {
        await api.patch(`/api/vehicles/${editing.id}/`, payload);
      } else {
        await api.post('/api/vehicles/', payload);
      }
      setEditing(null);
      load();
    } catch (err) {
      setError(err.data?.display_plate?.[0] || err.data?.owner?.[0] || err.message);
    } finally {
      setSaving(false);
    }
  };

  const remove = async (v) => {
    if (!window.confirm(`Delete vehicle ${v.display_plate}?`)) return;
    await api.del(`/api/vehicles/${v.id}/`);
    load();
  };

  return (
    <>
      <PageHeader
        kicker="Registry"
        title="Vehicles"
        actions={
          isAdmin ? (
            <button className="btn btn-primary" onClick={openNew} disabled={!people.length}>
              + Register Vehicle
            </button>
          ) : null
        }
      />

      <section className="page-section">
        <div className="panel">
          <div className="toolbar">
            <input
              className="search-input"
              placeholder="Search plate…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          {loading ? (
            <div className="empty-state">Loading…</div>
          ) : vehicles.length ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Plate</th>
                    <th>Owner</th>
                    <th>Make / Model</th>
                    <th>Color</th>
                    <th>Status</th>
                    <th>Added</th>
                    {isAdmin ? <th /> : null}
                  </tr>
                </thead>
                <tbody>
                  {vehicles.map((v) => (
                    <tr key={v.id}>
                      <td><strong>{v.display_plate}</strong></td>
                      <td>{v.owner_name}</td>
                      <td>{[v.make, v.model].filter(Boolean).join(' ') || '—'}</td>
                      <td>{v.color || '—'}</td>
                      <td>
                        <span className={`badge ${v.is_active ? 'good' : 'neutral'}`}>
                          {v.is_active ? 'active' : 'disabled'}
                        </span>
                      </td>
                      <td>{formatTime(v.created_at)}</td>
                      {isAdmin ? (
                        <td className="row-actions">
                          <button className="btn btn-secondary btn-sm" onClick={() => openEdit(v)}>Edit</button>
                          <button className="btn btn-secondary btn-sm danger" onClick={() => remove(v)}>Delete</button>
                        </td>
                      ) : null}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="empty-state">No vehicles registered yet.</div>
          )}
        </div>
      </section>

      {editing ? (
        <Modal
          title={editing.id ? 'Edit Vehicle' : 'Register Vehicle'}
          onClose={() => setEditing(null)}
          footer={
            <>
              <button className="btn btn-secondary" onClick={() => setEditing(null)}>Cancel</button>
              <button className="btn btn-primary" onClick={save} disabled={saving}>
                {saving ? 'Saving…' : 'Save'}
              </button>
            </>
          }
        >
          <Field label="Owner">
            <select value={form.owner} onChange={(e) => setForm({ ...form, owner: e.target.value })}>
              {people.map((p) => (
                <option key={p.id} value={p.id}>{p.full_name}{p.unit ? ` (${p.unit})` : ''}</option>
              ))}
            </select>
          </Field>
          <Field label="Plate number">
            <input
              value={form.display_plate}
              onChange={(e) => setForm({ ...form, display_plate: e.target.value })}
              placeholder="e.g. KDA 123A"
            />
          </Field>
          <div className="form-row">
            <Field label="Make">
              <input value={form.make} onChange={(e) => setForm({ ...form, make: e.target.value })} />
            </Field>
            <Field label="Model">
              <input value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })} />
            </Field>
          </div>
          <Field label="Color">
            <input value={form.color} onChange={(e) => setForm({ ...form, color: e.target.value })} />
          </Field>
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
            />
            <span>Active (grants gate access)</span>
          </label>
          {error ? <div className="alert error">{error}</div> : null}
        </Modal>
      ) : null}
    </>
  );
}
