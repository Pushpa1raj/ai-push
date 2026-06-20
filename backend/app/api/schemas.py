from datetime import datetime

from pydantic import BaseModel, Field


class MessageOut(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationCreate(BaseModel):
    title: str = Field(default="New conversation")


class ConversationUpdate(BaseModel):
    title: str


class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationDetail(ConversationOut):
    messages: list[MessageOut] = []


class DocumentOut(BaseModel):
    id: str
    filename: str
    file_type: str
    file_size: int
    created_at: datetime
    chunk_count: int

    model_config = {"from_attributes": True}


class MemoryOut(BaseModel):
    id: str
    memory_type: str
    content: str
    category: str
    importance: int
    importance_score: float
    created_at: datetime
    last_accessed: datetime | None
    expires_at: datetime | None
    is_active: bool

    model_config = {"from_attributes": True}


class MemoryUpdate(BaseModel):
    content: str


class UserProfileOut(BaseModel):
    name: str | None
    college: str | None
    branch: str | None
    year: str | None
    sgpa: str | None
    preferred_language: str | None
    current_project: str | None

    model_config = {"from_attributes": True}
