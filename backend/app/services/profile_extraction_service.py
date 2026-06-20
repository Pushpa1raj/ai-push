import json
from sqlalchemy.orm import Session

from app.models.memory import Memory
from app.models.user_profile import UserProfile
from app.services.ollama_service import OllamaService
from app.core.config import get_active_model

SYSTEM_PROMPT = """
You are a highly precise profile extraction system. Extract key profile information from the following semantic memories about the user.

You can extract the following fields:
- name: The user's name.
- college: The college or university the user attends.
- branch: The user's field of study, major, or branch (e.g. CSE, IT, ECE).
- year: The user's current year of study.
- sgpa: The user's SGPA or GPA.
- preferred_language: The user's preferred programming or spoken language.
- current_project: What the user is currently working on or building.

Return ONLY a JSON object containing the fields you found. If a field is not found in the memories, omit it or set it to null. Do NOT return an array. Return a single JSON object.

Example output:
{
  "college": "Techno Main Salt Lake",
  "preferred_language": "Hinglish",
  "current_project": "Phus AI"
}
"""

def update_profile_from_memories(memories: list[Memory], db: Session, ollama_service: OllamaService) -> None:
    """
    Analyzes semantic memories and updates the UserProfile.
    """
    semantic_memories = [m for m in memories if m.memory_type == "semantic"]
    if not semantic_memories:
        return

    memories_text = "\n".join([f"- {m.content}" for m in semantic_memories])
    prompt = f"MEMORIES:\n{memories_text}\n\nExtract profile fields based on the rules."

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt}
    ]

    try:
        model_name = get_active_model()
        print(f"[MODEL] Using model: {model_name} for profile extraction")
        response = ollama_service.generate(
            model=model_name,
            messages=messages,
            options={"temperature": 0.0},
            format="json"
        )
        content = response.get("message", {}).get("content", "").strip()
        
        import re
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            content = match.group(0)
        else:
            return

        parsed_data = json.loads(content)
        if not isinstance(parsed_data, dict):
            return

        # Fetch or create profile
        profile = db.query(UserProfile).first()
        if not profile:
            profile = UserProfile()
            db.add(profile)

        # Update fields if found
        updatable_fields = ["name", "college", "branch", "year", "sgpa", "preferred_language", "current_project"]
        updated = False

        for field in updatable_fields:
            val = parsed_data.get(field)
            if val is not None and str(val).strip():
                # Only update if changed
                current_val = getattr(profile, field)
                new_val = str(val).strip()
                if current_val != new_val:
                    setattr(profile, field, new_val)
                    print(f"[PROFILE] Updated {field}")
                    updated = True

        if updated:
            db.commit()

    except Exception as e:
        print(f"[PROFILE PIPELINE] Error extracting profile: {e}")
