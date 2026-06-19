import json

from app.services.ollama_service import OllamaService

SYSTEM_PROMPT = """
You are a highly precise memory extraction system. Analyze the user and assistant messages and extract two types of memories: 'episodic' (long-term facts) and 'conversational' (short-term recent activities).

RULES:
- episodic: High-value facts, user preferences, long-term goals, affiliations.
- conversational: What the user is currently doing, recent bugs, immediate sprint progress.
- DO NOT save low-value facts, temporary questions, greetings, or random facts.

Format your response as a JSON list of objects. Return an empty list [] if nothing is worth remembering.

Example format:
[
  {"type": "episodic", "content": "User prefers Hinglish"},
  {"type": "conversational", "content": "User was fixing sidebar bug"}
]
"""

def extract_memories(user_message: str, assistant_message: str, ollama_service: OllamaService, model: str = "qwen3:4b") -> list[dict[str, str]]:
    """
    Extracts potential memory candidates from a conversation turn.
    Returns a list of extracted memory dictionaries with 'type' and 'content'.
    """
    prompt = f"USER MESSAGE: {user_message}\nASSISTANT MESSAGE: {assistant_message}\n\nExtract memories based on the rules."
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt}
    ]
    
    try:
        response = ollama_service.generate(
            model=model,
            messages=messages,
            options={"temperature": 0.0}
        )
        content = response.get("message", {}).get("content", "").strip()
        
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        memories = json.loads(content)
        if isinstance(memories, list):
            valid_memories = []
            for m in memories:
                if isinstance(m, dict) and "type" in m and "content" in m:
                    valid_memories.append({"type": str(m["type"]), "content": str(m["content"])})
            return valid_memories
    except Exception as e:
        print(f"Warning: Failed to extract memories: {e}")
        
    return []
