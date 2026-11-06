import json
import logging


class EventFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "level": record.levelname,
                "event": record.getMessage(),
                "failure_type": getattr(record, "failure_type", None),
            }
        )


def configure(level: str) -> None:
    logger = logging.getLogger("sentinel")
    handler = logging.StreamHandler()
    handler.setFormatter(EventFormatter())
    logger.handlers = [handler]
    logger.setLevel(level)
    logger.propagate = False
    # HTTP libraries can include endpoint URLs in their diagnostic logs.
    for name in ("httpx", "httpcore", "sqlalchemy.engine"):
        logging.getLogger(name).setLevel(logging.WARNING)
