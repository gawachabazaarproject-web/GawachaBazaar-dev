"""Bulk order request state machine.

Same pure-logic pattern as payment_state.py / reservation_state.py /
fulfillment_state.py: no DB/HTTP dependencies, single source of truth for
what a request may legally become next.

MAIN PROGRESSION (linear):
    REQUESTED -> UNDER_REVIEW -> QUOTED -> CUSTOMER_ACCEPTED -> CONVERTED_TO_ORDER

TERMINAL ALTERNATIVES (reachable from any non-terminal state):
    REJECTED, CANCELLED, EXPIRED

A quote revision (a new QuoteVersion) does NOT move the request out of
QUOTED - QUOTED covers "at least one quote version has been sent, and the
customer hasn't accepted yet," regardless of how many times admin
re-quotes. Only CUSTOMER_ACCEPTED (the customer's own action) advances
past QUOTED.
"""

from dataclasses import dataclass
from enum import StrEnum


class BulkOrderRequestStatus(StrEnum):
    REQUESTED = "REQUESTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    QUOTED = "QUOTED"
    CUSTOMER_ACCEPTED = "CUSTOMER_ACCEPTED"
    CONVERTED_TO_ORDER = "CONVERTED_TO_ORDER"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


TERMINAL_REQUEST_STATUSES = frozenset(
    {
        BulkOrderRequestStatus.CONVERTED_TO_ORDER,
        BulkOrderRequestStatus.REJECTED,
        BulkOrderRequestStatus.CANCELLED,
        BulkOrderRequestStatus.EXPIRED,
    }
)

# Every non-terminal status may move to any of these terminal alternatives.
_TERMINAL_ALTERNATIVES = frozenset(
    {
        BulkOrderRequestStatus.REJECTED,
        BulkOrderRequestStatus.CANCELLED,
        BulkOrderRequestStatus.EXPIRED,
    }
)

_MAIN_PROGRESSION: dict[BulkOrderRequestStatus, BulkOrderRequestStatus] = {
    BulkOrderRequestStatus.REQUESTED: BulkOrderRequestStatus.UNDER_REVIEW,
    BulkOrderRequestStatus.UNDER_REVIEW: BulkOrderRequestStatus.QUOTED,
    BulkOrderRequestStatus.QUOTED: BulkOrderRequestStatus.CUSTOMER_ACCEPTED,
    BulkOrderRequestStatus.CUSTOMER_ACCEPTED: BulkOrderRequestStatus.CONVERTED_TO_ORDER,
}


class IllegalBulkOrderRequestTransitionError(Exception):
    """Raised when a requested bulk order request status transition is
    not legal."""

    def __init__(
        self, current: "BulkOrderRequestStatus", target: "BulkOrderRequestStatus"
    ) -> None:
        self.current = current
        self.target = target
        super().__init__(
            f"Illegal bulk order request status transition: {current.value} -> {target.value}"
        )


@dataclass(frozen=True)
class BulkOrderRequestTransitionResult:
    applied: bool
    previous: BulkOrderRequestStatus
    current: BulkOrderRequestStatus


def transition_bulk_order_request_status(
    current: BulkOrderRequestStatus, target: BulkOrderRequestStatus
) -> BulkOrderRequestTransitionResult:
    """Same-state is an idempotent no-op. Legal moves are: the single
    next step in the main progression, or any terminal alternative from a
    non-terminal state. A terminal status never transitions anywhere.
    """
    if current == target:
        return BulkOrderRequestTransitionResult(
            applied=False, previous=current, current=current
        )

    if current in TERMINAL_REQUEST_STATUSES:
        raise IllegalBulkOrderRequestTransitionError(current, target)

    if target in _TERMINAL_ALTERNATIVES or _MAIN_PROGRESSION.get(current) == target:
        return BulkOrderRequestTransitionResult(
            applied=True, previous=current, current=target
        )

    raise IllegalBulkOrderRequestTransitionError(current, target)


def is_request_terminal(status: BulkOrderRequestStatus) -> bool:
    return status in TERMINAL_REQUEST_STATUSES
