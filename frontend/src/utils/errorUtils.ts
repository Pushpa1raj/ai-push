/**
 * Convert an unknown error into a human-readable message suitable for
 * display in the UI. Handles common network and backend failure scenarios.
 */
export function toReadableError(err: unknown): string {
  if (
    err instanceof TypeError &&
    (err.message === "Failed to fetch" ||
      err.message === "NetworkError when attempting to fetch resource.")
  ) {
    return "Cannot reach the server. Please check that the backend is running.";
  }

  if (err instanceof Error) {
    const msg = err.message;

    if (msg.includes("502") || msg.includes("503") || msg.includes("504")) {
      return "The backend is temporarily unavailable. Please try again in a moment.";
    }
    if (msg.includes("500") && msg.toLowerCase().includes("ollama")) {
      return "Ollama is not reachable. Make sure it is installed and running.";
    }
    if (msg.includes("500")) {
      return "Something went wrong on the server. Please try again.";
    }

    return msg;
  }

  return "An unexpected error occurred. Please try again.";
}
