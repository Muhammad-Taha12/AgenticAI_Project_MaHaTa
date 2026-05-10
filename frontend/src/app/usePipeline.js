import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { applyEdit, fetchEditHistory, fetchJobResult, rerunPhase, startJob, undoEdit } from "./api.js";

const defaultPrompt = "A hopeful astronaut discovers a glowing ocean beneath Mars.";

function loadPrompt() {
  try { return localStorage.getItem("agentic.prompt") || defaultPrompt; } catch { return defaultPrompt; }
}
function savePrompt(value) {
  try { localStorage.setItem("agentic.prompt", value); } catch {}
}

export function usePipeline() {
  const [prompt, setPrompt]       = useState(loadPrompt);
  const [job, setJob]             = useState(null);
  const [result, setResult]       = useState(null);
  const [error, setError]         = useState("");
  const [editHistory, setEditHistory] = useState([]);
  const [canUndo, setCanUndo]     = useState(false);
  const [editBusy, setEditBusy]   = useState(false);
  const streamRef = useRef(null);

  const isBusy = job?.status === "running" || job?.status === "pending";

  useEffect(() => { savePrompt(prompt); }, [prompt]);
  useEffect(() => () => { streamRef.current?.close(); }, []);

  const stopStream = useCallback(() => {
    streamRef.current?.close();
    streamRef.current = null;
  }, []);

  const syncResult = useCallback(async (jobId) => {
    try {
      const payload = await fetchJobResult(jobId);
      setResult(payload);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to load results");
    }
  }, []);

  const syncHistory = useCallback(async (jobId) => {
    try {
      const payload = await fetchEditHistory(jobId);
      setEditHistory(payload.history || []);
      setCanUndo(payload.can_undo || false);
    } catch { /* history is non-critical */ }
  }, []);

  const attachStream = useCallback((jobId) => {
    stopStream();
    const stream = new EventSource(`/events/${jobId}`);
    streamRef.current = stream;
    stream.onmessage = (event) => {
      const snapshot = JSON.parse(event.data);
      setJob(snapshot);
      syncResult(snapshot.job_id);
      if (snapshot.status === "completed" || snapshot.status === "failed") {
        stopStream();
        syncHistory(snapshot.job_id);
      }
    };
    stream.onerror = () => stopStream();
  }, [stopStream, syncResult, syncHistory]);

  const launch = useCallback(async () => {
    setError(""); setResult(null); setEditHistory([]); setCanUndo(false);
    try {
      const created = await startJob(prompt);
      setJob({ ...created, phases: { 1: "pending", 2: "pending", 3: "pending" }, progress: 0, message: "Job queued" });
      attachStream(created.job_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to start job");
    }
  }, [attachStream, prompt]);

  const replayStage = useCallback(async (phaseId) => {
    if (!job?.job_id) return;
    setError("");
    try {
      await rerunPhase(job.job_id, phaseId, prompt);
      attachStream(job.job_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to rerun phase");
    }
  }, [attachStream, job?.job_id, prompt]);

  const submitEdit = useCallback(async (instruction) => {
    if (!job?.job_id || editBusy) return;
    setError(""); setEditBusy(true);
    try {
      const res = await applyEdit(job.job_id, instruction);
      if (!res.success) {
        setError(res.error || "Edit failed");
      } else {
        attachStream(job.job_id);
      }
      await syncHistory(job.job_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Edit failed");
    } finally {
      setEditBusy(false);
    }
  }, [job?.job_id, editBusy, attachStream, syncHistory]);

  const submitUndo = useCallback(async () => {
    if (!job?.job_id || !canUndo || editBusy) return;
    setError(""); setEditBusy(true);
    try {
      const res = await undoEdit(job.job_id);
      if (!res.success) {
        setError(res.error || "Undo failed");
      } else {
        attachStream(job.job_id);
      }
      await syncHistory(job.job_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Undo failed");
    } finally {
      setEditBusy(false);
    }
  }, [job?.job_id, canUndo, editBusy, attachStream, syncHistory]);

  const summary = useMemo(() => ({
    id: job?.job_id || "—",
    status: job?.status || "idle",
    progress: job?.progress ?? 0,
    message: job?.message || "Ready",
  }), [job]);

  return {
    prompt, setPrompt, job, result, error, isBusy, summary,
    launch, replayStage,
    editHistory, canUndo, editBusy, submitEdit, submitUndo,
  };
}
