import { useEffect, useRef, useState } from "react";
import { type ConversationMessage, sendMessage } from "../api";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Array<{ file: string; topic_label: string }>;
}

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 px-4 py-3 bg-white rounded-2xl rounded-bl-sm shadow-sm max-w-xs">
      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.3s]" />
      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.15s]" />
      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
    </div>
  );
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div className={`max-w-[75%] ${isUser ? "order-2" : "order-1"}`}>
        <div
          className={`px-4 py-3 rounded-2xl text-sm leading-relaxed ${
            isUser
              ? "bg-blue-600 text-white rounded-br-sm"
              : "bg-white text-gray-800 rounded-bl-sm shadow-sm"
          }`}
        >
          {message.content}
        </div>
        {message.sources && message.sources.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {message.sources.map((source, i) => (
              <span
                key={i}
                className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full"
                title={source.file}
              >
                📄 {source.topic_label || source.file}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "Hallo! Ik ben de kennisassistent. Stel me een vraag over contracten — ik beantwoord alleen op basis van de vastgelegde kennis.",
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || isLoading) return;

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    const history: ConversationMessage[] = messages
      .filter((m) => m.id !== "welcome")
      .map((m) => ({ role: m.role, content: m.content }));

    try {
      const response = await sendMessage(text, history);
      const assistantMessage: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: response.answer,
        sources: response.sources,
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      const errorMessage: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content:
          "Er is een fout opgetreden. Controleer of de backend draait op poort 8000.",
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full max-w-3xl mx-auto">
      {/* Berichtenlijst */}
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-1">
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
        {isLoading && (
          <div className="flex justify-start mb-4">
            <TypingIndicator />
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Invoerveld */}
      <div className="border-t border-gray-200 bg-white px-4 py-4">
        <div className="flex gap-3 items-end">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Stel een vraag over contracten... (Enter om te sturen)"
            rows={2}
            className="flex-1 resize-none border border-gray-300 rounded-xl px-4 py-3 text-sm
                       focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
                       disabled:opacity-50"
            disabled={isLoading}
          />
          <button
            onClick={() => void handleSend()}
            disabled={!input.trim() || isLoading}
            className="h-10 w-10 flex items-center justify-center bg-blue-600 text-white
                       rounded-xl hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed
                       transition-colors flex-shrink-0"
            aria-label="Verstuur"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
              />
            </svg>
          </button>
        </div>
        <p className="text-xs text-gray-400 mt-2 text-center">
          Antwoorden zijn gebaseerd op de vastgelegde kennisbank — volledig lokaal, geen externe diensten
        </p>
      </div>
    </div>
  );
}
