import React from 'react';

export default function AcquirerCard({ acquirer, rank }) {
  const {
    acquirer_name,
    acquirer_type,
    conviction_level,
    conviction_rationale,
    acquirer_overview,
    strategic_fit_thesis,
    precedent_activity,
    valuation_context,
    risk_flags,
  } = acquirer;

  const convictionClass = conviction_level?.toLowerCase() || 'low';

  return (
    <div className="acquirer-card" id={`acquirer-card-${rank}`}>
      {/* Top Identity Row */}
      <div className="card-top-row">
        <div className="acquirer-identity">
          <span className="acquirer-rank">#{rank}</span>
          <span className="acquirer-name">{acquirer_name}</span>
          <span className="acquirer-type-badge">{acquirer_type}</span>
          {acquirer.composite_score ? (
            <span className="score-badge">Match: {(acquirer.composite_score * 100).toFixed(1)}%</span>
          ) : null}
        </div>

        <div className={`conviction-badge ${convictionClass}`}>
          <span>●</span>
          <span>{conviction_level} Conviction</span>
        </div>
      </div>

      {/* 6. Conviction Rationale Banner */}
      <div className="conviction-banner">
        <strong>Conviction Verdict:</strong> {conviction_rationale}
      </div>

      {/* Sections 1 & 2 */}
      <div className="sections-grid">
        <div className="section-block">
          <div className="section-title">1. Acquirer Overview & Footprint</div>
          <div className="section-content">{acquirer_overview}</div>
        </div>

        <div className="section-block">
          <div className="section-title">2. Strategic Fit Thesis</div>
          <div className="section-content">{strategic_fit_thesis}</div>
        </div>
      </div>

      {/* Sections 3 & 4 */}
      <div className="sections-grid">
        <div className="section-block">
          <div className="section-title">3. Verified Precedent Activity</div>
          <div className="section-content">{precedent_activity}</div>
        </div>

        <div className="section-block">
          <div className="section-title">4. Valuation Context & Multiples</div>
          <div className="section-content">{valuation_context}</div>
        </div>
      </div>

      {/* Section 5: Risk Flags */}
      <div className="risk-box">
        <div className="risk-title">
          <span>⚠️</span> 5. Key Transaction & Integration Risks
        </div>
        <ul className="risk-list">
          {risk_flags?.map((risk, idx) => (
            <li key={idx} className="risk-item">
              <span className="risk-bullet">•</span>
              <span>{risk}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
