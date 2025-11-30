from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List
import uuid

from models.check import CheckCreate, CheckUpdate, CheckResponse, CheckListResponse, DayStatus
from models.db_check import DBCheck, DBDayStatus
from models.db_user import DBUser
from database import get_db
from routers.auth import get_current_user

security = HTTPBearer()

router = APIRouter(prefix="/api/v1/checks", tags=["checks"])


def calculate_stats(check: DBCheck) -> tuple[int, int]:
    """Calculate passed_days and percentage for a check"""
    today = datetime.utcnow().date()
    created_date = check.created_at.date()
    
    # Calculate passed days
    passed_days = (today - created_date).days
    
    # Count checked days
    checked_count = sum(1 for day in check.day_statuses if day.is_checked)
    
    # Calculate percentage
    percentage = int((checked_count / check.count * 100)) if check.count > 0 else 0
    
    return passed_days, percentage


def check_to_response(check: DBCheck) -> CheckResponse:
    """Convert DBCheck to CheckResponse"""
    passed_days, percentage = calculate_stats(check)
    
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
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
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
            today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
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
    
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_date = today.date()
    
    # Find existing day status for today
    existing_day = None
    for day in check.day_statuses:
        if day.date.date() == today_date:
            existing_day = day
            break
    
    if existing_day:
        # Update existing day
        existing_day.is_checked = True
        existing_day.checked_at = datetime.utcnow()
    else:
        # Create new day status for today
        new_day = DBDayStatus(
            id=str(uuid.uuid4()),
            check_id=check.id,
            date=today,
            is_checked=True,
            checked_at=datetime.utcnow()
        )
        db.add(new_day)
        # Update count if today is beyond the original count
        if today_date > (check.created_at.date() + timedelta(days=check.count - 1)):
            check.count += 1
    
    db.commit()
    db.refresh(check)
    
    return check_to_response(check)

