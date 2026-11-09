import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Uuid
from sqlalchemy.orm import relationship

from database import Base


class PasswordResetTokenPurpose(str, enum.Enum):
    RESET = "reset"


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    token_id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    token_hash = Column(String(255), nullable=False, unique=True)
    user_id = Column(
        Uuid, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    purpose = Column(
        Enum(PasswordResetTokenPurpose, name="password_reset_token_purpose"),
        nullable=False,
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    user = relationship("User", back_populates="password_reset_tokens")
