import { DocumentOut } from "../types/document";

const API_BASE = "/documents";

export async function listDocuments(): Promise<DocumentOut[]> {
  const response = await fetch(API_BASE);
  if (!response.ok) {
    throw new Error(`Failed to list documents: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

export async function uploadDocument(file: File): Promise<DocumentOut> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE}/upload`, {
    method: "POST",
    body: formData, // fetch will automatically set Content-Type to multipart/form-data with the correct boundary
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const errorData = await response.json();
      if (errorData.detail) detail = errorData.detail;
    } catch (e) {
      // ignore JSON parse error
    }
    throw new Error(`Failed to upload document: ${detail}`);
  }

  return response.json();
}

export async function deleteDocument(id: string): Promise<void> {
  const response = await fetch(`${API_BASE}/${id}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error(`Failed to delete document: ${response.status} ${response.statusText}`);
  }
}
