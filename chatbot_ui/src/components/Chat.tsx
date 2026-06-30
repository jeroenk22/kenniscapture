import { ArrowUp, Square } from "lucide-react";
import { useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { type Source, type ConversationMessage, sendMessageStream } from "../api";
import { ChatContainerContent, ChatContainerRoot } from "./prompt-kit/chat-container";
import { Loader } from "./prompt-kit/loader";
import { Message, MessageContent } from "./prompt-kit/message";
import {
  PromptInput,
  PromptInputAction,
  PromptInputActions,
  PromptInputTextarea,
} from "./prompt-kit/prompt-input";
import { Button } from "./ui/button";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
}

export default function Chat() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "Hallo! Ik ben de kennisassistent. Stel me een vraag over contracten — ik beantwoord alleen op basis van de vastgelegde kennis.",
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const handleSubmit = async () => {
    const text = input.trim();
    if (!text || isLoading) return;

    const userMessage: ChatMessage = {
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

    const controller = new AbortController();
    abortRef.current = controller;

    const assistantId = crypto.randomUUID();
    setMessages((prev) => [...prev, { id: assistantId, role: "assistant", content: "" }]);

    try {
      for await (const chunk of sendMessageStream(text, history, controller.signal)) {
        if (chunk.token) {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, content: m.content + chunk.token } : m,
            ),
          );
        }
        if (chunk.done) {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, sources: chunk.sources } : m,
            ),
          );
        }
      }
    } catch (err) {
      if (err instanceof Error && err.name !== "AbortError") {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, content: `Fout: ${err instanceof Error ? err.message : String(err)}` }
              : m,
          ),
        );
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleAction = () => {
    if (isLoading) {
      abortRef.current?.abort();
      setIsLoading(false);
      return;
    }
    void handleSubmit();
  };

  return (
    <div className="flex flex-col h-full max-w-3xl mx-auto">
      <ChatContainerRoot className="flex-1 px-4 py-6">
        <ChatContainerContent className="space-y-6 px-4 py-6">
          {messages.map((msg) => {
            const isUser = msg.role === "user";
            return (
              <Message
                key={msg.id}
                className={cn("flex w-full flex-col gap-1", isUser ? "items-end" : "items-start")}
              >
                <MessageContent
                  className={cn(
                    "max-w-[80%] text-sm leading-relaxed",
                    isUser
                      ? "bg-primary text-primary-foreground rounded-3xl rounded-br-sm px-4 py-2.5"
                      : "bg-secondary text-foreground rounded-3xl rounded-bl-sm px-4 py-2.5",
                  )}
                >
                  {msg.content}
                </MessageContent>
                {msg.sources && msg.sources.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-1">
                    {msg.sources.map((source) => (
                      <a
                        key={`${source.file}:${source.topic_label}`}
                        href={`http://${window.location.hostname}:8000/api/download/${encodeURIComponent(source.file)}`}
                        download={source.file}
                        className="text-xs bg-muted text-muted-foreground px-2 py-0.5 rounded-full hover:bg-muted/70 cursor-pointer no-underline"
                        title={source.passage ? `${source.file}${source.page != null ? ` — p. ${source.page}` : ""}\n\n"${source.passage.slice(0, 200)}"` : source.file}
                      >
                        {source.topic_label || source.file}
                        {source.page != null ? ` — p. ${source.page}` : ""}
                      </a>
                    ))}
                  </div>
                )}
              </Message>
            );
          })}
          {isLoading && messages[messages.length - 1]?.content === "" && (
            <Message className="items-start">
              <MessageContent className="bg-secondary rounded-3xl rounded-bl-sm px-4 py-3">
                <Loader variant="typing" size="sm" />
              </MessageContent>
            </Message>
          )}
        </ChatContainerContent>
      </ChatContainerRoot>

      <div className="shrink-0 px-4 pb-4">
        <PromptInput
          value={input}
          onValueChange={setInput}
          isLoading={isLoading}
          onSubmit={handleAction}
          className="w-full border-input bg-background"
        >
          <PromptInputTextarea placeholder="Stel een vraag over contracten... (Enter om te sturen)" />
          <PromptInputActions className="justify-end px-1 pb-1 pt-2">
            <PromptInputAction tooltip={isLoading ? "Genereren stoppen" : "Bericht versturen"}>
              <Button
                size="icon"
                className="size-8 rounded-full"
                disabled={!input.trim() && !isLoading}
                onClick={handleAction}
                aria-label={isLoading ? "Genereren stoppen" : "Bericht versturen"}
              >
                {isLoading ? (
                  <Square className="size-3 fill-current" />
                ) : (
                  <ArrowUp className="size-4" />
                )}
              </Button>
            </PromptInputAction>
          </PromptInputActions>
        </PromptInput>
        <p className="text-xs text-muted-foreground mt-2 text-center">
          Volledig lokaal — geen externe diensten
        </p>
      </div>
    </div>
  );
}
