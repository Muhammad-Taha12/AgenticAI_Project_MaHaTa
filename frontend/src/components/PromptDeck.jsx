import { Play, Sparkles } from "lucide-react";

export function PromptDeck({ prompt, setPrompt, onStart, disabled, summary, error }) {
  return (
    <section className="card prompt-card">
      <div className="hero-copy">
        <div className="brand-line">
          <Sparkles size={14} />
          <span>Agentic Video Pipeline</span>
        </div>
        <h1>One prompt.<br />Full pipeline.</h1>
        <p>
          Story, audio, and video stages run end-to-end locally.
          Watch each phase in real time, replay any stage independently.
        </p>
      </div>

      <label className="prompt-label" htmlFor="prompt">
        prompt
      </label>
      <textarea
        id="prompt"
        value={prompt}
        onChange={(event) => setPrompt(event.target.value)}
        placeholder="// Describe the short video you want to generate..."
      />

      <div className="prompt-actions">
        <button className="primary-action" type="button" onClick={onStart} disabled={disabled}>
          <Play size={14} />
          run pipeline
        </button>

        <div className="job-summary">
          <span>{summary.id === "—" ? "no active job" : `job:${summary.id.slice(0, 8)}`}</span>
          <strong>{summary.status}</strong>
          <small>{summary.progress}%</small>
        </div>
      </div>

      <div className="progress-shell" aria-label="Current job progress">
        <div className="progress-text">
          <span>{summary.message}</span>
          <strong>{summary.progress}%</strong>
        </div>
        <div className="progress-bar">
          <div style={{ width: `${summary.progress}%` }} />
        </div>
      </div>

      {error ? <p className="error-copy">{error}</p> : null}
    </section>
  );
}
