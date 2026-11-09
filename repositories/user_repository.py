import uuid

from sqlalchemy.orm import Session

from models import AccountStatus, User, UserRole


def create(
    db: Session,
    email: str,
    password_hash: str | None,
    first_name: str,
    last_name: str,
    role: UserRole,
    account_status: AccountStatus = AccountStatus.ACTIVE,
    company_name: str | None = None,
) -> User:
    user = User(
        email=email,
        password_hash=password_hash,
        first_name=first_name,
        last_name=last_name,
        role=role,
        account_status=account_status,
        company_name=company_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_by_id(db: Session, user_id: str) -> User | None:
    try:
        uid = uuid.UUID(str(user_id))
    except (ValueError, TypeError):
        return None
    return db.query(User).filter(User.user_id == uid).first()


def get_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def list(db: Session) -> list[User]:
    return db.query(User).order_by(User.created_at.desc()).all()


def update(
    db: Session,
    user_id: str,
    email: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    role: UserRole | None = None,
    company_name: str | None = None,
) -> User | None:
    user = get_by_id(db, user_id)
    if user is None:
        return None
    if email is not None:
        user.email = email
    if first_name is not None:
        user.first_name = first_name
    if last_name is not None:
        user.last_name = last_name
    if role is not None:
        user.role = role
    if company_name is not None:
        user.company_name = company_name
    db.commit()
    db.refresh(user)
    return user


def set_status(db: Session, user_id: str, status: str) -> User | None:
    user = get_by_id(db, user_id)
    if user is None:
        return None
    user.account_status = status
    db.commit()
    db.refresh(user)
    return user
