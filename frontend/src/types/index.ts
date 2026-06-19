export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
}

export type Model = "qwen3:4b" | "gemma3:4b" | "gemma4:e2b";

export const MODELS: readonly Model[] = ["qwen3:4b", "gemma3:4b", "gemma4:e2b"] as const;

export interface ChatRequest {
  model: Model;
  messages: Pick<Message, "role" | "content">[];
  options?: Record<string, unknown>;
  conversation_id?: string;
}

export * from "./conversation";
export * from "./document";
