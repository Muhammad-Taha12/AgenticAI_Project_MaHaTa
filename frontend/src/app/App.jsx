import { ArtifactPanel } from "../components/ArtifactPanel.jsx";
import { EditPanel } from "../components/EditPanel.jsx";
import { PromptDeck } from "../components/PromptDeck.jsx";
import { StageRail } from "../components/StageRail.jsx";
import { usePipeline } from "./usePipeline.js";

export function App() {
  const pipeline = usePipeline();

  return (
    <main className="app-shell">
      <section className="dashboard">
        <PromptDeck
          prompt={pipeline.prompt}
          setPrompt={pipeline.setPrompt}
          onStart={pipeline.launch}
          disabled={pipeline.isBusy}
          summary={pipeline.summary}
          error={pipeline.error}
        />
        <StageRail
          job={pipeline.job}
          onReplay={pipeline.replayStage}
          disabled={pipeline.isBusy}
        />
      </section>

      <section className="dashboard dashboard--bottom">
        <EditPanel
          job={pipeline.job}
          canUndo={pipeline.canUndo}
          editBusy={pipeline.editBusy}
          onEdit={pipeline.submitEdit}
          onUndo={pipeline.submitUndo}
          history={pipeline.editHistory}
        />
        <ArtifactPanel result={pipeline.result} />
      </section>
    </main>
  );
}
