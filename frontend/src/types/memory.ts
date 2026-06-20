export interface MemoryOut {
  id: string;
  memory_type: string;
  content: string;
  category: string;
  importance: number;
  importance_score: number;
  created_at: string;
  expires_at: string | null;
}
