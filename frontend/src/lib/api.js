const ACCESS_KEY = 'gate_access';
const REFRESH_KEY = 'gate_refresh';

export const tokens = {
  get access() {
    return localStorage.getItem(ACCESS_KEY) || '';
  },
  get refresh() {
    return localStorage.getItem(REFRESH_KEY) || '';
  },
  set({ access, refresh }) {
    if (access) localStorage.setItem(ACCESS_KEY, access);
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

class ApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

async function refreshAccess() {
  const refresh = tokens.refresh;
  if (!refresh) return false;
  const res = await fetch('/api/auth/refresh/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh }),
  });
  if (!res.ok) return false;
  const data = await res.json();
  tokens.set({ access: data.access });
  return true;
}

function buildHeaders(extra, hasBody, isForm) {
  const headers = { ...extra };
  if (hasBody && !isForm) headers['Content-Type'] = 'application/json';
  const access = tokens.access;
  if (access) headers.Authorization = `Bearer ${access}`;
  return headers;
}

async function request(path, { method = 'GET', body, isForm = false, _retried = false } = {}) {
  const hasBody = body !== undefined && body !== null;
  const res = await fetch(path, {
    method,
    headers: buildHeaders({}, hasBody, isForm),
    body: hasBody ? (isForm ? body : JSON.stringify(body)) : undefined,
  });

  if (res.status === 401 && !_retried && tokens.refresh) {
    const refreshed = await refreshAccess();
    if (refreshed) return request(path, { method, body, isForm, _retried: true });
    tokens.clear();
  }

  const text = await res.text();
  const data = text ? JSON.parse(text) : null;

  if (!res.ok) {
    const message = data?.detail || data?.error || data?.details || `Request failed (${res.status})`;
    throw new ApiError(message, res.status, data);
  }
  return data;
}

export const api = {
  get: (path) => request(path),
  post: (path, body) => request(path, { method: 'POST', body }),
  postForm: (path, formData) => request(path, { method: 'POST', body: formData, isForm: true }),
  put: (path, body) => request(path, { method: 'PUT', body }),
  patch: (path, body) => request(path, { method: 'PATCH', body }),
  del: (path) => request(path, { method: 'DELETE' }),
};

export async function login(username, password) {
  const res = await fetch('/api/auth/login/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(data.detail || 'Invalid username or password.', res.status, data);
  }
  const data = await res.json();
  tokens.set({ access: data.access, refresh: data.refresh });
  return data;
}

export { ApiError };
