import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Uuid
from sqlalchemy.orm import relationship

from database import Base


class MFATokenPurpose(str, enum.Enum):
    SETUP = "setup"
    VERIFY = "verify"


class MFAToken(Base):
    __tablename__ = "mfa_tokens"

    token_id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    token = Column(String, nullable=False, unique=True)
    user_id = Column(
        Uuid, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    secret_encrypted = Column(String(512), nullable=False)
    purpose = Column(Enum(MFATokenPurpose, name="mfa_token_purpose"), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    user = relationship("User", back_populates="mfa_tokens")
