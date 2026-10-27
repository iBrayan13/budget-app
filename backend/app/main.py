from fastapi import APIRouter, FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.api.routes import (
    accounts,
    auth,
    categories,
    debts,
    goals,
    health,
    loans,
    plan,
    rates,
    recurring,
    setup,
    transactions,
    transfers,
)
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="Presupuesto Personal",
    docs_url=None if settings.is_production else "/api/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/api/openapi.json",
)


@app.exception_handler(IntegrityError)
def integrity_error(_: Request, __: IntegrityError) -> JSONResponse:
    # Safety net for races; endpoints validate explicitly before writing.
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": "El registro ya existe o está siendo usado por otros datos"},
    )


api = APIRouter(prefix="/api")
for module in (
    health,
    auth,
    setup,
    accounts,
    categories,
    rates,
    transactions,
    transfers,
    recurring,
    debts,
    goals,
    loans,
    plan,
):
    api.include_router(module.router)
app.include_router(api)
