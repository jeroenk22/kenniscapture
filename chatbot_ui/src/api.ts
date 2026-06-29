export interface ConversationMessage {
  role: "user" | "assistant";
  content: string;
}

export interface Source {
  file: string;
  passage: string;
  topic_label: string;
}

export interface ChatResponse {
  answer: string;
  sources: Source[];
}

export async function sendMessage(
  message: string,
  history: ConversationMessage[],
): Promise<ChatResponse> {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      conversation_history: history,
    }),
  });

  if (!response.ok) {
    throw new Error(`API fout: ${response.status} ${response.statusText}`);
  }

  return response.json() as Promise<ChatResponse>;
}
