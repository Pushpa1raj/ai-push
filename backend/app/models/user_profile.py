import uuid
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

class UserProfile(Base):
    __tablename__ = "user_profile"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    college: Mapped[str | None] = mapped_column(String, nullable=True)
    branch: Mapped[str | None] = mapped_column(String, nullable=True)
    year: Mapped[str | None] = mapped_column(String, nullable=True)
    sgpa: Mapped[str | None] = mapped_column(String, nullable=True)
    preferred_language: Mapped[str | None] = mapped_column(String, nullable=True)
    current_project: Mapped[str | None] = mapped_column(String, nullable=True)
