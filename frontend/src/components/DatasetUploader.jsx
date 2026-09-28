import React, { useState } from 'react';
import { uploadDealsCsv } from '../services/api';

export default function DatasetUploader({ onUploadSuccess }) {
  const [uploading, setUploading] = useState(false);
  const [feedback, setFeedback] = useState(null);
  const [error, setError] = useState(null);

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setFeedback(null);
    setError(null);

    try {
      const res = await uploadDealsCsv(file);
      setFeedback(
        `Ingested ${res.closed_records_ingested} Closed deals. ${res.acquirers_updated} acquirers recomputed.`
      );
      if (onUploadSuccess) onUploadSuccess();
    } catch (err) {
      setError(err.message || 'CSV upload failed');
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  return (
    <div className="glass-panel" id="dataset-uploader-panel">
      <div className="panel-header">
        <h2 className="panel-title">
          <span>📁</span> Deal History Database
        </h2>
      </div>

      <label className="dropzone" id="csv-dropzone">
        <input
          type="file"
          accept=".csv"
          onChange={handleFileChange}
          style={{ display: 'none' }}
          disabled={uploading}
          id="csv-file-input"
        />
        <div className="dropzone-icon">📥</div>
        <div className="dropzone-text">
          {uploading ? 'Processing & Ingesting Deals...' : 'Click to Upload Deals CSV'}
        </div>
        <div className="dropzone-subtext">Filters Closed deals & auto-deduplicates</div>
      </label>

      {feedback && (
        <div className="upload-feedback" id="upload-feedback-msg">
          ✓ {feedback}
        </div>
      )}

      {error && (
        <div className="upload-feedback" style={{ background: 'rgba(244, 63, 94, 0.1)', borderColor: 'rgba(244, 63, 94, 0.3)', color: '#fb7185' }}>
          ✕ {error}
        </div>
      )}
    </div>
  );
}
