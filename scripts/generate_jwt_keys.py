"""Create the initial SYSTEM_ADMINISTRATOR account directly (bypasses auth).

Usage:
    python scripts/create_admin.py [email] [password]

Defaults: admin@example.com / AdminPassword123!
"""

import os
import sys


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session

from database import SessionLocal, engine
from models import Base, User, UserRole
from services.user_service import hash_password


def main(email: str = "admin@example.com", password: str = "AdminPassword123!") -> None:
    Base.metadata.create_all(engine)
    db: Session = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            print(
                f"Admin already exists: {existing.email} (role={existing.role.value})"
            )
            return
        user = User(
            email=email,
            password_hash=hash_password(password),
            first_name="System",
            last_name="Administrator",
            role=UserRole.SYSTEM_ADMINISTRATOR,
            mfa_enabled=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(
            f"Created admin: {user.email} (user_id={user.user_id}, role=SYSTEM_ADMINISTRATOR)"
        )
    finally:
        db.close()


if __name__ == "__main__":
    email = sys.argv[1] if len(sys.argv) > 1 else "admin@example.com"
    password = sys.argv[2] if len(sys.argv) > 2 else "AdminPassword123!"
    main(email, password)
