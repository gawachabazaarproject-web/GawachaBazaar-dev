"""Writes to the generic admin-action audit ledger (`admin_action_logs`).

Deliberately not its own transaction: `record()` only adds to the session
and flushes - it never calls `db.commit()`. Every call site sits inside a
mutation that already commits once at the end of its own transaction (the
same pattern `StockMovement`/`PaymentTransaction` writes already follow),
so an audit entry and the business mutation it describes always land in
the same atomic commit, or neither does - there is no window where a
mutation succeeds but its audit record is silently lost.
"""

from sqlalchemy.orm import Session

from app.models.admin_action_log import AdminActionLog


class AdminAuditService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self,
        *,
        admin_user_id: int,
        action: str,
        resource_type: str,
        resource_id: int,
        previous_state: str | None = None,
        new_state: str | None = None,
        reason: str | None = None,
    ) -> None:
        self.db.add(
            AdminActionLog(
                admin_user_id=admin_user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                previous_state=previous_state,
                new_state=new_state,
                reason=reason,
            )
        )
        self.db.flush()
