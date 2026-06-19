import { Message } from "./index";

export interface ConversationOut {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail extends ConversationOut {
  messages: Message[];
}
