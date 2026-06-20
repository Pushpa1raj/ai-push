from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import StreamingResponse
import time

from app.api.conversations import router as conversations_router
from app.api.documents import router as documents_router
from app.api.memories import router as memories_router
from app.api.profile import router as profile_router
from app.core.database import SessionLocal, init_db
from app.core.utils import generate_conversation_title
from app.models.conversation import Conversation
from app.models.message import Message
from app.services.ollama_service import OllamaService


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    init_db()
    from app.core.config import get_active_model
    from app.services.ollama_service import OllamaService
    ollama = OllamaService()
    try:
        models = ollama.list_models()
        active = get_active_model()
        if not any(m.get("name") == active or m.get("name").startswith(active + ":") for m in models.get("models", [])):
            print(f"WARNING: Configured model {active} not found in Ollama.")
    except Exception as e:
        print(f"WARNING: Could not connect to Ollama to verify model: {e}")
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(conversations_router)
app.include_router(documents_router)
app.include_router(memories_router)
app.include_router(profile_router)
ollama_service = OllamaService()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/version")
def version() -> dict[str, str]:
    return {"version": "0.1.0"}


from app.services.retrieval_service import retrieve_chunks

def log_timing(msg: str):
    print(msg)
    with open("timing.log", "a") as f:
        f.write(msg + "\n")

