import { Download, FileJson, Music2, Play } from "lucide-react";

function JsonBox({ title, value }) {
  return (
    <section className="mini-card">
      <div className="mini-card-title">
        <FileJson size={16} />
        <h3>{title}</h3>
      </div>
      <pre>{JSON.stringify(value ?? {}, null, 2)}</pre>
    </section>
  );
}

export function ArtifactPanel({ result }) {
  const audioUrl = result?.assets?.audio_url;
  const videoUrl = result?.assets?.video_url;

  return (
    <section className="card artifact-grid">
      <div className="card-heading">
        <h2>Outputs</h2>
        <p>Preview the generated media and the JSON handoff data from the latest run.</p>
      </div>

      <div className="media-shell">
        {videoUrl ? (
          <video controls src={videoUrl} />
        ) : (
          <div className="empty-media">
            <Play size={26} />
            <span>The final video will appear here</span>
          </div>
        )}
      </div>

      <div className="audio-shell">
        <div className="audio-label">
          <Music2 size={16} />
          <span>Audio</span>
        </div>
        {audioUrl ? <audio controls src={audioUrl} /> : <span className="muted">Waiting for phase 2</span>}
      </div>

      <a className={`download-link ${videoUrl ? "" : "is-disabled"}`} href={videoUrl || "#"} download aria-disabled={!videoUrl}>
        <Download size={16} />
        Download final MP4
      </a>

      <div className="json-grid">
        <JsonBox title="Story" value={result?.preview?.story} />
        <JsonBox title="Characters" value={result?.preview?.characters} />
        <JsonBox title="Script" value={result?.preview?.script} />
        <JsonBox title="Timing manifest" value={result?.preview?.timing_manifest} />
      </div>
    </section>
  );
}
