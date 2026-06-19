import { ConversationDetail, ConversationOut } from "../types/conversation";

const API_BASE = "/conversations";

export async function listConversations(): Promise<ConversationOut[]> {
  const response = await fetch(API_BASE);
  if (!response.ok) {
    throw new Error(`Failed to list conversations: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

export async function getConversation(id: string): Promise<ConversationDetail> {
  const response = await fetch(`${API_BASE}/${id}`);
  if (!response.ok) {
    throw new Error(`Failed to get conversation: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

export async function renameConversation(id: string, title: string): Promise<ConversationOut> {
  const response = await fetch(`${API_BASE}/${id}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ title }),
  });
  if (!response.ok) {
    throw new Error(`Failed to rename conversation: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

export async function deleteConversation(id: string): Promise<void> {
  const response = await fetch(`${API_BASE}/${id}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error(`Failed to delete conversation: ${response.status} ${response.statusText}`);
  }
}
