import { useState } from "react";
import { RotateCcw, Wand2, Clock } from "lucide-react";

export function EditPanel({ job, canUndo, editBusy, onEdit, onUndo, history }) {
  const [instruction, setInstruction] = useState("");
  const isReady = job?.status === "completed" || job?.status === "failed";
  const disabled = !isReady || editBusy || !job?.job_id;

  function handleSubmit() {
    const trimmed = instruction.trim();
    if (!trimmed || disabled) return;
    onEdit(trimmed);
    setInstruction("");
  }

  function handleKey(e) {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) handleSubmit();
  }

  return (
    <section className="card edit-panel">
      <div className="card-heading">
        <h2>Edit agent</h2>
        <p>Natural-language edits — applied, then re-rendered.</p>
      </div>

      <label className="prompt-label" htmlFor="edit-instruction">instruction</label>
      <textarea
        id="edit-instruction"
        className="edit-textarea"
        value={instruction}
        onChange={(e) => setInstruction(e.target.value)}
        onKeyDown={handleKey}
        placeholder={
          isReady
            ? '// e.g. "make scene 2 more mysterious" or "rename char_001 to Elena"'
            : "// run the pipeline first, then edit here"
        }
        disabled={disabled}
        rows={4}
      />

      <div className="edit-actions">
        <button
          className="primary-action"
          type="button"
          onClick={handleSubmit}
          disabled={disabled || !instruction.trim()}
        >
          <Wand2 size={14} />
          apply edit
        </button>

        <button
          className="undo-action"
          type="button"
          onClick={onUndo}
          disabled={!canUndo || editBusy}
          title="Undo last edit and re-render"
        >
          <RotateCcw size={14} />
          undo
        </button>
      </div>

      {editBusy && (
        <p className="edit-status">
          <span className="edit-spinner" /> classifying &amp; applying…
        </p>
      )}

      {history.length > 0 && (
        <div className="edit-history">
          <div className="edit-history-heading">
            <Clock size={11} />
            <span>edit history ({history.length})</span>
          </div>
          <ol className="edit-history-list">
            {[...history].reverse().map((entry) => (
              <li key={entry.version} className="edit-history-entry">
                <span className="edit-version">v{entry.version}</span>
                <span className="edit-instruction-text">{entry.instruction}</span>
                <span className="edit-ts">{entry.timestamp?.slice(11, 19)}</span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </section>
  );
}
