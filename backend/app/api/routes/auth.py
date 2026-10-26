from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.core.security import DUMMY_HASH, create_access_token, verify_password
from app.models import User
from app.schemas.auth import LoginRequest, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=UserOut)
def login(body: LoginRequest, response: Response, db: DbSession) -> User:
    user = db.scalar(select(User).where(func.lower(User.email) == body.email.lower()))
    # Always run a hash check so response time does not reveal whether the email exists.
    valid = verify_password(body.password, user.hashed_password if user else DUMMY_HASH)
    if user is None or not valid or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Correo o contraseña incorrectos")

    settings = get_settings()
    response.set_cookie(
        settings.cookie_name,
        create_access_token(user.id),
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        path="/",
    )
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    response.delete_cookie(get_settings().cookie_name, path="/")


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> User:
    return user
