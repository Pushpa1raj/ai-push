import { MemoryOut } from "../types/memory";

const API_BASE = "/memories";

export async function listMemories(): Promise<MemoryOut[]> {
  const response = await fetch(API_BASE);
  if (!response.ok) {
    throw new Error("Failed to list memories");
  }
  return response.json();
}

export async function updateMemory(id: string, content: string): Promise<MemoryOut> {
  const response = await fetch(`${API_BASE}/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!response.ok) {
    throw new Error("Failed to update memory");
  }
  return response.json();
}

export async function deleteMemory(id: string): Promise<void> {
  const response = await fetch(`${API_BASE}/${id}`, { method: "DELETE" });
  if (!response.ok) {
    throw new Error("Failed to delete memory");
  }
}
