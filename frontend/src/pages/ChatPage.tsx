import { useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github-dark.css";
import { Message, Model, MODELS } from "../types";
import { streamChat } from "../services/chatService";
import { toReadableError } from "../utils/errorUtils";

let nextId = 0;
function createId(): string {
  return `msg-${Date.now()}-${nextId++}`;
}

const ChatPage: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [model, setModel] = useState<Model>(MODELS[0]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || loading) return;

    const userMessage: Message = {
      id: createId(),
      role: "user",
      content: text,
    };

    const assistantId = createId();
    const updatedMessages = [...messages, userMessage];
    setMessages([
      ...updatedMessages,
      { id: assistantId, role: "assistant", content: "" },
    ]);
    setInput("");
    setError(null);
    setLoading(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamChat(
        {
          model,
          messages: updatedMessages.map(({ role, content }) => ({ role, content })),
        },
        (token) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantId
                ? { ...msg, content: msg.content + token }
                : msg,
            ),
          );
        },
        controller.signal,
      );
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        console.error("Failed to stream message:", err);
        setError(toReadableError(err));
        // Remove the empty assistant message on failure
        setMessages((prev) => prev.filter((msg) => msg.id !== assistantId));
      }
    } finally {
      abortRef.current = null;
      setLoading(false);
    }
  };

  const handleClear = () => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setMessages([]);
    setInput("");
    setError(null);
    setLoading(false);
  };

  return (
    <div>
      <div>
        <h1>Chat</h1>
        <select
          value={model}
          onChange={(e) => setModel(e.target.value as Model)}
          disabled={loading}
        >
          {MODELS.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
        <button onClick={handleClear} disabled={loading && !abortRef.current}>
          Clear Chat
        </button>
      </div>

      <div>
        {messages.length === 0 && <p>No messages yet.</p>}
        {messages.map((msg) => (
          <div key={msg.id}>
            <strong>{msg.role}:</strong>
            {msg.role === "assistant" ? (
              <ReactMarkdown rehypePlugins={[rehypeHighlight]}>
                {msg.content}
              </ReactMarkdown>
            ) : (
              <span> {msg.content}</span>
            )}
          </div>
        ))}
        {loading && <p>Generating…</p>}
      </div>

      {error && (
        <div role="alert">
          <p><strong>Error:</strong> {error}</p>
          <button onClick={() => setError(null)}>Dismiss</button>
        </div>
      )}

      <div>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSend();
          }}
          placeholder="Type a message…"
          disabled={loading}
        />
        <button onClick={handleSend} disabled={loading}>
          Send
        </button>
      </div>
    </div>
  );
};

export default ChatPage;
