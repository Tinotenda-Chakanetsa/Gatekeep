import { useCallback, useEffect, useState } from 'react';
import { api } from '../lib/api.js';
import { useAuth } from '../auth/AuthContext.jsx';
import Modal from '../components/Modal.jsx';
import { Field, PageHeader } from '../components/ui.jsx';

const EMPTY = { username: '', email: '', first_name: '', last_name: '', role: 'operator', password: '', is_active: true };

export default function Users() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get('/api/users/');
      setUsers(data.results || []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const openNew = () => {
    setForm(EMPTY);
    setError('');
    setEditing({});
  };
  const openEdit = (u) => {
    setForm({ ...u, password: '' });
    setError('');
    setEditing(u);
  };

  const save = async () => {
    setSaving(true);
    setError('');
    try {
      const payload = { ...form };
      if (editing.id && !payload.password) delete payload.password;
      if (editing.id) await api.patch(`/api/users/${editing.id}/`, payload);
      else await api.post('/api/users/', payload);
      setEditing(null);
      load();
    } catch (err) {
      setError(err.data?.username?.[0] || err.message);
    } finally {
      setSaving(false);
    }
  };

  const remove = async (u) => {
    if (u.id === me.id) return;
    if (!window.confirm(`Delete user ${u.username}?`)) return;
    await api.del(`/api/users/${u.id}/`);
    load();
  };

  return (
    <>
      <PageHeader
        kicker="Administration"
        title="Dashboard Users"
        actions={<button className="btn btn-primary" onClick={openNew}>+ Add User</button>}
      />

      <section className="page-section">
        <div className="panel">
          {loading ? (
            <div className="empty-state">Loading…</div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Username</th>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Role</th>
                    <th>Status</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id}>
                      <td><strong>{u.username}</strong>{u.id === me.id ? ' (you)' : ''}</td>
                      <td>{[u.first_name, u.last_name].filter(Boolean).join(' ') || '—'}</td>
                      <td>{u.email || '—'}</td>
                      <td><span className={`badge ${u.role === 'admin' ? 'good' : 'neutral'}`}>{u.role}</span></td>
                      <td>{u.is_active ? 'active' : 'disabled'}</td>
                      <td className="row-actions">
                        <button className="btn btn-secondary btn-sm" onClick={() => openEdit(u)}>Edit</button>
                        {u.id !== me.id ? (
                          <button className="btn btn-secondary btn-sm danger" onClick={() => remove(u)}>Delete</button>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>

      {editing ? (
        <Modal
          title={editing.id ? 'Edit User' : 'Add User'}
          onClose={() => setEditing(null)}
          footer={
            <>
              <button className="btn btn-secondary" onClick={() => setEditing(null)}>Cancel</button>
              <button className="btn btn-primary" onClick={save} disabled={saving || !form.username}>
                {saving ? 'Saving…' : 'Save'}
              </button>
            </>
          }
        >
          <Field label="Username">
            <input value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} />
          </Field>
          <div className="form-row">
            <Field label="First name">
              <input value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} />
            </Field>
            <Field label="Last name">
              <input value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} />
            </Field>
          </div>
          <Field label="Email">
            <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </Field>
          <div className="form-row">
            <Field label="Role">
              <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                <option value="operator">Operator</option>
                <option value="admin">Administrator</option>
              </select>
            </Field>
            <Field label={editing.id ? 'New password (optional)' : 'Password'}>
              <input
                type="password"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                placeholder={editing.id ? 'Leave blank to keep' : ''}
              />
            </Field>
          </div>
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
