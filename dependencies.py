from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.user import User


def get_current_user(db: Session = Depends(get_db)):

    user = db.query(User).first()
    if user is None:
        raise HTTPException(
            status_code=500, detail="No users in database. Insert one first."
        )
    return user
