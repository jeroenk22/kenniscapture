export interface ConversationMessage {
  role: "user" | "assistant";
  content: string;
}

export interface Source {
  file: string;
  passage: string;
  topic_label: string;
  page?: number | null;
}

export interface StreamChunk {
  token?: string;
  done?: boolean;
  sources?: Source[];
}

const API_BASE = `http://${window.location.hostname}:8000`;

export async function* sendMessageStream(
  message: string,
  history: ConversationMessage[],
  signal?: AbortSignal,
): AsyncGenerator<StreamChunk> {
  const response = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, conversation_history: history }),
    signal,
  });

  if (!response.ok || !response.body) {
    throw new Error(`API fout: ${response.status} ${response.statusText}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            yield JSON.parse(line.slice(6)) as StreamChunk;
          } catch {
            // ongeldige JSON-regel overslaan (bijv. Ollama foutmelding)
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

// Behoud voor backward compatibility met bestaande tests
export async function sendMessage(
  message: string,
  history: ConversationMessage[],
): Promise<{ answer: string; sources: Source[] }> {
  let answer = "";
  let sources: Source[] = [];
  for await (const chunk of sendMessageStream(message, history)) {
    if (chunk.token) answer += chunk.token;
    if (chunk.done && chunk.sources) sources = chunk.sources;
  }
  return { answer, sources };
}
