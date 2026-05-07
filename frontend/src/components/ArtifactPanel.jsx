import { Download, FileJson, Music2, Play } from "lucide-react";

function JsonBox({ title, value }) {
  return (
    <section className="mini-card">
      <div className="mini-card-title">
        <FileJson size={12} />
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
        <p>Preview generated media and JSON handoffs.</p>
      </div>

      <div className="media-shell">
        {videoUrl ? (
          <video controls src={videoUrl} />
        ) : (
          <div className="empty-media">
            <Play size={28} />
            <span>Awaiting video output</span>
          </div>
        )}
      </div>

      <div className="audio-shell">
        <div className="audio-label">
          <Music2 size={13} />
          <span>audio track</span>
        </div>
        {audioUrl
          ? <audio controls src={audioUrl} />
          : <span className="muted">// waiting for phase 2</span>
        }
      </div>

      <a
        className={`download-link ${videoUrl ? "" : "is-disabled"}`}
        href={videoUrl || "#"}
        download
        aria-disabled={!videoUrl}
      >
        <Download size={13} />
        export final mp4
      </a>

      <div className="json-grid">
        <JsonBox title="story" value={result?.preview?.story} />
        <JsonBox title="characters" value={result?.preview?.characters} />
        <JsonBox title="script" value={result?.preview?.script} />
        <JsonBox title="timing manifest" value={result?.preview?.timing_manifest} />
      </div>
    </section>
  );
}
