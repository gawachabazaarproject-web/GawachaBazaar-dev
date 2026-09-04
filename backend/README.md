# Gawacha Bazaar Backend

Production-grade FastAPI backend service for the Gawacha Bazaar platform.

## Architecture

- **Framework**: FastAPI (Python 3.11+)
- **Data Access & ORM**: SQLAlchemy 2.x (`DeclarativeBase`, synchronous connection pooling)
- **Database Driver**: psycopg 3 (`postgresql+psycopg://`)
- **Database Migrations**: Alembic
- **Settings & Validation**: Pydantic v2 + `pydantic-settings`
- **Security**: Argon2 password hashing (`argon2-cffi`) + JWT access tokens (`pyjwt`)
- **Testing**: `pytest` + `httpx` / Starlette `TestClient`
- **Linter & Formatter**: Ruff

## Directory Structure

```text
backend/
├── app/
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       └── router.py         # API v1 routes
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py             # Pydantic Settings & environment parsing
│   │   ├── logging.py            # Structured application logging
│   │   └── security.py           # Argon2 and JWT utilities
│   ├── db/
│   │   ├── __init__.py
│   │   ├── base.py               # SQLAlchemy 2 DeclarativeBase
│   │   └── session.py            # Engine, session factory & get_db dependency
│   ├── exceptions/
│   │   └── __init__.py           # Custom AppExceptions & global error handlers
│   ├── models/                   # Domain ORM models (reserved for schema phase)
│   ├── repositories/             # Data access repositories (reserved for schema phase)
│   ├── schemas/                  # Pydantic request/response schemas
│   ├── services/                 # Business logic services
│   └── main.py                   # Application factory, lifespan, health routes
├── alembic/
│   ├── env.py                    # Alembic migration environment
│   ├── script.py.mako            # Migration template
│   └── versions/                 # Migration revision scripts
├── tests/
│   ├── __init__.py
│   ├── conftest.py               # Test fixtures (TestClient)
│   ├── test_config.py            # Settings validation tests
│   ├── test_exceptions.py        # Error response structure tests
│   ├── test_health.py            # Service and database health tests
│   └── test_security.py          # Password hashing & JWT tests
├── Dockerfile                    # Python 3.11-slim non-root container definition
├── .dockerignore
├── .env                          # Local environment variables (never committed)
├── .env.example                  # Environment variable template
├── .gitignore                    # Backend git ignore rules
├── alembic.ini                   # Alembic configuration
├── pyproject.toml                # Build & tool configurations (Ruff, Pytest)
├── requirements.txt              # Production dependencies
├── requirements-dev.txt          # Development dependencies
└── README.md
```

## Setup Instructions

### 1. Virtual Environment & Dependencies

```bash
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt

# Linux/macOS:
# source venv/bin/activate
# pip install -r requirements.txt -r requirements-dev.txt
```

### 2. Environment Configuration

Copy `.env.example` to `.env` and configure your local parameters:

```bash
cp .env.example .env
```

Ensure `JWT_SECRET_KEY` is a strong random secret. Never commit `.env` to source control.

### 3. Running Code Quality & Tests

```bash
# Lint and format checks
python -m ruff check .

# Run test suite
python -m pytest -v
```

### 4. Database Migrations

```bash
# Check current migration version
alembic current

# Run migrations to head
alembic upgrade head
```

### 5. Running the Application Server

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- **Interactive API Documentation**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Health Check**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- **Database Probe**: [http://127.0.0.1:8000/health/db](http://127.0.0.1:8000/health/db)
