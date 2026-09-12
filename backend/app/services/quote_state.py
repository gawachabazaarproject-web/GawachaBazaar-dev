"""Quote version state machine.

Same pure-logic pattern as the other *_state.py modules.

    DRAFT -> SENT -> {SUPERSEDED, ACCEPTED, REJECTED, EXPIRED}
    DRAFT -> CANCELLED
    SENT -> CANCELLED

SUPERSEDED/ACCEPTED/REJECTED/EXPIRED/CANCELLED are all terminal for that
row - a re-negotiation never reopens or mutates an old version, it
creates a brand new DRAFT (see BulkOrderService.create_quote_version),
preserving commercial history. Once ACCEPTED, a version's commercial
terms are immutable - there is no transition out of ACCEPTED.
"""

from dataclasses import dataclass
from enum import StrEnum


class QuoteVersionStatus(StrEnum):
    DRAFT = "DRAFT"
    SENT = "SENT"
    SUPERSEDED = "SUPERSEDED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


TERMINAL_QUOTE_VERSION_STATUSES = frozenset(
    {
        QuoteVersionStatus.SUPERSEDED,
        QuoteVersionStatus.ACCEPTED,
        QuoteVersionStatus.REJECTED,
        QuoteVersionStatus.EXPIRED,
        QuoteVersionStatus.CANCELLED,
    }
)

_QUOTE_VERSION_TRANSITIONS: dict[QuoteVersionStatus, frozenset[QuoteVersionStatus]] = {
    QuoteVersionStatus.DRAFT: frozenset(
        {QuoteVersionStatus.SENT, QuoteVersionStatus.CANCELLED}
    ),
    QuoteVersionStatus.SENT: frozenset(
        {
            QuoteVersionStatus.SUPERSEDED,
            QuoteVersionStatus.ACCEPTED,
            QuoteVersionStatus.REJECTED,
            QuoteVersionStatus.EXPIRED,
            QuoteVersionStatus.CANCELLED,
        }
    ),
    QuoteVersionStatus.SUPERSEDED: frozenset(),
    QuoteVersionStatus.ACCEPTED: frozenset(),
    QuoteVersionStatus.REJECTED: frozenset(),
    QuoteVersionStatus.EXPIRED: frozenset(),
    QuoteVersionStatus.CANCELLED: frozenset(),
}


class IllegalQuoteVersionTransitionError(Exception):
    def __init__(self, current: "QuoteVersionStatus", target: "QuoteVersionStatus") -> None:
        self.current = current
        self.target = target
        super().__init__(
            f"Illegal quote version status transition: {current.value} -> {target.value}"
        )


@dataclass(frozen=True)
class QuoteVersionTransitionResult:
    applied: bool
    previous: QuoteVersionStatus
    current: QuoteVersionStatus


def transition_quote_version_status(
    current: QuoteVersionStatus, target: QuoteVersionStatus
) -> QuoteVersionTransitionResult:
    if current == target:
        return QuoteVersionTransitionResult(applied=False, previous=current, current=current)

    allowed = _QUOTE_VERSION_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise IllegalQuoteVersionTransitionError(current, target)

    return QuoteVersionTransitionResult(applied=True, previous=current, current=target)


def is_quote_version_terminal(status: QuoteVersionStatus) -> bool:
    return status in TERMINAL_QUOTE_VERSION_STATUSES
