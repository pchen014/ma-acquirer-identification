import React, { useState } from 'react';

const SAMPLE_PROMPTS = [
  {
    label: "Healthcare Services (~$200M EV)",
    text: "A $200M Healthcare Services company in the Southeast with 20% EBITDA margin, private, mid-market profile, looking for strategic or platform add-on."
  },
  {
    label: "Physician Groups (~$300M EV)",
    text: "A $300M multi-specialty physician group network in the Southeast with 15% EBITDA margin and private ownership."
  },
  {
    label: "Health IT Platform (~$120M EV)",
    text: "A $120M Health IT revenue cycle management software company in the Northeast with 22% EBITDA margin and high growth."
  }
];

export default function TargetInputForm({ onSubmit, loading }) {
  const [promptText, setPromptText] = useState(SAMPLE_PROMPTS[0].text);
  const [topK, setTopK] = useState(10);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!promptText.trim()) return;
    onSubmit(promptText, topK);
  };

  return (
    <div className="glass-panel" id="target-input-panel">
      <div className="panel-header">
        <h2 className="panel-title">
          <span>🎯</span> Target Profile & Banker Prompt
        </h2>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label className="form-label" htmlFor="target-prompt-input">
            Target Company Description (Free-Form Natural Language)
          </label>
          <textarea
            id="target-prompt-input"
            className="prompt-textarea"
            value={promptText}
            onChange={(e) => setPromptText(e.target.value)}
            placeholder="e.g. A $200M healthcare services company in the Southeast with 20% EBITDA margin, private..."
            disabled={loading}
          />
        </div>

        <div className="quick-prompts">
          <span style={{ fontSize: '11px', color: 'var(--text-muted)', alignSelf: 'center' }}>Samples:</span>
          {SAMPLE_PROMPTS.map((sample, idx) => (
            <button
              key={idx}
              type="button"
              className="quick-prompt-btn"
              onClick={() => setPromptText(sample.text)}
              disabled={loading}
              id={`quick-prompt-${idx}`}
            >
              {sample.label}
            </button>
          ))}
        </div>

        <div className="form-controls-row">
          <div className="top-k-wrapper">
            <label className="form-label" style={{ marginBottom: 0 }} htmlFor="top-k-select">
              Return:
            </label>
            <select
              id="top-k-select"
              className="top-k-select"
              value={topK}
              onChange={(e) => setTopK(e.target.value)}
              disabled={loading}
            >
              <option value={5}>Top 5 Acquirers</option>
              <option value={10}>Top 10 Acquirers</option>
              <option value={20}>Top 20 Acquirers</option>
              <option value={50}>Top 50 Acquirers</option>
            </select>
          </div>

          <button
            type="submit"
            className="btn-primary"
            disabled={loading || !promptText.trim()}
            id="submit-recommendation-btn"
          >
            {loading ? (
              <>
                <div className="spinner" />
                <span>Evaluating Candidates with Gemini 3.8 Flash...</span>
              </>
            ) : (
              <>
                <span>⚡</span>
                <span>Identify Top Acquirers & Build Pitch</span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
