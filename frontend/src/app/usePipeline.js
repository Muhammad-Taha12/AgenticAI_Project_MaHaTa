import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { fetchJobResult, rerunPhase, startJob } from "./api.js";

const defaultPrompt = "A hopeful astronaut discovers a glowing ocean beneath Mars.";

function loadPrompt() {
  try {
    return localStorage.getItem("agentic.prompt") || defaultPrompt;
  } catch {
    return defaultPrompt;
  }
}

function savePrompt(value) {
  try {
    localStorage.setItem("agentic.prompt", value);
  } catch {
    // Local storage is optional; the app still works without it.
  }
}

export function usePipeline() {
  const [prompt, setPrompt] = useState(loadPrompt);
  const [job, setJob] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const streamRef = useRef(null);

  const isBusy = job?.status === "running" || job?.status === "pending";

  useEffect(() => {
    savePrompt(prompt);
  }, [prompt]);

  useEffect(() => {
    return () => {
      streamRef.current?.close();
    };
  }, []);

  const stopStream = useCallback(() => {
    streamRef.current?.close();
    streamRef.current = null;
  }, []);

  const syncResult = useCallback(async (jobId) => {
    try {
      const payload = await fetchJobResult(jobId);
      setResult(payload);
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Unable to load results");
    }
  }, []);

  const attachStream = useCallback(
    (jobId) => {
      stopStream();
      const stream = new EventSource(`/events/${jobId}`);
      streamRef.current = stream;

      stream.onmessage = (event) => {
        const snapshot = JSON.parse(event.data);
        setJob(snapshot);
        syncResult(snapshot.job_id);

        if (snapshot.status === "completed" || snapshot.status === "failed") {
          stopStream();
        }
      };

      stream.onerror = () => {
        stopStream();
      };
    },
    [stopStream, syncResult],
  );

  const launch = useCallback(async () => {
    setError("");
    setResult(null);

    try {
      const created = await startJob(prompt);
      setJob({
        ...created,
        phases: { 1: "pending", 2: "pending", 3: "pending" },
        progress: 0,
        message: "Job queued",
      });
      attachStream(created.job_id);
    } catch (launchError) {
      setError(launchError instanceof Error ? launchError.message : "Unable to start job");
    }
  }, [attachStream, prompt]);

  const replayStage = useCallback(
    async (phaseId) => {
      if (!job?.job_id) return;

      setError("");
      try {
        await rerunPhase(job.job_id, phaseId, prompt);
        attachStream(job.job_id);
      } catch (phaseError) {
        setError(phaseError instanceof Error ? phaseError.message : "Unable to rerun phase");
      }
    },
    [attachStream, job?.job_id, prompt],
  );

  const summary = useMemo(() => {
    return {
      id: job?.job_id || "—",
      status: job?.status || "idle",
      progress: job?.progress ?? 0,
      message: job?.message || "Ready",
    };
  }, [job]);

  return {
    prompt,
    setPrompt,
    job,
    result,
    error,
    isBusy,
    summary,
    launch,
    replayStage,
  };
}
