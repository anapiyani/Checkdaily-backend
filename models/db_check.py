from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import uuid


class DBCheck(Base):
    """SQLAlchemy Check model (durations in Swift)"""
    __tablename__ = "checks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship to day statuses
    day_statuses = relationship("DBDayStatus", back_populates="check", cascade="all, delete-orphan")
    
    # Relationship to user
    user = relationship("DBUser", back_populates="checks")


class DBDayStatus(Base):
    """SQLAlchemy DayStatus model"""
    __tablename__ = "day_statuses"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    check_id = Column(String, ForeignKey("checks.id"), nullable=False, index=True)
    date = Column(DateTime(timezone=True), nullable=False, index=True)
    is_checked = Column(Boolean, nullable=False, default=False)
    checked_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationship to check
    check = relationship("DBCheck", back_populates="day_statuses")

