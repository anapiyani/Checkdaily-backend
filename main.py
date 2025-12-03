from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import auth, checks, user_settings, stats
from database import init_db
# Import models to ensure they're registered with SQLAlchemy
from models.db_user import DBUser
from models.db_check import DBCheck, DBDayStatus

app = FastAPI(
    title="CheckDaily API",
    description="Backend API for CheckDaily application",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    init_db()

app.include_router(auth.router)
app.include_router(checks.router)
app.include_router(user_settings.router)
app.include_router(stats.router)

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Welcome to CheckDaily API"}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

