from collections import defaultdict
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession, get_owned
from app.models import Account, Transfer, TransferRoute, User
from app.schemas.transfers import (
    CostOut,
    P2PSummary,
    PairSummary,
    RouteIn,
    RouteOut,
    TransferIn,
    TransferOut,
)
from app.services.fx import RateResolver, money
from app.services.p2p import TransferCost, transfer_cost

router = APIRouter(tags=["p2p"])

PCT = Decimal("0.01")


def _pct(cost: Decimal | None, base: Decimal | None) -> Decimal | None:
    if cost is None or not base:
        return None
    return (cost / base * 100).quantize(PCT)


def _cost_out(c: TransferCost) -> CostOut:
    return CostOut(
        value_out=money(c.value_out),
        value_in=money(c.value_in),
        cost=money(c.cost),
        fee=money(c.fee),
        spread=money(c.spread),
        cost_pct=_pct(c.cost, c.value_out),
    )


def _transfer_out(t: Transfer, rates: RateResolver) -> TransferOut:
    return TransferOut(
        id=t.id,
        route_id=t.route_id,
        step=t.step,
        from_account_id=t.from_account_id,
        to_account_id=t.to_account_id,
        from_currency=t.from_account.currency,
        to_currency=t.to_account.currency,
        amount_out=t.amount_out,
        amount_in=t.amount_in,
        fee_amount=t.fee_amount,
        ref_rate_out=t.ref_rate_out,
        ref_rate_in=t.ref_rate_in,
        occurred_on=t.occurred_on,
        notes=t.notes,
        cost=_cost_out(transfer_cost(t, rates)),
    )


def _route_out(route: TransferRoute, rates: RateResolver) -> RouteOut:
    steps = [_transfer_out(t, rates) for t in route.steps]
    costs = [transfer_cost(t, rates) for t in route.steps]
    total = (
        sum((c.cost for c in costs), Decimal(0)) if all(c.cost is not None for c in costs) else None
    )
    fees = (
        sum((c.fee for c in costs), Decimal(0)) if all(c.fee is not None for c in costs) else None
    )
    first_out = costs[0].value_out if costs else None
    return RouteOut(
        id=route.id,
        name=route.name,
        started_on=route.started_on,
        notes=route.notes,
        steps=steps,
        cost=CostOut(
            value_out=money(first_out),
            value_in=money(costs[-1].value_in) if costs else None,
            cost=money(total),
            fee=money(fees),
            spread=money(total - fees) if total is not None and fees is not None else None,
            cost_pct=_pct(total, first_out),
        ),
    )


def _check_accounts(db: DbSession, user: User, body: TransferIn) -> None:
    get_owned(db, Account, body.from_account_id, user, "Plataforma de origen")
    get_owned(db, Account, body.to_account_id, user, "Plataforma de destino")


# --- Single transfers -------------------------------------------------------------------------


@router.get("/transfers", response_model=list[TransferOut])
def list_transfers(
    db: DbSession,
    user: CurrentUser,
    start: date | None = None,
    end: date | None = None,
    account_id: int | None = None,
    limit: int = 500,
):
    q = select(Transfer).where(Transfer.user_id == user.id)
    if start:
        q = q.where(Transfer.occurred_on >= start)
    if end:
        q = q.where(Transfer.occurred_on <= end)
    if account_id:
        q = q.where(
            (Transfer.from_account_id == account_id) | (Transfer.to_account_id == account_id)
        )
    q = q.order_by(Transfer.occurred_on.desc(), Transfer.id.desc()).limit(min(limit, 2000))
    rates = RateResolver(db, user)
    return [_transfer_out(t, rates) for t in db.scalars(q).unique()]


@router.post("/transfers", response_model=TransferOut, status_code=status.HTTP_201_CREATED)
def create_transfer(body: TransferIn, db: DbSession, user: CurrentUser):
    _check_accounts(db, user, body)
    t = Transfer(user_id=user.id, **body.model_dump())
    db.add(t)
    db.commit()
    db.refresh(t)
    return _transfer_out(t, RateResolver(db, user))


@router.put("/transfers/{transfer_id}", response_model=TransferOut)
def replace_transfer(transfer_id: int, body: TransferIn, db: DbSession, user: CurrentUser):
    t = get_owned(db, Transfer, transfer_id, user, "Transferencia")
    _check_accounts(db, user, body)
    for field, value in body.model_dump().items():
        setattr(t, field, value)
    db.commit()
    db.refresh(t)
    return _transfer_out(t, RateResolver(db, user))


