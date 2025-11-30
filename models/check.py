from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class DayStatusBase(BaseModel):
    date: datetime
    is_checked: bool = False
    checked_at: Optional[datetime] = None


class DayStatus(DayStatusBase):
    id: str
    
    class Config:
        from_attributes = True


class CheckBase(BaseModel):
    name: str
    count: int


class CheckCreate(CheckBase):
    pass


class CheckUpdate(BaseModel):
    name: Optional[str] = None
    count: Optional[int] = None


class Check(CheckBase):
    id: str
    created_at: datetime
    day_statuses: List[DayStatus] = []
    
    class Config:
        from_attributes = True


class CheckResponse(BaseModel):
    id: str
    name: str
    count: int
    created_at: datetime
    passed_days: int
    percentage: int
    days: List[DayStatus]


class CheckTodayRequest(BaseModel):
    check_id: str


class CheckListResponse(BaseModel):
    checks: List[CheckResponse]

