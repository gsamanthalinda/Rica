from fastapi import Depends, HTTPException, status

from core.auth import get_current_user
from models import User, UserRole


def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role != UserRole.SYSTEM_ADMINISTRATOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


def require_supply_chain_manager(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role not in (
        UserRole.SYSTEM_ADMINISTRATOR,
        UserRole.SUPPLY_CHAIN_MANAGER,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Supply chain manager access required",
        )
    return current_user


def require_operations_manager(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role not in (
        UserRole.SYSTEM_ADMINISTRATOR,
        UserRole.SUPPLY_CHAIN_MANAGER,
        UserRole.OPERATIONS_MANAGER,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operations manager access required",
        )
    return current_user
