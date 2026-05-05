import { RotateCcw } from "lucide-react";

import { STAGE_DEFINITIONS, STAGE_LABELS } from "../app/constants.js";

function StageBadge({ state }) {
  return <span className={`badge badge-${state}`}>{STAGE_LABELS[state] ?? state}</span>;
}

export function StageRail({ job, disabled, onReplay }) {
  return (
    <section className="card stack">
      <div className="card-heading">
        <h2>Pipeline stages</h2>
        <p>Each stage can be replayed independently from the latest job snapshot.</p>
      </div>

      <div className="stage-list">
        {STAGE_DEFINITIONS.map((stage) => {
          const status = job?.phases?.[String(stage.id)] ?? "pending";
          return (
            <article className={`stage-row stage-${status}`} key={stage.id}>
              <div className="stage-index">{stage.id}</div>
              <div className="stage-copy">
                <div className="stage-title">
                  <strong>{stage.label}</strong>
                  <StageBadge state={status} />
                </div>
                <p>{stage.hint}</p>
              </div>
              <button
                type="button"
                className="icon-action"
                onClick={() => onReplay(stage.id)}
                disabled={disabled || !job?.job_id}
                aria-label={`Replay ${stage.label}`}
                title={`Replay ${stage.label}`}
              >
                <RotateCcw size={16} />
              </button>
            </article>
          );
        })}
      </div>
    </section>
  );
}
