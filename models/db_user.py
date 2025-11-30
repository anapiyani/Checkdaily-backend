from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class DBUser(Base):
    """SQLAlchemy User model for database"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Profile fields
    display_name = Column(String, nullable=True)
    bio = Column(Text, nullable=True)
    profile_picture_url = Column(String, nullable=True)
    
    # Relationship to checks
    checks = relationship("DBCheck", back_populates="user", cascade="all, delete-orphan")