@app.post("/chat")
def chat(request: dict, background_tasks: BackgroundTasks) -> StreamingResponse:
    from app.core.config import get_active_model
    model_name = get_active_model()
    model_name = get_active_model()
    print(f"[MODEL] Using model: {model_name} for chat request")
    
    t_start = time.time()
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
        
        from app.services.retrieval_service import retrieve_chunks, retrieve_memories, is_profile_query, get_cached_profile_summary
        
        # Memory retrieval step
        t0 = time.time()
        try:
            is_profile = is_profile_query(user_msg_content)
            if is_profile:
                profile_text = get_cached_profile_summary(db, top_k=10)
                top_memories = []
                t_profile = time.time() - t0
                log_timing(f"[TIMING] Profile Retrieval: {t_profile:.2f}s")
            else:
                top_memories = retrieve_memories(user_msg_content, db, top_k=5)
                profile_text = ""
                t_mem = time.time() - t0
                log_timing(f"[TIMING] Memory Retrieval: {t_mem:.2f}s")
        except Exception as e:
            print(f"Memory retrieval failed: {e}")
            top_memories = []
            is_profile = False
            profile_text = ""

        # RAG Retrieval step
        t0 = time.time()
        unique_sources = []
        try:
            top_chunks = retrieve_chunks(user_msg_content, db, top_k=3)
            if top_chunks:
                unique_filenames = {chunk.document.filename for chunk in top_chunks if chunk.document}
                unique_sources = sorted(list(unique_filenames))
        except Exception as e:
            print(f"Retrieval failed: {e}")
            top_chunks = []
        t_rag = time.time() - t0
        log_timing(f"[TIMING] RAG Retrieval: {t_rag:.2f}s")

    # Prepare modified messages for Ollama
    t0 = time.time()
    # For profile queries, keep only last 3 exchanges (6 msgs). Otherwise last 8.
    history_limit = 6 if is_profile else 8
    ollama_messages = list(request.get("messages", []))[-history_limit:]
    
    SYSTEM_PROMPT = "You are a helpful assistant. Answer directly. Use memory if relevant. Never reveal internal reasoning. Never output planning steps."
    ollama_messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})
    
    # Track per-section sizes for diagnostics
    section_sizes = {}
    
    if ollama_messages and (top_chunks or top_memories or is_profile):
        injected_content = ""
        
        if is_profile and profile_text:
            profile_block = f"=== PROFILE FACTS ===\n{profile_text}\n=== END PROFILE ===\n\n"
            injected_content += profile_block
            section_sizes["profile_block"] = len(profile_block)
            print("[PROFILE MODE] Injected structured profile context")
        elif top_memories:
            memories_text = "\n".join([f"- {mem.content}" for mem in top_memories])
            mem_block = f"Memory Facts:\n{memories_text}\n\n"
            injected_content += mem_block
            section_sizes["memory_block"] = len(mem_block)
            
        if top_chunks:
            context_text = "\n\n".join([chunk.content for chunk in top_chunks])
            rag_block = f"Context Facts:\n{context_text}\n\n"
            injected_content += rag_block
            section_sizes["rag_block"] = len(rag_block)
            
        injected_content += f"USER:\n{user_msg_content}"

        
        # Copy the last message and update content
        ollama_messages[-1] = dict(ollama_messages[-1])
        ollama_messages[-1]["content"] = injected_content
        
    t_prompt = time.time() - t0
    log_timing(f"[TIMING] Prompt Build: {t_prompt:.2f}s")
    
    # --- Detailed Prompt Size Analysis ---
    if ollama_messages:
        last_msg_content = ollama_messages[-1]["content"]
        total_prompt_chars = sum(len(m.get("content", "")) for m in ollama_messages)
        total_prompt_words = sum(len(m.get("content", "").split()) for m in ollama_messages)
        total_prompt_tokens_est = total_prompt_chars // 4
        
        log_timing("[PROMPT SIZE]")
        log_timing(f"  Total chars: {total_prompt_chars}")
        log_timing(f"  Total words: {total_prompt_words}")
        log_timing(f"  Estimated tokens: ~{total_prompt_tokens_est}")
        log_timing(f"  Memories injected: {len(top_memories)}")
        log_timing(f"  Chunks injected: {len(top_chunks)}")
        log_timing(f"  History messages: {len(ollama_messages)}")
        log_timing(f"  Is profile query: {is_profile}")
        
        # Per-section breakdown
        if section_sizes:
            log_timing("[PROMPT SECTIONS]")
            for section_name, size in section_sizes.items():
                log_timing(f"  {section_name}: {size} chars (~{size // 4} tokens)")
        
        # History section size (all messages except last which has injected content)
        history_chars = sum(len(m.get("content", "")) for m in ollama_messages[:-1])
        log_timing(f"  conversation_history: {history_chars} chars (~{history_chars // 4} tokens)")
        
        # Log final prompt payload
        log_timing("\n[FINAL PROMPT PAYLOAD SENT TO OLLAMA]")
        for m in ollama_messages:
            log_timing(f"[{m.get('role', 'unknown').upper()}]")
            log_timing(m.get("content", ""))
            log_timing("-" * 40)
        log_timing("=====================================\n")

    def _extract_and_save(user_msg, conv_id):
        import time
        t_ext_start = time.time()
        print("[ASYNC MEMORY] Started extraction")
        try:
            with SessionLocal() as db_session:
                from app.services.memory_service import process_and_save_memories
                process_and_save_memories(
                    user_message=user_msg,
                    conversation_id=conv_id,
                    ollama_service=ollama_service,
                    db=db_session
                )
        except Exception as e:
            print(f"[MEMORY PIPELINE] Error in background extraction thread: {e}")
        t_ext = time.time() - t_ext_start
        log_timing(f"[TIMING] Memory Extraction: {t_ext:.2f}s")
        log_timing("[ASYNC MEMORY] Completed extraction")

    def event_stream():
        t_llm_start = time.time()
        t_first_token = None
        t_first_visible_token = None
        token_count = 0
        raw_output = ""
        yielded_output = ""
        
        def filter_think(text: str) -> str:
            import re
            text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<think>.*$', '', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'</think>', '', text, flags=re.IGNORECASE)
            match = re.search(r'</?(?:t(?:h(?:i(?:n(?:k)?)?)?)?)?$', text, flags=re.IGNORECASE)
            if match:
                text = text[:match.start()]
            return text

        try:
            log_timing(f"[STREAMING] Ollama request started at {time.strftime('%H:%M:%S')}")
            for chunk in ollama_service.stream(
                model_name,
                ollama_messages,
                options=request.get("options"),
            ):
                content = chunk.get("message", {}).get("content")
                if content:
                    if t_first_token is None:
                        t_first_token = time.time()
                        log_timing(f"[STREAMING] Time to First Token (TTFT): {t_first_token - t_llm_start:.2f}s")
                    
                    raw_output += content
                    token_count += 1
                    
                    filtered = filter_think(raw_output)
                    if len(filtered) > len(yielded_output):
                        new_chars = filtered[len(yielded_output):]
                        yielded_output += new_chars
                        
                        if t_first_visible_token is None and new_chars.strip():
                            t_first_visible_token = time.time()
                            log_timing(f"[STREAMING] Time to First Visible Token: {t_first_visible_token - t_llm_start:.2f}s")
                            
                        yield f"data: {new_chars}\n\n"
                        
            import re
            final_filtered = re.sub(r'<think>.*?</think>', '', raw_output, flags=re.DOTALL | re.IGNORECASE)
            final_filtered = re.sub(r'<think>.*$', '', final_filtered, flags=re.DOTALL | re.IGNORECASE)
            final_filtered = re.sub(r'</think>', '', final_filtered, flags=re.IGNORECASE)
            
            if len(final_filtered) > len(yielded_output):
                new_chars = final_filtered[len(yielded_output):]
                yielded_output += new_chars
                yield f"data: {new_chars}\n\n"
                
            assistant_content = yielded_output
                
            if unique_sources:
                sources_text = "\n\n"
                for source in unique_sources:
                    sources_text += f"[Source: {source}]\n"
                    
                assistant_content += sources_text
                
                for char in sources_text:
                    yield f"data: {char}\n\n"
        finally:
            t_llm = time.time() - t_llm_start
            tokens_per_sec = token_count / t_llm if t_llm > 0 else 0
            log_timing(f"[STREAMING] Tokens generated: {token_count}")
            log_timing(f"[STREAMING] Generation speed: {tokens_per_sec:.1f} tokens/sec")
            log_timing(f"[TIMING] LLM Generation: {t_llm:.2f}s")
            t_req = time.time() - t_start
            log_timing(f"[TIMING] Total Request: {t_req:.2f}s")
            
            log_timing("\n[RAW MODEL OUTPUT]")
            log_timing(raw_output)
            log_timing("==================\n")
            
            if "<think>" in raw_output.lower() or "</think>" in raw_output.lower():
                think_len = len(raw_output) - len(assistant_content)
                log_timing(f"[THINK DETECTED] length={think_len} chars")
                log_timing("[THINK REMOVED]")
                
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
                    
                background_tasks.add_task(
                    _extract_and_save,
                    user_msg_content,
                    conversation_id
                )

    headers = {"x-conversation-id": conversation_id}
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers, background=background_tasks)