@router.delete("/transfers/{transfer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transfer(transfer_id: int, db: DbSession, user: CurrentUser):
    db.delete(get_owned(db, Transfer, transfer_id, user, "Transferencia"))
    db.commit()


# --- Routes (P2P chains) ----------------------------------------------------------------------


def _add_steps(db: DbSession, user: User, route: TransferRoute, body: RouteIn) -> None:
    for i, step in enumerate(body.steps, start=1):
        _check_accounts(db, user, step)
        data = step.model_dump()
        data["occurred_on"] = step.occurred_on or body.started_on
        db.add(Transfer(user_id=user.id, route_id=route.id, step=i, **data))


def _load_route(db: DbSession, route_id: int) -> TransferRoute:
    return db.scalar(
        select(TransferRoute)
        .where(TransferRoute.id == route_id)
        .options(selectinload(TransferRoute.steps))
        .execution_options(populate_existing=True)
    )


@router.get("/transfer-routes", response_model=list[RouteOut])
def list_routes(
    db: DbSession,
    user: CurrentUser,
    start: date | None = None,
    end: date | None = None,
    limit: int = 200,
):
    q = (
        select(TransferRoute)
        .where(TransferRoute.user_id == user.id)
        .options(selectinload(TransferRoute.steps))
    )
    if start:
        q = q.where(TransferRoute.started_on >= start)
    if end:
        q = q.where(TransferRoute.started_on <= end)
    q = q.order_by(TransferRoute.started_on.desc(), TransferRoute.id.desc()).limit(min(limit, 1000))
    rates = RateResolver(db, user)
    return [_route_out(r, rates) for r in db.scalars(q)]


@router.post("/transfer-routes", response_model=RouteOut, status_code=status.HTTP_201_CREATED)
def create_route(body: RouteIn, db: DbSession, user: CurrentUser):
    route = TransferRoute(
        user_id=user.id, name=body.name, started_on=body.started_on, notes=body.notes
    )
    db.add(route)
    db.flush()
    _add_steps(db, user, route, body)
    db.commit()
    return _route_out(_load_route(db, route.id), RateResolver(db, user))


@router.put("/transfer-routes/{route_id}", response_model=RouteOut)
def replace_route(route_id: int, body: RouteIn, db: DbSession, user: CurrentUser):
    route = get_owned(db, TransferRoute, route_id, user, "Ruta")
    for step in list(route.steps):
        db.delete(step)
    db.flush()
    route.name, route.started_on, route.notes = body.name, body.started_on, body.notes
    _add_steps(db, user, route, body)
    db.commit()
    return _route_out(_load_route(db, route.id), RateResolver(db, user))


@router.delete("/transfer-routes/{route_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_route(route_id: int, db: DbSession, user: CurrentUser):
    """Deletes the route and all its steps (they are real money movements)."""
    route = get_owned(db, TransferRoute, route_id, user, "Ruta")
    for step in list(route.steps):
        db.delete(step)
    db.delete(route)
    db.commit()


# --- Summary ----------------------------------------------------------------------------------


@router.get("/p2p/summary", response_model=P2PSummary)
def p2p_summary(
    db: DbSession, user: CurrentUser, start: date | None = None, end: date | None = None
):
    if start and end and start > end:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Rango de fechas inválido")
    q = select(Transfer).where(Transfer.user_id == user.id)
    if start:
        q = q.where(Transfer.occurred_on >= start)
    if end:
        q = q.where(Transfer.occurred_on <= end)

    rates = RateResolver(db, user)
    volume = cost = fees = Decimal(0)
    count = missing = 0
    pairs: dict[tuple[int, int], list[Decimal]] = defaultdict(lambda: [Decimal(0), Decimal(0), 0])
    for t in db.scalars(q).unique():
        c = transfer_cost(t, rates)
        if c.cost is None or c.fee is None or c.value_out is None:
            missing += 1
            continue
        count += 1
        # Only money entering a chain counts as volume; later steps move the same money again.
        if t.route_id is None or t.step == 1:
            volume += c.value_out
        cost += c.cost
        fees += c.fee
        pair = pairs[(t.from_account_id, t.to_account_id)]
        pair[0] += c.value_out
        pair[1] += c.cost
        pair[2] += 1

    by_pair = sorted(
        (
            PairSummary(
                from_account_id=f,
                to_account_id=to,
                count=n,
                volume=money(v),
                cost=money(cs),
                cost_pct=_pct(cs, v),
            )
            for (f, to), (v, cs, n) in pairs.items()
        ),
        key=lambda p: p.cost,
        reverse=True,
    )
    return P2PSummary(
        base_currency=user.base_currency,
        count=count,
        volume=money(volume),
        cost=money(cost),
        fees=money(fees),
        spread=money(cost - fees),
        cost_pct=_pct(cost, volume),
        missing_rates=missing,
        by_pair=by_pair,
    )
