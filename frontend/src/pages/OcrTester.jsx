import { useEffect, useRef, useState } from 'react';
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
      const res = await fetch('/api/ocr/', { method: 'POST', body: data });
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
          </div>
        </section>
      </section>

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
