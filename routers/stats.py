from datetime import datetime, timezone, timedelta, date

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from database import get_db
from models.check import YearActivityResponse, YearDayActivity
from models.db_check import DBCheck, DBDayStatus
from models.db_user import DBUser
from routers.auth import get_current_user


router = APIRouter(prefix="/api/v1/stats", tags=["stats"])

security = HTTPBearer()


def get_user_from_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> DBUser:
    """Get current user from JWT token"""
    token = credentials.credentials
    user = get_current_user(token, db)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return user


@router.get("/yearly-activity", response_model=YearActivityResponse)
async def get_yearly_activity(
    year: int,
    user: DBUser = Depends(get_user_from_token),
    db: Session = Depends(get_db),
):
    """
    Return GitHub-style yearly activity for the given year.

    For each day of the year, we count how many checks were completed
    (i.e., day statuses with is_checked = True) across all checks of the user.
    """
    if year < 1970 or year > 2100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Year must be between 1970 and 2100",
        )

    start_dt = datetime(year, 1, 1, tzinfo=timezone.utc)
    end_dt = datetime(year + 1, 1, 1, tzinfo=timezone.utc)

    # Query all checked day statuses for this user in the given year
    day_statuses = (
        db.query(DBDayStatus)
        .join(DBCheck, DBDayStatus.check_id == DBCheck.id)
        .filter(
            DBCheck.user_id == user.id,
            DBDayStatus.is_checked.is_(True),
            DBDayStatus.date >= start_dt,
            DBDayStatus.date < end_dt,
        )
        .all()
    )

    # Aggregate by date
    counts_by_date: dict[date, int] = {}
    for day in day_statuses:
        dt = day.date
        if dt.tzinfo is not None:
            d = dt.astimezone(timezone.utc).date()
        else:
            d = dt.date()
        counts_by_date[d] = counts_by_date.get(d, 0) + 1

    # Build a full list of days for the year
    days: list[YearDayActivity] = []
    current = start_dt.date()
    while current < end_dt.date():
        count = counts_by_date.get(current, 0)
        days.append(YearDayActivity(date=current, completed_count=count))
        current += timedelta(days=1)

    max_count = max((d.completed_count for d in days), default=0)

    return YearActivityResponse(year=year, max_count=max_count, days=days)


