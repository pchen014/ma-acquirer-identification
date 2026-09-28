import React, { useState, useEffect } from 'react';
import DatasetUploader from './components/DatasetUploader';
import TargetInputForm from './components/TargetInputForm';
import AcquirerCard from './components/AcquirerCard';
import { getDatabaseStats, recommendAcquirers } from './services/api';

export default function App() {
  const [stats, setStats] = useState({ total_closed_deals: 0, total_acquirers: 0 });
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const fetchStats = async () => {
    try {
      const data = await getDatabaseStats();
      setStats(data);
    } catch (e) {
      // Backend not yet ready or offline
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  const handleRecommend = async (targetInput, topK) => {
    setLoading(true);
    setError(null);
    try {
      const data = await recommendAcquirers(targetInput, topK);
      setResult(data);
    } catch (err) {
      setError(err.message || 'Recommendation failed. Please check the backend connection.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="brand-section">
          <div className="brand-icon">⚡</div>
          <div>
            <h1 className="brand-title">M&A Acquirer Identification Engine</h1>
            <div className="brand-subtitle">AI Innovation Team • Investment Banking Division</div>
          </div>
        </div>

        <div className="header-stats">
          <div className="stat-pill" id="stat-deals-pill">
            <div className="stat-dot" />
            <span>Closed Deals: <strong>{stats.total_closed_deals}</strong></span>
          </div>
          <div className="stat-pill" id="stat-acquirers-pill">
            <span>Acquirer Profiles: <strong>{stats.total_acquirers}</strong></span>
          </div>
        </div>
      </header>

      {/* Top Grid: Data Ingestion & Target Input */}
      <div className="top-grid">
        <DatasetUploader onUploadSuccess={fetchStats} />
        <TargetInputForm onSubmit={handleRecommend} loading={loading} />
      </div>

      {/* Error Banner */}
      {error && (
        <div className="upload-feedback" style={{ background: 'rgba(244, 63, 94, 0.1)', borderColor: 'rgba(244, 63, 94, 0.3)', color: '#fb7185', marginBottom: '24px' }}>
          ✕ {error}
        </div>
      )}

      {/* Results Section */}
      {result ? (
        <div className="results-section" id="results-deck">
          <div className="results-header">
            <div>
              <h2 style={{ fontSize: '20px', color: '#f8fafc' }}>
                Top {result.total_recommended} Potential Acquirers
              </h2>
              <div className="results-meta">
                <span className="meta-chip">Sector: <strong>{result.target_profile.sector}</strong></span>
                <span className="meta-chip">Target EV: <strong>${result.target_profile.deal_size_mm}M</strong></span>
                <span className="meta-chip">Region: <strong>{result.target_profile.geography}</strong></span>
                <span className="meta-chip">EBITDA Margin: <strong>{result.target_profile.ebitda_margin_pct}%</strong></span>
              </div>
            </div>

            {result.pdf_download_url && (
              <a
                href={result.pdf_download_url}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-download"
                id="download-pdf-btn"
              >
                <span>📄</span>
                <span>Download Pitch Book PDF (1-Page/Acquirer)</span>
              </a>
            )}
          </div>

          <div className="acquirers-list">
            {result.recommendations.map((acquirer, index) => (
              <AcquirerCard
                key={acquirer.acquirer_name + index}
                rank={index + 1}
                acquirer={acquirer}
              />
            ))}
          </div>
        </div>
      ) : (
        <div className="empty-state" id="empty-results-state">
          <div style={{ fontSize: '42px', marginBottom: '12px' }}>📊</div>
          <h3 style={{ fontSize: '18px', color: '#94a3b8', marginBottom: '6px' }}>
            No Target Profile Analyzed Yet
          </h3>
          <p style={{ fontSize: '13px', maxWidth: '480px', margin: '0 auto' }}>
            Type your target company description or click one of the quick sample presets above, then click <strong>Identify Top Acquirers & Build Pitch</strong>.
          </p>
        </div>
      )}
    </div>
  );
}
