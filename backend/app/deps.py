from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from .database import get_db
from .models import User, UserRole
from .security import get_user_from_token


def get_current_active_user(current_user: User = Depends(get_user_from_token)) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user


def get_current_active_admin(
    current_user: User = Depends(get_current_active_user),
) -> User:
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def get_current_active_professional(
    current_user: User = Depends(get_current_active_user),
) -> User:
    if current_user.role != UserRole.professional:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Professional access required")
    return current_user


def get_current_active_client(
    current_user: User = Depends(get_current_active_user),
) -> User:
    if current_user.role != UserRole.client:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Client access required")
    return current_user


def get_db_session() -> Session:
    return Depends(get_db)
