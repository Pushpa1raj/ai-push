export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
}

export type Model = "gemma3:4b";

export const MODELS: readonly Model[] = ["gemma3:4b"] as const;

export interface ChatRequest {
  model: Model;
  messages: Pick<Message, "role" | "content">[];
  options?: Record<string, unknown>;
  conversation_id?: string;
}

export * from "./conversation";
export * from "./document";
