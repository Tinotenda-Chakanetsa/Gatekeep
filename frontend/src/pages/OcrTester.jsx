import { useEffect, useRef, useState } from 'react';
import { API_BASE } from '../lib/api.js';
import { PageHeader, formatScore } from '../components/ui.jsx';

export default function OcrTester() {
  const inputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  useEffect(() => {
    if (!file) {
      setPreviewUrl('');
      return undefined;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const onPick = (f) => {
    setFile(f || null);
    setResult(null);
    setError('');
  };

  const run = async () => {
    if (!file) {
      setError('Choose an image first.');
      return;
    }
    const data = new FormData();
    data.append('image', file);
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/ocr/`, { method: 'POST', body: data });
      const json = await res.json();
      if (!res.ok) throw new Error(json.details || json.error || 'OCR failed.');
      setResult(json);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <PageHeader kicker="Diagnostics" title="OCR Tester" />

      <section className="hero-grid">
        <div className="panel upload-panel">
          <div className="section-heading">
            <div>
              <span className="panel-kicker">Input</span>
              <h2>Upload &amp; Run</h2>
            </div>
          </div>
          <div
            className="drop-zone"
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              onPick(e.dataTransfer.files?.[0]);
            }}
          >
            <span className="drop-icon">+</span>
            <p>{file ? file.name : 'Drag and drop a car image here'}</p>
            <span className="drop-caption">Manually test the YOLO + PaddleOCR pipeline</span>
            <div className="action-row">
              <button className="btn" onClick={() => inputRef.current?.click()}>Choose Image</button>
              {file ? <button className="btn btn-secondary" onClick={() => onPick(null)}>Clear</button> : null}
            </div>
            <input ref={inputRef} type="file" accept="image/*" hidden onChange={(e) => onPick(e.target.files?.[0])} />
          </div>
          <div className="action-row action-row-main">
            <button className="btn btn-primary" onClick={run} disabled={loading}>
              {loading ? 'Running…' : 'Run Detection + OCR'}
            </button>
          </div>
          {error ? <div className="alert error">{error}</div> : null}
        </div>

        <section className="panel output-panel">
          <div className="section-heading">
            <div>
              <span className="panel-kicker">Output</span>
              <h2>Extracted Plate</h2>
            </div>
          </div>
          <div className="selected-text-box">{result?.selected_text || 'No plate text extracted yet.'}</div>
          <div className="summary-notes">
            <div>
              <span>Plate detected</span>
              <strong>{result ? (result.plate_detected ? 'Yes' : 'No') : '—'}</strong>
            </div>
            <div>
              <span>Avg OCR score</span>
              <strong>{formatScore(result?.average_score)}</strong>
            </div>
            <div>
              <span>Winning reader</span>
              <strong>{result?.selected_source ? readerLabel(result.selected_source) : '—'}</strong>
            </div>
          </div>
        </section>
      </section>

      {result?.readers ? (
        <section className="panel">
          <div className="section-heading">
            <div>
              <span className="panel-kicker">Diagnostics</span>
              <h2>Reader Comparison</h2>
            </div>
          </div>
          <p style={{ marginTop: 0, color: 'var(--muted, #8a8a8a)' }}>
            Both readers run on every capture; the higher-confidence result wins (with a small bias
            toward the character detector since it is purpose-built for plate fonts).
          </p>
          <div className="hero-grid" style={{ marginTop: '1rem' }}>
            <ReaderCard
              title="Character detector (YOLO)"
              reader={result.readers.char_detector}
              isWinner={result.selected_source === 'char_detector'}
              unavailableHint="Drop plate_char_detector.pt into backend/models/ and restart to enable."
            />
            <ReaderCard
              title="PaddleOCR"
              reader={result.readers.paddle}
              isWinner={result.selected_source === 'paddle'}
            />
          </div>
        </section>
      ) : null}

      <section className="content-grid">
        <section className="panel media-panel">
          <div className="section-heading"><h2>Original</h2></div>
          {previewUrl ? <img src={previewUrl} alt="preview" className="preview-image" /> : <div className="empty-state">No image selected.</div>}
        </section>
        {result?.detection?.annotated_image_base64 ? (
          <section className="panel media-panel">
            <div className="section-heading"><h2>YOLO Detection</h2></div>
            <img src={result.detection.annotated_image_base64} alt="annotated" className="preview-image" />
          </section>
        ) : (
          <section className="panel media-panel">
            <div className="section-heading"><h2>Detected Crop</h2></div>
            {result?.detection?.crop_image_base64 ? (
              <img src={result.detection.crop_image_base64} alt="crop" className="preview-image" />
            ) : (
              <div className="empty-state">Run OCR to see detection output.</div>
            )}
          </section>
        )}
      </section>
    </>
  );
}

function readerLabel(source) {
  if (source === 'char_detector') return 'Character detector';
  if (source === 'paddle') return 'PaddleOCR';
  return source;
}

function ReaderCard({ title, reader, isWinner, unavailableHint }) {
  const available = reader?.available !== false;
  const items = reader?.items || [];
  return (
    <div className="panel" style={{ border: isWinner ? '2px solid var(--accent, #4caf50)' : undefined }}>
      <div className="section-heading">
        <div>
          <span className="panel-kicker">{isWinner ? 'Winner' : 'Reader'}</span>
          <h3 style={{ margin: 0 }}>{title}</h3>
        </div>
      </div>
      {!available ? (
        <div className="empty-state">
          Not loaded. {unavailableHint || 'Model file missing on the backend.'}
        </div>
      ) : (
        <>
          <div className="selected-text-box" style={{ fontSize: '1.4rem' }}>
            {reader?.joined_text || <em style={{ opacity: 0.6 }}>(no text)</em>}
          </div>
          <div className="summary-notes">
            <div>
              <span>Avg score</span>
              <strong>{formatScore(reader?.average_score)}</strong>
            </div>
            <div>
              <span>Items</span>
              <strong>{reader?.item_count ?? 0}</strong>
            </div>
          </div>
          {items.length ? (
            <div style={{ marginTop: '0.75rem', display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
              {items.map((item, idx) => (
                <span
                  key={idx}
                  title={`score: ${formatScore(item.score)}`}
                  style={{
                    padding: '0.2rem 0.5rem',
                    border: '1px solid var(--border, #444)',
                    borderRadius: 4,
                    fontFamily: 'monospace',
                    fontSize: '0.9rem',
                  }}
                >
                  {item.text}
                </span>
              ))}
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}
