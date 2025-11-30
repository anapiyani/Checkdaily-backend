# CheckDaily Backend

FastAPI backend application for CheckDaily.

## Getting Started

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

### Installation

1. Create a virtual environment (recommended):
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

### Running the Application

Start the development server:
```bash
uvicorn main:app --reload
```

The API will be available at:
- **API**: http://localhost:8000
- **Interactive API docs (Swagger UI)**: http://localhost:8000/docs
- **Alternative API docs (ReDoc)**: http://localhost:8000/redoc

### Project Structure

```
CheckDaily-backend/
├── main.py              # Main FastAPI application
├── requirements.txt     # Python dependencies
├── routers/            # API route handlers
├── models/             # Pydantic models
├── schemas/            # Database schemas (if using SQLAlchemy)
└── README.md           # This file
```

### Development

- The `--reload` flag enables auto-reload on code changes
- API documentation is automatically generated from your code
- Use type hints and Pydantic models for automatic validation

## Authentication API

### Register User
**POST** `/api/v1/auth/register`

Request body:
```json
{
  "username": "john_doe",
  "email": "john@example.com",
  "password": "securepassword123"
}
```

Response:
```json
{
  "success": true,
  "message": "User registered successfully",
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": 1,
    "username": "john_doe",
    "email": "john@example.com"
  }
}
```

### Login User
**POST** `/api/v1/auth/login`

Request body:
```json
{
  "email": "john@example.com",
  "password": "securepassword123"
}
```

Response:
```json
{
  "success": true,
  "message": "Login successful",
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": 1,
    "username": "john_doe",
    "email": "john@example.com"
  }
}
```

### Get Current User
**GET** `/api/v1/auth/me`

Headers:
```
Authorization: Bearer <token>
```

Response:
```json
{
  "id": 1,
  "username": "john_doe",
  "email": "john@example.com",
  "created_at": "2025-01-15T10:30:00"
}
```

### Swift Integration Notes

1. Store the `token` from register/login responses
2. Include token in Authorization header for protected endpoints: `Authorization: Bearer <token>`
3. Token expires after 30 days
4. Update your Swift `AuthStorage` to store the token instead of using UserDefaults for authentication

