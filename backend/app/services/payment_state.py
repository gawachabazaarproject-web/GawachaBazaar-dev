"""Payment and payment-transaction state machines.

Centralizes every legal state transition so no code path can do
`payment.status = incoming_gateway_status` directly. This module has no
DB/HTTP/gateway dependencies - it is pure transition logic, unit-testable
in isolation, and is the single source of truth both the webhook handler
and the client-facing /verify endpoint apply the same authoritative
status through (see app/services/payment.py).

PAYMENT TRANSITION MATRIX
==========================
The spec (Phase 14) explicitly gives:
    PENDING -> PROCESSING
    PROCESSING -> PAID
    PROCESSING -> FAILED
    PROCESSING -> EXPIRED
    FAILED -> PROCESSING          (retry)
    EXPIRED -> PROCESSING         (retry)
    PAID is terminal (no outgoing transitions, ever)

This module documents two deliberate, narrow extensions beyond that
explicit list - not contradictions of it:
    PENDING -> PAID / FAILED / EXPIRED / CANCELLED   (direct)
        A gateway can confirm/reject synchronously, faster than our own
        PENDING->PROCESSING bookkeeping. Rejecting a legitimate fast
        confirmation just because we didn't record an intermediate
        PROCESSING step first would be strictly worse than allowing it.
    PROCESSING -> CANCELLED
        Represents a customer explicitly cancelling mid-flow (e.g. closing
        the UPI app) - a real, distinct terminal outcome from FAILED.

CANCELLED is treated as terminal in this phase (no FAILED/EXPIRED ->
CANCELLED retry-in-place is defined) - a cancelled attempt is superseded
by a brand-new payment attempt via /retry, not an in-place transition.

Idempotent re-application (event says PAID, payment is already PAID) is a
NO-OP, not an error and not a re-application. An illegal transition
(e.g. PAID -> FAILED, a late failure arriving after success) raises
IllegalTransitionError - callers must catch this and treat it as a
reconciliation signal (log + leave state untouched), never let it
propagate as if the mutation happened.
"""

from dataclasses import dataclass
from enum import StrEnum


class PaymentStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PAID = "PAID"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class TransactionStatus(StrEnum):
    INITIATED = "INITIATED"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


TRANSACTION_TERMINAL_STATUSES = frozenset(
    {
        TransactionStatus.SUCCESS,
        TransactionStatus.FAILED,
        TransactionStatus.CANCELLED,
        TransactionStatus.EXPIRED,
    }
)


class IllegalTransitionError(Exception):
    """Raised when a requested payment status transition is not legal.

    Callers must not let this abort a webhook/verify request with a 5xx -
    it represents a legitimate-but-late or out-of-order event that must be
    safely ignored (with a reconciliation log entry), not a system failure.
    """

    def __init__(self, current: "PaymentStatus", target: "PaymentStatus") -> None:
        self.current = current
        self.target = target
        super().__init__(
            f"Illegal payment status transition: {current.value} -> {target.value}"
        )


@dataclass(frozen=True)
class TransitionResult:
    """Result of attempting a payment status transition."""

    applied: bool  # True if the status actually changed
    previous: PaymentStatus
    current: PaymentStatus


_PAYMENT_TRANSITIONS: dict[PaymentStatus, frozenset[PaymentStatus]] = {
    PaymentStatus.PENDING: frozenset(
        {
            PaymentStatus.PROCESSING,
            PaymentStatus.PAID,
            PaymentStatus.FAILED,
            PaymentStatus.EXPIRED,
            PaymentStatus.CANCELLED,
        }
    ),
    PaymentStatus.PROCESSING: frozenset(
        {
            PaymentStatus.PAID,
            PaymentStatus.FAILED,
            PaymentStatus.EXPIRED,
            PaymentStatus.CANCELLED,
        }
    ),
    PaymentStatus.FAILED: frozenset({PaymentStatus.PROCESSING}),
    PaymentStatus.EXPIRED: frozenset({PaymentStatus.PROCESSING}),
    PaymentStatus.PAID: frozenset(),
    PaymentStatus.CANCELLED: frozenset(),
}


def transition_payment_status(
    current: PaymentStatus, target: PaymentStatus
) -> TransitionResult:
    """Attempt to move a payment from `current` to `target`.

    - Same-state (target == current): always a no-op success
      (`applied=False`) - this is what makes repeated/duplicate PAID
      events harmless.
    - Legal transition: `applied=True`.
    - Illegal transition: raises IllegalTransitionError. The caller decides
      what to do (reconciliation log, safe ignore) - this function never
      silently mutates state on an illegal request.
    """
    if current == target:
        return TransitionResult(applied=False, previous=current, current=current)

    allowed = _PAYMENT_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise IllegalTransitionError(current, target)

    return TransitionResult(applied=True, previous=current, current=target)


def is_payment_terminal(status: PaymentStatus) -> bool:
    """PAID and CANCELLED never accept further transitions in this phase."""
    return status in (PaymentStatus.PAID, PaymentStatus.CANCELLED)


def can_retry_payment(status: PaymentStatus) -> bool:
    """Only FAILED/EXPIRED payments may start a new attempt via /retry."""
    return status in (PaymentStatus.FAILED, PaymentStatus.EXPIRED)


def is_transaction_terminal(status: TransactionStatus) -> bool:
    return status in TRANSACTION_TERMINAL_STATUSES
