from app.core.security import hash_password, verify_password


def test_password_hashing() -> None:
    """Verify Argon2 password hashing and verification."""
    password = "MySecurePassword123!"
    hashed = hash_password(password)

    assert hashed != password
    assert hashed.startswith("$argon2")
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_uvicorn_websocket_handshake_log_redacts_token() -> None:
    """uvicorn logs WebSocket handshakes on `uvicorn.error` with the full
    query string - the realtime socket's access token must never reach
    the log output (see RedactTokenQueryFilter)."""
    import logging

    import app.core.logging  # noqa: F401 - installs the filters

    uvicorn_error = logging.getLogger("uvicorn.error")
    record = uvicorn_error.makeRecord(
        "uvicorn.error", logging.INFO, __file__, 0,
        '%s - "WebSocket %s" [accepted]',
        ("127.0.0.1:5000", "/api/v1/ws/events?token=eyJhbGciOi.secret.sig&x=1"),
        None,
    )
    assert all(f.filter(record) for f in uvicorn_error.filters)
    message = record.getMessage()
    assert "eyJhbGciOi" not in message
    assert "token=[REDACTED]&x=1" in message
