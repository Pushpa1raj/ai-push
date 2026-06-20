import sys
import os

# Add the backend path to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

from app.core.database import SessionLocal
from app.services.memory_service import process_and_save_memories
from app.services.ollama_service import OllamaService

user_msg = "My favorite color is blue"
assistant_msg = "That's such a lovely choice! Blue is versatile..."

ollama_service = OllamaService()

with SessionLocal() as db:
    print("Testing process_and_save_memories...")
    process_and_save_memories(
        user_message=user_msg,
        assistant_message=assistant_msg,
        conversation_id="test_conv_id",
        ollama_service=ollama_service,
        db=db,
        model="qwen3:4b"
    )
    print("Done testing process_and_save_memories.")
