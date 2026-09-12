"""Fulfillment state machine.

Same pure-logic pattern as payment_state.py / reservation_state.py. A
fulfillment moves through a single linear chain from order confirmation to
physical delivery:

    PENDING -> PICKING -> PACKED -> READY_FOR_DELIVERY -> ASSIGNED
             -> OUT_FOR_DELIVERY -> DELIVERED

DELIVERED is terminal and is the ONLY status that triggers physical
inventory consumption (see FulfillmentService.confirm_delivery). ASSIGNED
(Phase 16) additionally requires a delivery_partner_user_id to be set in
the same transaction - see FulfillmentService.assign_delivery_partner;
this module only enforces the status ordering, not that side effect.

There is no branch, no skip-ahead, and no reverse transition in this
phase - substitutions, partial fulfillment, and delivery failure/return
flows are explicitly out of scope.
"""

from dataclasses import dataclass
from enum import StrEnum


class FulfillmentStatus(StrEnum):
    PENDING = "PENDING"
    PICKING = "PICKING"
    PACKED = "PACKED"
    READY_FOR_DELIVERY = "READY_FOR_DELIVERY"
    ASSIGNED = "ASSIGNED"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"


_FULFILLMENT_ORDER: list[FulfillmentStatus] = [
    FulfillmentStatus.PENDING,
    FulfillmentStatus.PICKING,
    FulfillmentStatus.PACKED,
    FulfillmentStatus.READY_FOR_DELIVERY,
    FulfillmentStatus.ASSIGNED,
    FulfillmentStatus.OUT_FOR_DELIVERY,
    FulfillmentStatus.DELIVERED,
]

_NEXT_STATUS: dict[FulfillmentStatus, FulfillmentStatus] = {
    current: _FULFILLMENT_ORDER[i + 1]
    for i, current in enumerate(_FULFILLMENT_ORDER[:-1])
}


class IllegalFulfillmentTransitionError(Exception):
    """Raised when a requested fulfillment status transition is not legal."""

    def __init__(self, current: "FulfillmentStatus", target: "FulfillmentStatus") -> None:
        self.current = current
        self.target = target
        super().__init__(
            f"Illegal fulfillment status transition: {current.value} -> {target.value}"
        )


@dataclass(frozen=True)
class FulfillmentTransitionResult:
    applied: bool
    previous: FulfillmentStatus
    current: FulfillmentStatus


def transition_fulfillment_status(
    current: FulfillmentStatus, target: FulfillmentStatus
) -> FulfillmentTransitionResult:
    """Same-state is an idempotent no-op. Only the single next step in the
    fixed chain is legal - no skipping ahead, no going back.
    """
    if current == target:
        return FulfillmentTransitionResult(
            applied=False, previous=current, current=current
        )

    if _NEXT_STATUS.get(current) != target:
        raise IllegalFulfillmentTransitionError(current, target)

    return FulfillmentTransitionResult(applied=True, previous=current, current=target)


def is_fulfillment_terminal(status: FulfillmentStatus) -> bool:
    return status == FulfillmentStatus.DELIVERED
