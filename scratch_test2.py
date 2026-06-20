import sys
import os

# Add the backend path to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

from app.services.ollama_service import OllamaService

user_msg = "My favorite color is blue"
assistant_msg = "That's such a lovely choice! Blue is versatile..."

# Increased timeout to 300s to see if it eventually completes
ollama_service = OllamaService(timeout=300.0)

from app.services.memory_extraction_service import SYSTEM_PROMPT

prompt = f"USER MESSAGE: {user_msg}\nASSISTANT MESSAGE: {assistant_msg}\n\nExtract memories based on the rules."
messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": prompt}
]

print("Sending request to Ollama...")
response = ollama_service.generate(
    model="qwen3:4b",
    messages=messages,
    options={"temperature": 0.0}
)
print("Response from Ollama:")
print(response.get("message", {}).get("content", ""))
