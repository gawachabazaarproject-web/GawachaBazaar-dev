"""Inventory reservation state machine.

Mirrors app/services/payment_state.py's pattern: pure transition logic, no
DB/HTTP dependencies, single source of truth for what a reservation may
legally become next.

RESERVATION LIFECYCLE
======================
    ACTIVE    -> COMMITTED   (payment succeeded / COD accepted before expiry)
    ACTIVE    -> RELEASED    (generic release - order cancelled before
                              confirmation)
    ACTIVE    -> EXPIRED     (30-minute payment window elapsed, detected
                              lazily by whichever operation next touches the
                              reservation)
    COMMITTED -> RELEASED    (Phase 18: order cancelled AFTER confirmation
                              but before delivery - the central Phase 18
                              rule is "cancel any time before delivery is
                              completed", and a confirmed order's
                              reservation is COMMITTED, not ACTIVE, so this
                              is the one deliberate exception to
                              COMMITTED's prior terminal-ness. See
                              InventoryReservationService.release_reservation_for_order.)

RELEASED and EXPIRED are fully terminal (`TERMINAL_RESERVATION_STATUSES`).
COMMITTED is terminal in every direction except the one Phase 18 edge
above. In particular this means a reservation that expired can never be
resurrected by a late-arriving payment success; see
InventoryReservationService.commit_reservation_for_order for how that
invariant is enforced under a row lock. Once RELEASED (whichever prior
state it came from), a reservation never returns - a cancelled order's
reservation cannot be recommitted.
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
    ReservationStatus.COMMITTED: frozenset({ReservationStatus.RELEASED}),
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
