"""Order state machine.

Same pure-logic pattern as payment_state.py / reservation_state.py /
fulfillment_state.py. No prior phase needed this: every existing
order-status write (`_confirm_cod`/`_confirm_order_if_paid` -> CONFIRMED,
`_mark_order_expired_if_pending` -> EXPIRED, `confirm_delivery` ->
COMPLETED) is already guarded by its own narrow precondition check
(`order.status == "PENDING"`, `order.status != "CONFIRMED"`, etc.) and is
therefore left untouched here rather than retrofitted - this module exists
to make the ONE new decision Phase 18 introduces explicit and testable:
whether a given current status may legally become CANCELLED.

ORDER LIFECYCLE
================
    PENDING   -> CONFIRMED   (payment success / COD accepted)
    PENDING   -> EXPIRED     (reservation window lapsed before confirmation)
    PENDING   -> CANCELLED   (Phase 18: customer/admin cancels before payment)
    CONFIRMED -> COMPLETED   (delivery confirmed)
    CONFIRMED -> CANCELLED   (Phase 18: customer/admin cancels any time
                              before delivery is completed, regardless of
                              which Fulfillment sub-status - PICKING,
                              PACKED, READY_FOR_DELIVERY, ASSIGNED,
                              OUT_FOR_DELIVERY - it is currently in; the
                              Order itself stays CONFIRMED throughout all
                              of those, so this one transition covers all
                              of them)

COMPLETED, EXPIRED, and CANCELLED are all terminal - once an order leaves
PENDING/CONFIRMED it never returns, and in particular a CANCELLED order can
never resume normal fulfillment and a COMPLETED (delivered) order can never
become CANCELLED.
"""

from dataclasses import dataclass
from enum import StrEnum


class OrderStatus(StrEnum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"


_ORDER_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.PENDING: frozenset(
        {OrderStatus.CONFIRMED, OrderStatus.EXPIRED, OrderStatus.CANCELLED}
    ),
    OrderStatus.CONFIRMED: frozenset({OrderStatus.COMPLETED, OrderStatus.CANCELLED}),
    OrderStatus.COMPLETED: frozenset(),
    OrderStatus.EXPIRED: frozenset(),
    OrderStatus.CANCELLED: frozenset(),
}

TERMINAL_ORDER_STATUSES = frozenset(
    {OrderStatus.COMPLETED, OrderStatus.EXPIRED, OrderStatus.CANCELLED}
)


class IllegalOrderTransitionError(Exception):
    """Raised when a requested order status transition is not legal."""

    def __init__(self, current: "OrderStatus", target: "OrderStatus") -> None:
        self.current = current
        self.target = target
        super().__init__(
            f"Illegal order status transition: {current.value} -> {target.value}"
        )


@dataclass(frozen=True)
class OrderTransitionResult:
    applied: bool
    previous: OrderStatus
    current: OrderStatus


def transition_order_status(
    current: OrderStatus, target: OrderStatus
) -> OrderTransitionResult:
    """Same-state is an idempotent no-op (a repeated cancel request is
    harmless). Any other transition not explicitly listed above raises.
    """
    if current == target:
        return OrderTransitionResult(applied=False, previous=current, current=current)

    allowed = _ORDER_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise IllegalOrderTransitionError(current, target)

    return OrderTransitionResult(applied=True, previous=current, current=target)


def is_order_terminal(status: OrderStatus) -> bool:
    return status in TERMINAL_ORDER_STATUSES
