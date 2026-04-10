const API_BASE = import.meta.env.VITE_API_URL || "";

export function sendChatMessage(
  message,
  imageFiles,
  history,
  handSettings,
  { onState, onText, onDone, onError }
) {
  const ctrl = new AbortController();

  const body = new FormData();
  body.append("message", message);

  if (Array.isArray(imageFiles)) {
    imageFiles.forEach((file) => {
      body.append("files", file);
    });
  }

  if (Array.isArray(history) && history.length > 0) {
    body.append("history", JSON.stringify(history));
  }

  if (Array.isArray(handSettings) && handSettings.length > 0) {
    body.append("hand_settings", JSON.stringify(handSettings));
  }

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
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6).trim();

          if (raw === "[DONE]") {
            onDone();
            return;
          }

          let event;
          try {
            event = JSON.parse(raw);
          } catch {
            continue;
          }

          if (event.type === "state") onState(event.data);
          else if (event.type === "text") onText(event.data);
          else if (event.type === "error") throw new Error(event.data || "Chat stream failed");
        }
      }

      onDone();
    })
    .catch((error) => {
      if (error.name !== "AbortError") onError(error);
    });

  return ctrl;
}
