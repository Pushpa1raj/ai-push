class Settings:
    ACTIVE_MODEL: str = "gemma3:4b"  # Default model

settings = Settings()

def get_active_model() -> str:
    return settings.ACTIVE_MODEL
