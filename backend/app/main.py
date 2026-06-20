from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from app.api.conversations import router as conversations_router
from app.api.documents import router as documents_router
from app.api.memories import router as memories_router
from app.core.database import SessionLocal, init_db
from app.core.utils import generate_conversation_title
from app.models.conversation import Conversation
from app.models.message import Message
from app.services.ollama_service import OllamaService


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(conversations_router)
app.include_router(documents_router)
app.include_router(memories_router)
ollama_service = OllamaService()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/version")
def version() -> dict[str, str]:
    return {"version": "0.1.0"}


from app.services.retrieval_service import retrieve_chunks

@app.post("/chat")
def chat(request: dict) -> StreamingResponse:
    conversation_id = request.get("conversation_id")
    
    with SessionLocal() as db:
        if not conversation_id:
            user_msg_content = request["messages"][-1]["content"] if request.get("messages") else "New conversation"
            title = generate_conversation_title(user_msg_content) if user_msg_content else "New conversation"
            conversation = Conversation(title=title)
            db.add(conversation)
            db.commit()
            db.refresh(conversation)
            conversation_id = conversation.id
        
        user_msg_content = request["messages"][-1]["content"] if request.get("messages") else ""
        user_message = Message(
            conversation_id=conversation_id,
            role="user",
            content=user_msg_content
        )
        db.add(user_message)
        
        conversation = db.get(Conversation, conversation_id)
        if conversation:
            conversation.updated_at = datetime.now(timezone.utc)
            
        db.commit()
        
        from app.services.retrieval_service import retrieve_chunks, retrieve_memories
        
        # Memory retrieval step
        try:
            top_memories = retrieve_memories(user_msg_content, db, top_k=5)
        except Exception as e:
            print(f"Memory retrieval failed: {e}")
            top_memories = []

        # RAG Retrieval step
        unique_sources = []
        try:
            top_chunks = retrieve_chunks(user_msg_content, db, top_k=5)
            if top_chunks:
                unique_filenames = {chunk.document.filename for chunk in top_chunks if chunk.document}
                unique_sources = sorted(list(unique_filenames))
        except Exception as e:
            print(f"Retrieval failed: {e}")
            top_chunks = []

    # Prepare modified messages for Ollama
    ollama_messages = list(request.get("messages", []))
    if ollama_messages and (top_chunks or top_memories):
        injected_content = ""
        
        if top_memories:
            memories_text = "\n".join([f"- {mem.content}" for mem in top_memories])
            injected_content += f"MEMORIES:\n{memories_text}\n\n"
            
        if top_chunks:
            context_text = "\n\n".join([chunk.content for chunk in top_chunks])
            injected_content += f"CONTEXT:\n{context_text}\n\n"
            
        injected_content += f"USER:\n{user_msg_content}"
        
        # Copy the last message and update content
        ollama_messages[-1] = dict(ollama_messages[-1])
        ollama_messages[-1]["content"] = injected_content

    def event_stream():
        assistant_content = ""
        try:
            for chunk in ollama_service.stream(
                request["model"],
                ollama_messages,
                options=request.get("options"),
            ):
                content = chunk.get("message", {}).get("content")
                if content:
                    assistant_content += content
                    # We escape newlines just in case they're literal \n characters, 
                    # but Ollama streams tokens one by one which handles it fine.
                    yield f"data: {content}\n\n"
                    
            if unique_sources:
                sources_text = "\n\n"
                for source in unique_sources:
                    sources_text += f"[Source: {source}]\n"
                    
                assistant_content += sources_text
                
                # Stream the sources_text so the frontend UI renders it correctly
                # We yield character by character to safely avoid any SSE parser issues with internal newlines
                for char in sources_text:
                    yield f"data: {char}\n\n"
        finally:
            if assistant_content:
                with SessionLocal() as db:
                    assistant_message = Message(
                        conversation_id=conversation_id,
                        role="assistant",
                        content=assistant_content
                    )
                    db.add(assistant_message)
                    
                    conversation = db.get(Conversation, conversation_id)
                    if conversation:
                        conversation.updated_at = datetime.now(timezone.utc)
                        
                    db.commit()
                    
                import threading
                from app.services.memory_service import process_and_save_memories
                
                def _extract_and_save():
                    try:
                        with SessionLocal() as db:
                            process_and_save_memories(
                                user_message=user_msg_content,
                                assistant_message=assistant_content,
                                conversation_id=conversation_id,
                                ollama_service=ollama_service,
                                db=db,
                                model=request["model"]
                            )
                    except Exception as e:
                        print(f"[MEMORY PIPELINE] Error in background extraction thread: {e}")
                        
                threading.Thread(target=_extract_and_save).start()

    headers = {"x-conversation-id": conversation_id}
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)
