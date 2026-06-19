import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, String, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Memory(Base):
    __tablename__ = "memories"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    memory_type: Mapped[str] = mapped_column(String)  # episodic, conversational
    content: Mapped[str] = mapped_column(String)
    importance_score: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    embedding: Mapped[list[float]] = mapped_column(JSON, nullable=True)

    conversation_links: Mapped[list["ConversationMemory"]] = relationship(
        "ConversationMemory", back_populates="memory", cascade="all, delete-orphan"
    )


class ConversationMemory(Base):
    __tablename__ = "conversation_memories"

    conversation_id: Mapped[str] = mapped_column(
        String, ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True
    )
    memory_id: Mapped[str] = mapped_column(
        String, ForeignKey("memories.id", ondelete="CASCADE"), primary_key=True
    )

    memory: Mapped["Memory"] = relationship(
        "Memory", back_populates="conversation_links"
    )
    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="memory_links"
    )
