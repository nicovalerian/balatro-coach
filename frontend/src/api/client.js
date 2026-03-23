const API_BASE = import.meta.env.VITE_API_URL || "";

/**
 * Send a chat message (with optional image) and call callbacks as events arrive.
 *
 * @param {string} message
 * @param {File|null} imageFile
 * @param {{ onState: (state: object) => void, onText: (chunk: string) => void, onDone: () => void, onError: (err: Error) => void }} callbacks
 * @returns {AbortController} – call .abort() to cancel
 */
export function sendChatMessage(message, imageFile, { onState, onText, onDone, onError }) {
  const ctrl = new AbortController();

  const body = new FormData();
  body.append("message", message);
  if (imageFile) body.append("file", imageFile);

  fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    body,
    signal: ctrl.signal,
  })
    .then(async (res) => {
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`API error ${res.status}: ${text}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop(); // keep incomplete last line

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6).trim();
          if (raw === "[DONE]") {
            onDone();
            return;
          }
          try {
            const event = JSON.parse(raw);
            if (event.type === "state") onState(event.data);
            else if (event.type === "text") onText(event.data);
          } catch {
            // ignore malformed lines
          }
        }
      }
      onDone();
    })
    .catch((err) => {
      if (err.name !== "AbortError") onError(err);
    });

  return ctrl;
}

/**
 * Analyze a screenshot without asking a question.
 * Returns game state JSON.
 */
export async function analyzeScreenshot(file) {
  const body = new FormData();
  body.append("file", file);
  const res = await fetch(`${API_BASE}/api/analyze`, { method: "POST", body });
  if (!res.ok) throw new Error(`Analyze error: ${res.status}`);
  return res.json();
}
