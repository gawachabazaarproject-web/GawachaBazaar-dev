"""Inventory reservation state machine.

Mirrors app/services/payment_state.py's pattern: pure transition logic, no
DB/HTTP dependencies, single source of truth for what a reservation may
legally become next.

RESERVATION LIFECYCLE
======================
    ACTIVE -> COMMITTED   (payment succeeded / COD accepted before expiry)
    ACTIVE -> RELEASED    (generic release - kept reusable for a future
                           cancellation feature; nothing in Phase 15 calls
                           this automatically)
    ACTIVE -> EXPIRED     (30-minute payment window elapsed, detected
                           lazily by whichever operation next touches the
                           reservation)

COMMITTED, RELEASED, and EXPIRED are all terminal - once a reservation
leaves ACTIVE it never returns. In particular this means a reservation
that expired can never be resurrected by a late-arriving payment success;
see InventoryReservationService.commit_reservation_for_order for how that
invariant is enforced under a row lock.
"""

from dataclasses import dataclass
from enum import StrEnum


class ReservationStatus(StrEnum):
    ACTIVE = "ACTIVE"
    COMMITTED = "COMMITTED"
    RELEASED = "RELEASED"
    EXPIRED = "EXPIRED"


TERMINAL_RESERVATION_STATUSES = frozenset(
    {
        ReservationStatus.COMMITTED,
        ReservationStatus.RELEASED,
        ReservationStatus.EXPIRED,
    }
)


class IllegalReservationTransitionError(Exception):
    """Raised when a requested reservation status transition is not legal."""

    def __init__(self, current: "ReservationStatus", target: "ReservationStatus") -> None:
        self.current = current
        self.target = target
        super().__init__(
            f"Illegal reservation status transition: {current.value} -> {target.value}"
        )


@dataclass(frozen=True)
class ReservationTransitionResult:
    applied: bool
    previous: ReservationStatus
    current: ReservationStatus


_RESERVATION_TRANSITIONS: dict[ReservationStatus, frozenset[ReservationStatus]] = {
    ReservationStatus.ACTIVE: frozenset(
        {
            ReservationStatus.COMMITTED,
            ReservationStatus.RELEASED,
            ReservationStatus.EXPIRED,
        }
    ),
    ReservationStatus.COMMITTED: frozenset(),
    ReservationStatus.RELEASED: frozenset(),
    ReservationStatus.EXPIRED: frozenset(),
}


def transition_reservation_status(
    current: ReservationStatus, target: ReservationStatus
) -> ReservationTransitionResult:
    if current == target:
        return ReservationTransitionResult(
            applied=False, previous=current, current=current
        )

    allowed = _RESERVATION_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise IllegalReservationTransitionError(current, target)

    return ReservationTransitionResult(applied=True, previous=current, current=target)


def is_reservation_terminal(status: ReservationStatus) -> bool:
    return status in TERMINAL_RESERVATION_STATUSES
