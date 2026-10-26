from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import decode_access_token
from app.models import User

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(request: Request, db: DbSession) -> User:
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "No autenticado")
    token = request.cookies.get(get_settings().cookie_name)
    if not token:
        raise unauthorized
    user_id = decode_access_token(token)
    if user_id is None:
        raise unauthorized
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_owned[M](db: Session, model: type[M], obj_id: int, user: User, label: str) -> M:
    """Loads a row of the current user; 404 for missing rows and rows of other users alike."""
    obj = db.get(model, obj_id)
    if obj is None or obj.user_id != user.id:  # type: ignore[attr-defined]
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{label} no encontrado(a)")
    return obj
