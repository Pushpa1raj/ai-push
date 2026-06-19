import { ChatRequest } from "../types";

const API_BASE = "/chat";
/**
 * Connect to the backend SSE stream for a chat request.
 *
 * Uses native `fetch` + `ReadableStream` to read the `text/event-stream`
 * response. Each SSE frame (`data: <token>\n\n`) is parsed and the token
 * text is forwarded to the `onToken` callback.
 *
 * @param request  – The chat payload (model, messages, options).
 * @param onToken  – Called once for every streamed token string.
 * @param signal   – Optional `AbortSignal` to cancel the stream.
 * @returns A promise that resolves when the stream ends.
 */
export async function streamChat(
  request: ChatRequest,
  onToken: (token: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(API_BASE, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal,
  });

  if (!response.ok) {
    throw new Error(`Chat stream failed: ${response.status} ${response.statusText}`);
  }

  const body = response.body;
  if (!body) {
    throw new Error("Response body is null — streaming not supported by the browser.");
  }

  const reader = body.getReader();
  const decoder = new TextDecoder();

  // Buffer for incomplete SSE frames that may span multiple chunks.
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // SSE frames are delimited by a blank line (\n\n).
      const frames = buffer.split("\n\n");

      // The last element is either empty (complete frame) or an
      // incomplete frame that we keep in the buffer.
      buffer = frames.pop() ?? "";

      for (const frame of frames) {
        for (const line of frame.split("\n")) {
          if (line.startsWith("data: ")) {
            const token = line.slice("data: ".length);
            onToken(token);
          }
        }
      }
    }

    // Process any remaining data left in the buffer.
    if (buffer.trim()) {
      for (const line of buffer.split("\n")) {
        if (line.startsWith("data: ")) {
          const token = line.slice("data: ".length);
          onToken(token);
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
