import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

class EmbeddingService:
    def __init__(self, base_url: str = "http://localhost:11434", timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def embed_text(self, text: str, model: str = "nomic-embed-text") -> list[float]:
        """
        Generates an embedding vector for the given text using Ollama's /api/embed endpoint.
        """
        payload = {
            "model": model,
            "input": text,
        }
        
        request = Request(
            f"{self.base_url}/api/embed",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        
        try:
            with urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
                
                # /api/embed returns a list of embeddings under the 'embeddings' key
                embeddings = result.get("embeddings")
                if not embeddings or not isinstance(embeddings, list) or len(embeddings) == 0:
                    raise RuntimeError("No embeddings returned from Ollama")
                    
                return embeddings[0]
                
        except HTTPError as error:
            detail = error.read().decode("utf-8")
            raise RuntimeError(f"Ollama embedding request failed: {error.code} {detail}") from error
        except URLError as error:
            raise RuntimeError(f"Unable to connect to Ollama at {self.base_url}") from error

# Instantiate a global instance for easy import
embedding_service = EmbeddingService()
