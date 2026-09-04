from fastapi import APIRouter

api_router = APIRouter()


@api_router.get("/ping", tags=["system"])
def ping() -> dict[str, str]:
    """Simple ping check for API v1."""
    return {"ping": "pong"}
