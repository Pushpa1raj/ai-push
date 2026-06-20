import sys
import os

# Add the backend path to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

from app.services.embedding_service import embedding_service

print("Testing embedding...")
vec = embedding_service.embed_text("Test string")
print(f"Embedding length: {len(vec)}")
