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
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "route_name"):
            log_data["route_name"] = record.route_name
        if hasattr(record, "upstream_ms"):
            log_data["upstream_ms"] = record.upstream_ms
        if hasattr(record, "status_code"):
            log_data["status_code"] = record.status_code
        return json.dumps(log_data, ensure_ascii=False)


def configure_logging(level: int = logging.INFO) -> None:
    """Configure root logger with JSON formatter."""
    logger = logging.getLogger()
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(level)
