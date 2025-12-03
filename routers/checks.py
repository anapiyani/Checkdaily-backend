from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import List
import uuid

from models.check import (
    CheckCreate,
    CheckUpdate,
    CheckResponse,
    CheckListResponse,
    DayStatus,
)
from models.db_check import DBCheck, DBDayStatus
from models.db_user import DBUser
from database import get_db
from routers.auth import get_current_user

security = HTTPBearer()

router = APIRouter(prefix="/api/v1/checks", tags=["checks"])


def _normalize_date(dt: datetime) -> datetime.date:
    """Normalize a stored datetime to a UTC date."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).date()
    return dt.date()


def calculate_stats(check: DBCheck) -> tuple[int, int, int, int]:
    """
    Calculate:
    - passed_days: days since creation (inclusive)
    - percentage: checked days / count * 100
    - current_streak: consecutive checked days ending today
    - longest_streak: maximum consecutive checked days
    """
    today = datetime.now(timezone.utc).date()

    # Handle timezone-aware or naive datetime for created_at
    created_at = check.created_at
    if isinstance(created_at, datetime):
        created_date = _normalize_date(created_at)
    else:
        created_date = created_at

    # passed_days: days since creation including today (min 1)
    if created_date == today:
        passed_days = 1
    else:
        passed_days = max(1, (today - created_date).days + 1)

    # Prepare sorted list of days up to today
    days_sorted = sorted(check.day_statuses, key=lambda d: d.date)
    days_sorted = [
        d for d in days_sorted if _normalize_date(d.date) <= today
    ]

    # Count checked days for percentage
    checked_count = sum(1 for day in days_sorted if day.is_checked)
    percentage = int((checked_count / check.count * 100)) if check.count > 0 else 0

    # Longest streak & current streak
    longest_streak = 0
    current_streak = 0

    # Longest streak: walk forward through days
    streak = 0
    last_date = None
    for day in days_sorted:
        day_date = _normalize_date(day.date)
        if day.is_checked:
            if last_date is None or (day_date - last_date).days == 1:
                streak += 1
            else:
                streak = 1
            last_date = day_date
            longest_streak = max(longest_streak, streak)
        else:
            # gap or unchecked breaks streak
            last_date = day_date
            streak = 0

    # Current streak: walk backwards from today
    target_date = today
    for day in reversed(days_sorted):
        day_date = _normalize_date(day.date)
        if day_date < target_date:
            # once we've passed the target_date, if we haven't found a checked
            # day for it, streak ends
            break
        if day_date == target_date:
            if day.is_checked:
                current_streak += 1
                target_date = target_date - timedelta(days=1)
            else:
                break

    return passed_days, percentage, current_streak, longest_streak


def check_to_response(check: DBCheck) -> CheckResponse:
    """Convert DBCheck to CheckResponse"""
    passed_days, percentage, current_streak, longest_streak = calculate_stats(check)
    
    days = [
        DayStatus(
            id=day.id,
            date=day.date,
            is_checked=day.is_checked,
            checked_at=day.checked_at
        )
        for day in sorted(check.day_statuses, key=lambda d: d.date)
    ]
    
    return CheckResponse(
        id=check.id,
        name=check.name,
        count=check.count,
        created_at=check.created_at,
        passed_days=passed_days,
        percentage=percentage,
        current_streak=current_streak,
        longest_streak=longest_streak,
        days=days
    )


def get_user_from_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> DBUser:
    """Get current user from JWT token"""
    token = credentials.credentials
    user = get_current_user(token, db)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    return user


@router.get("", response_model=CheckListResponse)
async def get_all_checks(
    user: DBUser = Depends(get_user_from_token),
    db: Session = Depends(get_db)
):
    """
    Get all checks for the current user
    
    Returns list of all checks with their day statuses
    """
    checks = db.query(DBCheck).filter(DBCheck.user_id == user.id).all()
    
    return CheckListResponse(
        checks=[check_to_response(check) for check in checks]
    )


@router.get("/{check_id}", response_model=CheckResponse)
async def get_check(
    check_id: str,
    user: DBUser = Depends(get_user_from_token),
    db: Session = Depends(get_db)
):
    """
    Get a specific check by ID
    """
    check = db.query(DBCheck).filter(
        DBCheck.id == check_id,
        DBCheck.user_id == user.id
    ).first()
    
    if not check:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Check not found"
        )
    
    return check_to_response(check)


@router.post("", response_model=CheckResponse, status_code=status.HTTP_201_CREATED)
async def create_check(
    check_data: CheckCreate,
    user: DBUser = Depends(get_user_from_token),
    db: Session = Depends(get_db)
):
    """
    Create a new check
    
    Expected from Swift app:
    - name: String
    - count: Int (number of days)
    """
    # Create the check
    db_check = DBCheck(
        id=str(uuid.uuid4()),
        user_id=user.id,
        name=check_data.name,
        count=max(0, check_data.count)
    )
    
    db.add(db_check)
    
    # Create initial day statuses for the count
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    day_statuses = []
    
    for i in range(db_check.count):
        day_date = today + timedelta(days=i)
        day_status = DBDayStatus(
            id=str(uuid.uuid4()),
            check_id=db_check.id,
            date=day_date,
            is_checked=False,
            checked_at=None
        )
        day_statuses.append(day_status)
    
    db.add_all(day_statuses)
    db.commit()
    db.refresh(db_check)
    
    return check_to_response(db_check)


@router.put("/{check_id}", response_model=CheckResponse)
async def update_check(
    check_id: str,
    check_data: CheckUpdate,
    user: DBUser = Depends(get_user_from_token),
    db: Session = Depends(get_db)
):
    """
    Update a check (name and/or count)
    """
    check = db.query(DBCheck).filter(
        DBCheck.id == check_id,
        DBCheck.user_id == user.id
    ).first()
    
    if not check:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Check not found"
        )
    
    # Update fields if provided
    if check_data.name is not None:
        check.name = check_data.name
    if check_data.count is not None:
        new_count = max(0, check_data.count)
        
        # If count increased, add new day statuses
        if new_count > check.count:
            today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            existing_dates = {day.date.date() for day in check.day_statuses}
            
            for i in range(check.count, new_count):
                day_date = today + timedelta(days=i)
                if day_date.date() not in existing_dates:
                    day_status = DBDayStatus(
                        id=str(uuid.uuid4()),
                        check_id=check.id,
                        date=day_date,
                        is_checked=False,
                        checked_at=None
                    )
                    db.add(day_status)
        
        # If count decreased, remove extra day statuses (keep checked ones)
        elif new_count < check.count:
            # Sort by date and remove unchecked ones beyond new_count
            sorted_days = sorted(check.day_statuses, key=lambda d: d.date)
            for day in sorted_days[new_count:]:
                if not day.is_checked:
                    db.delete(day)
        
        check.count = new_count
    
    db.commit()
    db.refresh(check)
    
    return check_to_response(check)


@router.delete("/{check_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_check(
    check_id: str,
    user: DBUser = Depends(get_user_from_token),
    db: Session = Depends(get_db)
):
    """
    Delete a check
    """
    check = db.query(DBCheck).filter(
        DBCheck.id == check_id,
        DBCheck.user_id == user.id
    ).first()
    
    if not check:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Check not found"
        )
    
    db.delete(check)
    db.commit()
    
    return None


@router.post("/{check_id}/check-today", response_model=CheckResponse)
async def check_today(
    check_id: str,
    user: DBUser = Depends(get_user_from_token),
    db: Session = Depends(get_db)
):
    """
    Mark today as checked for a specific check
    """
    check = db.query(DBCheck).filter(
        DBCheck.id == check_id,
        DBCheck.user_id == user.id
    ).first()
    
    if not check:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Check not found"
        )
    
    # Get today's date in UTC
    today_utc = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_date = today_utc.date()
    
    # Find existing day status for today
    # Compare dates properly by normalizing both to date objects
    existing_day = None
    for day in check.day_statuses:
        # Get the date part from the stored datetime (which is timezone-aware)
        day_date_obj = day.date
        
        # Convert timezone-aware datetime to UTC date
        if day_date_obj.tzinfo is not None:
            # Timezone-aware: convert to UTC and get date
            day_date = day_date_obj.astimezone(timezone.utc).date()
        elif isinstance(day_date_obj, datetime):
            # Naive datetime: assume UTC and get date
            day_date = day_date_obj.date()
        else:
            # Already a date object
            day_date = day_date_obj
        
        # Compare dates (both should be date objects now)
        if day_date == today_date:
            existing_day = day
            break
    
    if existing_day:
        # Update existing day
        existing_day.is_checked = True
        existing_day.checked_at = datetime.now(timezone.utc)
    else:
        # Create new day status for today
        new_day = DBDayStatus(
            id=str(uuid.uuid4()),
            check_id=check.id,
            date=today_utc,
            is_checked=True,
            checked_at=datetime.now(timezone.utc)
        )
        db.add(new_day)
        # Update count if today is beyond the original count
        last_day = check.created_at.date() + timedelta(days=check.count - 1)
        if today_date > last_day:
            check.count += 1
    
    db.commit()
    db.refresh(check)
    
    return check_to_response(check)


@router.post("/{check_id}/uncheck-today", response_model=CheckResponse)
async def uncheck_today(
    check_id: str,
    user: DBUser = Depends(get_user_from_token),
    db: Session = Depends(get_db)
):
    """
    Mark today's entry as unchecked for a specific check.
    This lets the user undo an accidental check-in.
    """
    check = db.query(DBCheck).filter(
        DBCheck.id == check_id,
        DBCheck.user_id == user.id
    ).first()
    
    if not check:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Check not found"
        )
    
    # Work with UTC dates
    today_utc = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_date = today_utc.date()
    
    # Locate today's day status entry
    target_day = None
    for day in check.day_statuses:
        day_date_obj = day.date
        if isinstance(day_date_obj, datetime):
            if day_date_obj.tzinfo is not None:
                current_date = day_date_obj.astimezone(timezone.utc).date()
            else:
                current_date = day_date_obj.date()
        else:
            current_date = day_date_obj
        
        if current_date == today_date:
            target_day = day
            break
    
    if not target_day:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Today is not part of this check or was never generated"
        )
    
    target_day.is_checked = False
    target_day.checked_at = None
    
    db.commit()
    db.refresh(check)
    
    return check_to_response(check)
