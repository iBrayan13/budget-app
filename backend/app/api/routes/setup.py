from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.services.defaults import seed_categories, seed_defaults

router = APIRouter(prefix="/setup", tags=["setup"])


@router.post("/defaults")
def load_defaults(db: DbSession, user: CurrentUser) -> dict[str, int]:
    """Creates the suggested platforms and categories that do not exist yet."""
    return seed_defaults(db, user)


@router.post("/categories")
def load_categories(db: DbSession, user: CurrentUser) -> dict[str, int]:
    """Only the suggested categories, for when platforms were already created by hand."""
    return {"categories": seed_categories(db, user)}
