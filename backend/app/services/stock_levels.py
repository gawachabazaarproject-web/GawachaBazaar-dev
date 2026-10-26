"""One rule for "is this item running low?", used everywhere stock is judged
(dashboard, inventory list, alerts).

Every variant has a *reserve level*: the stock the shop wants to keep on the
shelf. When no reserve is set the DEFAULT_RESERVE applies. Compared with the
quantity available (on hand minus reserved for orders):

  OUT    - nothing available
  BELOW  - at or below the reserve
  NEAR   - above the reserve but within NEAR_FACTOR of it (running close)
  OK     - comfortably above
"""

from decimal import Decimal

DEFAULT_RESERVE = Decimal("10")
# "Close to reserve" = within 25% above it.
NEAR_FACTOR = Decimal("1.25")

OUT = "OUT"
BELOW = "BELOW"
NEAR = "NEAR"
OK = "OK"

# Levels an admin should be told about, most urgent first.
ALERT_LEVELS = (OUT, BELOW, NEAR)


def effective_reserve(reserve_level: Decimal | None) -> Decimal:
    return DEFAULT_RESERVE if reserve_level is None else reserve_level


def stock_level(available: Decimal, reserve_level: Decimal | None) -> str:
    reserve = effective_reserve(reserve_level)
    if available <= 0:
        return OUT
    if available <= reserve:
        return BELOW
    if available <= reserve * NEAR_FACTOR:
        return NEAR
    return OK


def product_status(levels: list[str]) -> str:
    """One status for a whole product from the levels of its sellable sizes
    ("OUT" / "LOW" / "OK") - the single rule behind the Inventory chips, the
    Products list and the header alert, so they always agree.

      OUT - no size can be sold (every size is OUT), or there is no size at all
      LOW - some size is out, at/below its reserve, or close to it
      OK  - every size is comfortably stocked
    """
    if not levels or all(level == OUT for level in levels):
        return "OUT"
    if any(level in ALERT_LEVELS for level in levels):
        return "LOW"
    return "OK"
