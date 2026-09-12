"""Refund approval-workflow state machine.

Same pure-logic pattern as payment_state.py / order_state.py. This governs
the `refunds` table's own approval lifecycle - a DIFFERENT concern from
`payment_transactions.status` (which tracks one gateway-call attempt, PAYMENT
or REFUND, and already has its own INITIATED/PROCESSING/SUCCESS/FAILED
vocabulary reused as-is for refund attempts - see
app/services/payment_state.py's TransactionStatus).

REFUND LIFECYCLE
=================
    PENDING_APPROVAL -> APPROVED   (admin approves)
    PENDING_APPROVAL -> REJECTED   (admin rejects; terminal)
    APPROVED         -> PROCESSING (admin triggers gateway processing)
    PROCESSING       -> REFUNDED   (gateway attempt succeeded; terminal)
    PROCESSING       -> FAILED     (gateway attempt failed/unavailable)
    FAILED           -> PROCESSING (admin retries processing - mirrors
                                     PaymentStatus's FAILED -> PROCESSING
                                     retry; does NOT skip back through
                                     approval)

REFUNDED and REJECTED are terminal. A customer can never move a refund out
of PENDING_APPROVAL - only ADMIN actions call `transition_refund_status`.
"""

from dataclasses import dataclass
from enum import StrEnum


class RefundStatus(StrEnum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PROCESSING = "PROCESSING"
    REFUNDED = "REFUNDED"
    FAILED = "FAILED"


_REFUND_TRANSITIONS: dict[RefundStatus, frozenset[RefundStatus]] = {
    RefundStatus.PENDING_APPROVAL: frozenset(
        {RefundStatus.APPROVED, RefundStatus.REJECTED}
    ),
    RefundStatus.APPROVED: frozenset({RefundStatus.PROCESSING}),
    RefundStatus.PROCESSING: frozenset({RefundStatus.REFUNDED, RefundStatus.FAILED}),
    RefundStatus.FAILED: frozenset({RefundStatus.PROCESSING}),
    RefundStatus.REFUNDED: frozenset(),
    RefundStatus.REJECTED: frozenset(),
}

TERMINAL_REFUND_STATUSES = frozenset({RefundStatus.REFUNDED, RefundStatus.REJECTED})


class IllegalRefundTransitionError(Exception):
    """Raised when a requested refund status transition is not legal."""

    def __init__(self, current: "RefundStatus", target: "RefundStatus") -> None:
        self.current = current
        self.target = target
        super().__init__(
            f"Illegal refund status transition: {current.value} -> {target.value}"
        )


@dataclass(frozen=True)
class RefundTransitionResult:
    applied: bool
    previous: RefundStatus
    current: RefundStatus


def transition_refund_status(
    current: RefundStatus, target: RefundStatus
) -> RefundTransitionResult:
    if current == target:
        return RefundTransitionResult(applied=False, previous=current, current=current)

    allowed = _REFUND_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise IllegalRefundTransitionError(current, target)

    return RefundTransitionResult(applied=True, previous=current, current=target)


def is_refund_terminal(status: RefundStatus) -> bool:
    return status in TERMINAL_REFUND_STATUSES
