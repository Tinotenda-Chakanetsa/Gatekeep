import { useEffect } from 'react';

export default function Modal({ title, onClose, children, footer }) {
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div className="modal panel" onMouseDown={(e) => e.stopPropagation()}>
        <div className="section-heading">
          <h2>{title}</h2>
          <button type="button" className="btn btn-secondary modal-close" onClick={onClose}>
            ✕
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer ? <div className="modal-footer action-row">{footer}</div> : null}
      </div>
    </div>
  );
}
