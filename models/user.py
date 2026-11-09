import enum
import uuid

from sqlalchemy import Boolean, Column, DateTime, Enum, String, Uuid, func
from sqlalchemy.orm import relationship

from database import Base


class UserRole(str, enum.Enum):
    SYSTEM_ADMINISTRATOR = "SYSTEM_ADMINISTRATOR"
    SUPPLY_CHAIN_MANAGER = "SUPPLY_CHAIN_MANAGER"
    OPERATIONS_MANAGER = "OPERATIONS_MANAGER"


class AccountStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    PENDING = "PENDING"
    DISABLED = "DISABLED"


class User(Base):
    __tablename__ = "users"

    user_id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=True)
    password_changed_at = Column(DateTime(timezone=True), nullable=True)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    mfa_enabled = Column(Boolean, nullable=False, default=False, server_default="false")
    mfa_secret_encrypted = Column(String(512), nullable=True)
    email_mfa_enabled = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    company_name = Column(String(255), nullable=True)
    role = Column(
        Enum(UserRole, name="user_role", validate_strings=True), nullable=False
    )
    account_status = Column(
        Enum(AccountStatus, name="account_status"),
        nullable=False,
        default=AccountStatus.ACTIVE,
        server_default=AccountStatus.ACTIVE.value,
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    batches = relationship("MineralBatch", back_populates="creator")
    history_events = relationship("BatchHistory", back_populates="recorder")
    value_calculations = relationship("ValueCalculation", back_populates="calculator")
    scenarios = relationship("Scenario", back_populates="creator")
    mfa_tokens = relationship("MFAToken", back_populates="user")
    password_reset_tokens = relationship("PasswordResetToken", back_populates="user")
    one_time_codes = relationship("OneTimeCode", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")
