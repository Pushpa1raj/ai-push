from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from app.services.ollama_service import OllamaService

app = FastAPI()
ollama_service = OllamaService()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/version")
def version() -> dict[str, str]:
    return {"version": "0.1.0"}


@app.post("/chat")
def chat(request: dict) -> StreamingResponse:
    def event_stream():
        for chunk in ollama_service.stream(
            request["model"],
            request["messages"],
            options=request.get("options"),
        ):
            content = chunk.get("message", {}).get("content")
            if content:
                yield f"data: {content}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
