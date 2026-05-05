import { Play, Sparkles } from "lucide-react";

export function PromptDeck({ prompt, setPrompt, onStart, disabled, summary, error }) {
  return (
    <section className="card prompt-card">
      <div className="hero-copy">
        <div className="brand-line">
          <Sparkles size={22} />
          <span>Agentic Video Pipeline</span>
        </div>
        <h1>Write one prompt, watch the whole pipeline unfold.</h1>
        <p>
          Story, audio, and video phases stay visible end-to-end, with reruns and media preview built in.
        </p>
      </div>

      <label className="prompt-label" htmlFor="prompt">
        Prompt
      </label>
      <textarea
        id="prompt"
        value={prompt}
        onChange={(event) => setPrompt(event.target.value)}
        placeholder="Describe the short video you want to generate..."
      />

      <div className="prompt-actions">
        <button className="primary-action" type="button" onClick={onStart} disabled={disabled}>
          <Play size={18} />
          Generate video
        </button>

        <div className="job-summary">
          <span>{summary.id === "—" ? "No job yet" : `Job ${summary.id.slice(0, 8)}`}</span>
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
