"""Admin panel home ("Today at Gawacha Bazaar") - live operational
snapshot. `reports.read` (ADMIN, OPERATIONS) - the same people who see the
reports this summarizes."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies.auth import require_permission
from app.dependencies.database import get_db
from app.models.user import User
from app.schemas.dashboard import DashboardSummaryResponse
from app.services.dashboard import DashboardService

router = APIRouter()


@router.get(
    "",
    response_model=DashboardSummaryResponse,
    summary="Today's orders, collections, fulfilment backlog, low stock and delivery issues",
)
def get_dashboard(
    _current_user: User = Depends(require_permission("reports.read")),
    db: Session = Depends(get_db),
) -> DashboardSummaryResponse:
    return DashboardService(db).summary(now=datetime.now(UTC))
