import json
import logging


class JSONFormatter(logging.Formatter):
    """Structured JSON formatter for logs."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
        }
        for key in ("request_id", "route_name", "upstream_ms", "status_code", "method", "path"):
            if hasattr(record, key):
                log_data[key] = getattr(record, key)
        return json.dumps(log_data, ensure_ascii=False)


def configure_logging(level: int = logging.INFO) -> None:
    """Configure root logger with JSON formatter."""
    logger = logging.getLogger()
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(level)
