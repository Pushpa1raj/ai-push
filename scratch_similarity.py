import asyncio
from app.services.embedding_service import embedding_service
from app.services.retrieval_service import cosine_similarity

v1 = embedding_service.embed_text("User's favorite color is blue")
v2 = embedding_service.embed_text("User's favorite color is black")
v3 = embedding_service.embed_text("User studies at Techno Main Salt Lake")

print("blue vs black:", cosine_similarity(v1, v2))
print("blue vs college:", cosine_similarity(v1, v3))
