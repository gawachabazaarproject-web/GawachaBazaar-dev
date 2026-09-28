import logging
import re
import sys

from app.core.config import settings
from app.core.request_id import get_request_id

_TOKEN_QUERY_RE = re.compile(r"(\btoken=)[^&\s\"']+")


class RedactTokenQueryFilter(logging.Filter):
    """Redacts `token=<value>` query parameters from uvicorn's log lines.

    The realtime WebSocket authenticates with `?token=<access JWT>` (see
    app/api/v1/realtime.py), and uvicorn logs every WebSocket handshake -
    `"WebSocket /api/v1/ws/events?token=..." [accepted]` - on the
    `uvicorn.error` logger with the full query string. `--no-access-log`
    does not cover those lines, so without this every realtime connection
    writes a live access token into the logs. The value is redacted rather
    than the line dropped: connect/reject events are still useful.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _TOKEN_QUERY_RE.sub(r"\1[REDACTED]", record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(
                _TOKEN_QUERY_RE.sub(r"\1[REDACTED]", arg) if isinstance(arg, str) else arg
                for arg in record.args
            )
        return True


class RequestIDFilter(logging.Filter):
    """Logging filter that injects the current request correlation ID."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


def setup_logging() -> logging.Logger:
    """Configure application-wide structured logging with request correlation."""
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] [%(request_id)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(RequestIDFilter())
    handler.setLevel(log_level)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Avoid duplicate handlers on re-init
    if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
        root_logger.addHandler(handler)
    else:
        root_logger.handlers = [handler]

    # Logger-level filters: uvicorn creates these records on the loggers
    # themselves, so they never pass through a root handler's filters.
    for uvicorn_logger_name in ("uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(uvicorn_logger_name)
        if not any(isinstance(f, RedactTokenQueryFilter) for f in uvicorn_logger.filters):
            uvicorn_logger.addFilter(RedactTokenQueryFilter())

    # Suppress verbose external loggers
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.DEBUG else logging.WARNING
    )

    app_logger = logging.getLogger("gawachabazaar")
    app_logger.setLevel(log_level)
    return app_logger


logger = setup_logging()
