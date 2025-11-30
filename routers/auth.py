from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
import os

from models.user import RegisterRequest, LoginRequest, AuthResponse
from models.db_user import DBUser
from database import get_db

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = os.getenv("SECRET_KEY", "bd63be1361e7820f1c5533db622826dea58e0cfea9084c8d3a928d0425297de73c8fc43da7093a990fca8d3b5598b34d42623402f0bed89bad3f89378bc57721")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30 * 24 * 60  # 30 days

security = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_current_user(token: str, db: Session) -> Optional[DBUser]:
    """Get current user from JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return None
        return db.query(DBUser).filter(DBUser.email == email).first()
    except JWTError:
        return None


@router.post("/register", response_model=AuthResponse)
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """
    Register a new user
    
    Expected from Swift app:
    - username: String
    - email: String
    - password: String
    """
    # Check if email already exists
    existing_user = db.query(DBUser).filter(DBUser.email == request.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Check if username already exists
    existing_username = db.query(DBUser).filter(DBUser.username == request.username).first()
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
    
    # Create new user
    hashed_password = get_password_hash(request.password)
    
    db_user = DBUser(
        username=request.username,
        email=request.email,
        hashed_password=hashed_password
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    access_token = create_access_token(data={"sub": request.email})
    
    return AuthResponse(
        success=True,
        message="User registered successfully",
        token=access_token,
        user={
            "id": db_user.id,
            "username": db_user.username,
            "email": db_user.email
        }
    )


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    Login user
    
    Expected from Swift app:
    - email: String
    - password: String
    """
    user = db.query(DBUser).filter(DBUser.email == request.email).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    access_token = create_access_token(data={"sub": request.email})
    
    return AuthResponse(
        success=True,
        message="Login successful",
        token=access_token,
        user={
            "id": user.id,
            "username": user.username,
            "email": user.email
        }
    )


@router.get("/me")
async def get_me(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Get current user information
    
    Requires Authorization header: Bearer <token>
    """
    token = credentials.credentials
    user = get_current_user(token, db)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "created_at": user.created_at.isoformat()
    }
