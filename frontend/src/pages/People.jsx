import { useCallback, useEffect, useState } from 'react';
import { api } from '../lib/api.js';
import { useAuth } from '../auth/AuthContext.jsx';
import Modal from '../components/Modal.jsx';
import { Field, PageHeader } from '../components/ui.jsx';

const EMPTY = { full_name: '', email: '', phone: '', unit: '', is_active: true, notes: '' };

export default function People() {
  const { isAdmin } = useAuth();
  const [people, setPeople] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get(`/api/people/?search=${encodeURIComponent(search)}`);
      setPeople(data.results || []);
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => {
    load();
  }, [load]);

  const openNew = () => {
    setForm(EMPTY);
    setError('');
    setEditing({});
  };
  const openEdit = (p) => {
    setForm({
      full_name: p.full_name,
      email: p.email,
      phone: p.phone,
      unit: p.unit,
      is_active: p.is_active,
      notes: p.notes,
    });
    setError('');
    setEditing(p);
  };

  const save = async () => {
    setSaving(true);
    setError('');
    try {
      if (editing.id) await api.patch(`/api/people/${editing.id}/`, form);
      else await api.post('/api/people/', form);
      setEditing(null);
      load();
    } catch (err) {
      setError(err.data?.full_name?.[0] || err.message);
    } finally {
      setSaving(false);
    }
  };

  const remove = async (p) => {
    if (!window.confirm(`Delete ${p.full_name} and all their vehicles?`)) return;
    await api.del(`/api/people/${p.id}/`);
    load();
  };

  return (
    <>
      <PageHeader
        kicker="Registry"
        title="People"
        actions={isAdmin ? <button className="btn btn-primary" onClick={openNew}>+ Add Person</button> : null}
      />

      <section className="page-section">
        <div className="panel">
          <div className="toolbar">
            <input
              className="search-input"
              placeholder="Search name, unit, email…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          {loading ? (
            <div className="empty-state">Loading…</div>
          ) : people.length ? (
            <div className="card-list">
              {people.map((p) => (
                <div key={p.id} className="panel person-card">
                  <div className="person-head">
                    <div>
                      <strong className="person-name">{p.full_name}</strong>
                      <span className="muted-copy">{p.unit || 'No unit'} · {p.phone || 'No phone'}</span>
                    </div>
                    <span className={`badge ${p.is_active ? 'good' : 'neutral'}`}>
                      {p.is_active ? 'active' : 'inactive'}
                    </span>
                  </div>
                  <div className="person-vehicles">
                    {p.vehicles?.length ? (
                      p.vehicles.map((v) => (
                        <span key={v.id} className={`plate-chip ${v.is_active ? '' : 'muted'}`}>
                          {v.display_plate}
                        </span>
                      ))
                    ) : (
                      <span className="muted-copy">No vehicles</span>
                    )}
                  </div>
                  {isAdmin ? (
                    <div className="row-actions">
                      <button className="btn btn-secondary btn-sm" onClick={() => openEdit(p)}>Edit</button>
                      <button className="btn btn-secondary btn-sm danger" onClick={() => remove(p)}>Delete</button>
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state">No people registered yet.</div>
          )}
        </div>
      </section>

      {editing ? (
        <Modal
          title={editing.id ? 'Edit Person' : 'Add Person'}
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
          <Field label="Full name">
            <input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
          </Field>
          <div className="form-row">
            <Field label="Unit">
              <input value={form.unit} onChange={(e) => setForm({ ...form, unit: e.target.value })} />
            </Field>
            <Field label="Phone">
              <input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
            </Field>
          </div>
          <Field label="Email">
            <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </Field>
          <Field label="Notes">
            <textarea rows={3} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          </Field>
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
            />
            <span>Active</span>
          </label>
          {error ? <div className="alert error">{error}</div> : null}
        </Modal>
      ) : null}
    </>
  );
}
