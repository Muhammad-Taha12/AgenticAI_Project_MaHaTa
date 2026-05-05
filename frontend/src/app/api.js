const JSON_HEADERS = { "Content-Type": "application/json" };

async function parseResponse(response) {
  if (response.ok) {
    return response.json();
  }

  const message = await response.text();
  throw new Error(message || "Request failed");
}

export async function startJob(prompt) {
  const response = await fetch("/run-pipeline", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ prompt }),
  });

  return parseResponse(response);
}

export async function rerunPhase(jobId, phaseId, prompt) {
  const response = await fetch(`/run-phase/${jobId}/${phaseId}`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ prompt }),
  });

  return parseResponse(response);
}

export async function fetchJobResult(jobId) {
  const response = await fetch(`/result/${jobId}`);
  return parseResponse(response);
}
