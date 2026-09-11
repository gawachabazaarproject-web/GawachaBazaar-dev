"""Phase 14 unit tests: payment state machine.

Pure logic tests - no DB, no HTTP, no gateway. This is the complete
transition matrix required by the spec: every legal transition, every
illegal transition, terminal-state behavior, and idempotent no-ops.

The expected matrix below is written independently of
app/services/payment_state.py's internal `_PAYMENT_TRANSITIONS` dict (not
just re-deriving from it) so this test actually locks in the *intended*
behavior - if a future edit to that dict silently changes what's legal,
this test catches it rather than trivially agreeing with it.
"""

import pytest

from app.services.payment_state import (
    IllegalTransitionError,
    PaymentStatus,
    TransactionStatus,
    can_retry_payment,
    is_payment_terminal,
    is_transaction_terminal,
    transition_payment_status,
)

ALL_STATUSES = list(PaymentStatus)

# The complete, explicitly-authored legal-transition matrix (current -> {legal targets}).
# Matches the spec's given matrix plus the two documented extensions from
# the module docstring (PENDING direct-to-terminal, PROCESSING->CANCELLED).
_EXPECTED_LEGAL: dict[PaymentStatus, set[PaymentStatus]] = {
    PaymentStatus.PENDING: {
        PaymentStatus.PROCESSING,
        PaymentStatus.PAID,
        PaymentStatus.FAILED,
        PaymentStatus.EXPIRED,
        PaymentStatus.CANCELLED,
    },
    PaymentStatus.PROCESSING: {
        PaymentStatus.PAID,
        PaymentStatus.FAILED,
        PaymentStatus.EXPIRED,
        PaymentStatus.CANCELLED,
    },
    PaymentStatus.FAILED: {PaymentStatus.PROCESSING},
    PaymentStatus.EXPIRED: {PaymentStatus.PROCESSING},
    PaymentStatus.PAID: set(),
    PaymentStatus.CANCELLED: set(),
}


@pytest.mark.parametrize(
    "current,target",
    [(c, t) for c in ALL_STATUSES for t in ALL_STATUSES if c != t],
)
def test_full_transition_matrix(current: PaymentStatus, target: PaymentStatus) -> None:
    """Every non-self-transition in the 6x6 matrix (30 pairs): legal ones
    apply cleanly, everything else raises IllegalTransitionError.
    """
    if target in _EXPECTED_LEGAL[current]:
        result = transition_payment_status(current, target)
        assert result.applied is True
        assert result.previous == current
        assert result.current == target
    else:
        with pytest.raises(IllegalTransitionError) as exc_info:
            transition_payment_status(current, target)
        assert exc_info.value.current == current
        assert exc_info.value.target == target


@pytest.mark.parametrize("status", ALL_STATUSES)
def test_same_state_is_always_a_noop(status: PaymentStatus) -> None:
    """Repeated identical events (e.g. duplicate PAID webhook) must never
    error and must never report as 'applied'.
    """
    result = transition_payment_status(status, status)
    assert result.applied is False
    assert result.previous == status
    assert result.current == status


def test_paid_is_terminal_no_outgoing_transitions() -> None:
    for target in ALL_STATUSES:
        if target == PaymentStatus.PAID:
            continue
        with pytest.raises(IllegalTransitionError):
            transition_payment_status(PaymentStatus.PAID, target)


def test_late_failed_after_paid_never_downgrades() -> None:
    """The single most important guarantee in this phase: a FAILED event
    arriving after PAID must be rejected, never silently applied.
    """
    with pytest.raises(IllegalTransitionError) as exc_info:
        transition_payment_status(PaymentStatus.PAID, PaymentStatus.FAILED)
    assert exc_info.value.current == PaymentStatus.PAID
    assert exc_info.value.target == PaymentStatus.FAILED


def test_paid_to_expired_and_cancelled_forbidden() -> None:
    with pytest.raises(IllegalTransitionError):
        transition_payment_status(PaymentStatus.PAID, PaymentStatus.EXPIRED)
    with pytest.raises(IllegalTransitionError):
        transition_payment_status(PaymentStatus.PAID, PaymentStatus.CANCELLED)


def test_cancelled_is_terminal() -> None:
    for target in ALL_STATUSES:
        if target == PaymentStatus.CANCELLED:
            continue
        with pytest.raises(IllegalTransitionError):
            transition_payment_status(PaymentStatus.CANCELLED, target)


def test_failed_and_expired_can_retry_to_processing() -> None:
    assert transition_payment_status(
        PaymentStatus.FAILED, PaymentStatus.PROCESSING
    ).applied is True
    assert transition_payment_status(
        PaymentStatus.EXPIRED, PaymentStatus.PROCESSING
    ).applied is True


def test_failed_cannot_jump_directly_to_paid() -> None:
    """A retry must go through PROCESSING again - FAILED cannot become PAID
    in one step (there is no attempt in flight to have succeeded).
    """
    with pytest.raises(IllegalTransitionError):
        transition_payment_status(PaymentStatus.FAILED, PaymentStatus.PAID)


def test_is_payment_terminal() -> None:
    assert is_payment_terminal(PaymentStatus.PAID) is True
    assert is_payment_terminal(PaymentStatus.CANCELLED) is True
    for status in (
        PaymentStatus.PENDING,
        PaymentStatus.PROCESSING,
        PaymentStatus.FAILED,
        PaymentStatus.EXPIRED,
    ):
        assert is_payment_terminal(status) is False


def test_can_retry_payment() -> None:
    assert can_retry_payment(PaymentStatus.FAILED) is True
    assert can_retry_payment(PaymentStatus.EXPIRED) is True
    for status in (
        PaymentStatus.PENDING,
        PaymentStatus.PROCESSING,
        PaymentStatus.PAID,
        PaymentStatus.CANCELLED,
    ):
        assert can_retry_payment(status) is False


def test_is_transaction_terminal() -> None:
    for status in (
        TransactionStatus.SUCCESS,
        TransactionStatus.FAILED,
        TransactionStatus.CANCELLED,
        TransactionStatus.EXPIRED,
    ):
        assert is_transaction_terminal(status) is True
    for status in (TransactionStatus.INITIATED, TransactionStatus.PROCESSING):
        assert is_transaction_terminal(status) is False
