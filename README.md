# Gawacha Bazaar

Gawacha Bazaar is a production-grade, farm-to-home fresh food marketplace platform connecting local agricultural producers directly with consumers.

## Architecture Overview

The system is structured as a modular monolith designed for horizontal extensibility:

- **Backend**: Python 3.11 + FastAPI (REST API, versioned endpoints)
- **Database**: PostgreSQL 16
- **ORM & Data Layer**: SQLAlchemy 2.x (declarative base, synchronous connection pooling)
- **PostgreSQL Driver**: psycopg 3 (`postgresql+psycopg://`)
- **Migrations**: Alembic
- **Configuration & Validation**: Pydantic v2 + `pydantic-settings`
- **Authentication**: JWT (`pyjwt`) + Argon2 password hashing (`argon2-cffi`)
- **Testing**: `pytest` + `httpx` / Starlette `TestClient`
- **Linting & Formatting**: Ruff
- **Containerization**: Docker & Docker Compose (health-checked multi-container environment)
- **Frontend Clients (Future Phases)**: Next.js (Web) and React Native (Mobile)

## Repository Structure

```text
GawachaBazaar/
├── backend/
│   ├── app/
│   │   ├── api/             # API versioning & routers (v1)
│   │   ├── core/            # Configuration, logging, security
│   │   ├── db/              # SQLAlchemy 2 declarative base & session factory
│   │   ├── exceptions/      # Uniform application exceptions & error handlers
│   │   ├── models/          # Domain entity models (to be designed)
│   │   ├── repositories/    # Database query abstractions
│   │   ├── schemas/         # Pydantic request/response validation schemas
│   │   ├── services/        # Business logic services
│   │   └── main.py          # FastAPI application factory & lifespan
│   ├── alembic/             # Alembic migration environment and versions
│   ├── tests/               # Pytest automated test suite
│   ├── Dockerfile           # Python 3.11-slim non-root container image
│   ├── .dockerignore        # Container build ignore rules
│   ├── .env.example         # Environment template (no secrets)
│   ├── .gitignore           # Backend git ignore rules
│   ├── alembic.ini          # Alembic configuration
│   ├── pyproject.toml       # Project metadata, Ruff & Pytest settings
│   ├── requirements.txt     # Production dependencies
│   ├── requirements-dev.txt # Development & testing dependencies
│   └── README.md            # Backend developer guide
├── mobile/                  # React Native mobile client (future)
├── web/                     # Next.js web application (future)
├── docker-compose.yml       # Production-ready local container orchestration
├── .gitignore               # Root git ignore rules
└── README.md                # Root project documentation
```

## Prerequisites

- **Python**: 3.11+
- **Docker & Docker Compose**: v2.20+ / Docker Desktop
- **PostgreSQL**: 16 (via Docker Compose or local installation)

## Getting Started

### 1. Local Host Development Setup

```bash
# Navigate to backend directory
cd backend

# Create and activate Python virtual environment
python -m venv venv

# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# Linux/macOS:
# source venv/bin/activate

# Install dependencies
pip install -r requirements.txt -r requirements-dev.txt

# Create local environment file from template
cp .env.example .env
```

### 2. Running Quality Checks & Tests

```bash
cd backend

# Run Ruff linter and formatter checks
python -m ruff check .

# Run automated tests
python -m pytest -v
```

### 3. Database Migrations (Alembic)

```bash
cd backend

# Inspect current migration version
alembic current

# Run migrations to head
alembic upgrade head
```

### 4. Running the Backend Server

```bash
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- **Interactive API Docs (Swagger)**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Service Health Check**: `GET http://127.0.0.1:8000/health`
- **Database Health Check**: `GET http://127.0.0.1:8000/health/db`

### 5. Running with Docker Compose

Docker Compose coordinates both the PostgreSQL database and the FastAPI backend service with integrated healthchecks:

```bash
# Validate compose configuration
docker compose config

# Build and start services in background
docker compose up --build -d

# Check service health and status
docker compose ps

# View service logs
docker compose logs -f backend
```

> **Port Conflict Note**: To prevent collisions with any local PostgreSQL instance already running on host port `5432`, the containerized PostgreSQL binds to host port `5433` by default (`POSTGRES_HOST_PORT=5433`). Within Docker network, the backend connects directly via `db:5432`.
