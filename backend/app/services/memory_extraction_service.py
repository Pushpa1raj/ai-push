import json

from app.services.ollama_service import OllamaService

VALID_CATEGORIES = {"personal", "education", "project", "preference", "goal", "other"}
VALID_TYPES = {"semantic", "episodic"}

SYSTEM_PROMPT = """
You are a highly precise memory extraction system. Analyze the user and assistant messages and extract two types of memories: 'semantic' (facts, preferences, knowledge) and 'episodic' (events, actions, experiences).

RULES:
- semantic: Facts, user preferences, long-term goals, affiliations, knowledge.
- episodic: Events that happened, actions taken, deployments, uploads, things done on a specific day.
- DO NOT save low-value facts, temporary questions, greetings, or random facts.

Each memory must include:
- type: "semantic" or "episodic"
- content: the memory text
- category: one of "personal", "education", "project", "preference", "goal", "other"
- importance: integer from 1 to 10

Format your response as a JSON list of objects. Return an empty list [] if nothing is worth remembering.

Example format:
[
  {"type": "semantic", "content": "User studies at Techno Main Salt Lake", "category": "education", "importance": 8},
  {"type": "semantic", "content": "User is building Phus AI", "category": "project", "importance": 9},
  {"type": "semantic", "content": "User's favorite color is blue", "category": "preference", "importance": 6},
  {"type": "episodic", "content": "User deployed Phus AI today", "category": "project", "importance": 7},
  {"type": "episodic", "content": "User uploaded a PDF yesterday", "category": "other", "importance": 5}
]
"""

def extract_memories(user_message: str, assistant_message: str, ollama_service: OllamaService, model: str = "qwen3:4b") -> list[dict[str, str]]:
    """
    Extracts potential memory candidates from a conversation turn.
    Returns a list of extracted memory dictionaries with 'type', 'content', 'category', and 'importance'.
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
            options={"temperature": 0.0},
            format="json"
        )
        content = response.get("message", {}).get("content", "").strip()
        print(f"[MEMORY PIPELINE] Raw extraction response: {content}")
        
        # Robustly extract JSON array or object from the response
        import re
        match = re.search(r'\[.*\]|\{.*\}', content, re.DOTALL)
        if match:
            content = match.group(0)
        else:
            print("[MEMORY PIPELINE] No JSON array or object found in response.")
            return []
            
        parsed_data = json.loads(content)
        
        # If the model returned a single object, wrap it in a list
        if isinstance(parsed_data, dict):
            memories = [parsed_data]
        elif isinstance(parsed_data, list):
            memories = parsed_data
        else:
            memories = []
            
        print(f"[MEMORY PIPELINE] Parsed {len(memories)} memories")
        if memories:
            valid_memories = []
            for m in memories:
                if isinstance(m, dict) and "type" in m and "content" in m:
                    # Extract and validate type
                    m_type = str(m["type"]).lower()
                    if m_type not in VALID_TYPES:
                        m_type = "semantic"  # default facts to semantic
                    
                    # Extract category, default to "other" if missing or invalid
                    category = str(m.get("category", "other")).lower()
                    if category not in VALID_CATEGORIES:
                        category = "other"
                    
                    # Extract importance, default to 5, clamp to 1-10
                    try:
                        importance = int(m.get("importance", 5))
                        importance = max(1, min(10, importance))
                    except (ValueError, TypeError):
                        importance = 5
                    
                    print(f"[MEMORY PIPELINE] Type: {m_type}")
                    print(f"[MEMORY PIPELINE] Category: {category}")
                    print(f"[MEMORY PIPELINE] Importance: {importance}")
                    
                    valid_memories.append({
                        "type": m_type,
                        "content": str(m["content"]),
                        "category": category,
                        "importance": importance,
                    })
            return valid_memories
    except Exception as e:
        print(f"[MEMORY PIPELINE] Error extracting memories: {e}")
        
    return []
