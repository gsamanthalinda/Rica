import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import relationship

from database import Base


class OneTimeCodePurpose(str, enum.Enum):
    ACTIVATION = "activation"
    LOGIN_MFA = "login_mfa"
    RESET = "reset"


class OneTimeCode(Base):
    __tablename__ = "one_time_codes"

    code_id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = Column(
        Uuid, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    purpose = Column(
        Enum(OneTimeCodePurpose, name="one_time_code_purpose"), nullable=False
    )
    code_hash = Column(String(255), nullable=False)
    attempts = Column(Integer, nullable=False, default=0, server_default="0")
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user = relationship("User", back_populates="one_time_codes")
