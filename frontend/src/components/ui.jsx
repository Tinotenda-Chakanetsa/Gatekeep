export function PageHeader({ kicker, title, actions }) {
  return (
    <header className="topbar">
      <div>
        {kicker ? <p className="eyebrow">{kicker}</p> : null}
        <h2 className="topbar-title">{title}</h2>
      </div>
      {actions ? <div className="topbar-status">{actions}</div> : null}
    </header>
  );
}

export function Field({ label, children }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}

export function DecisionBadge({ decision }) {
  const tone = decision === 'granted' ? 'good' : decision === 'denied' ? 'bad' : 'warn';
  const text = decision === 'no_plate' ? 'no plate' : decision;
  return <span className={`badge ${tone}`}>{text}</span>;
}

export function formatScore(score) {
  if (score === null || score === undefined || Number.isNaN(score)) return 'N/A';
  return `${(score * 100).toFixed(1)}%`;
}

export function formatTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString();
}
