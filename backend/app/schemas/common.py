from decimal import Decimal
from typing import Annotated

from pydantic import AfterValidator, Field, PlainSerializer, StringConstraints

# Output decimals as plain strings ("0.00000000", never "0E-8").
Dec = Annotated[Decimal, PlainSerializer(lambda v: format(v, "f"), return_type=str)]

Currency = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Za-z0-9]{2,10}$"),
]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
LongName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]

# Fits NUMERIC(20, 8)
_MAX = Decimal("999999999999")
Amount = Annotated[Decimal, Field(max_digits=20, decimal_places=8, ge=-_MAX, le=_MAX)]
PositiveAmount = Annotated[Decimal, Field(gt=0, max_digits=20, decimal_places=8, le=_MAX)]
Rate = PositiveAmount


def _non_zero(v: Decimal) -> Decimal:
    if v == 0:
        raise ValueError("no puede ser cero")
    return v


NonZeroAmount = Annotated[Amount, AfterValidator(_non_zero)]
