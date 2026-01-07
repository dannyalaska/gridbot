import logging
from collections import deque
from pathlib import Path
from typing import Deque, List, Optional


class InMemoryLogHandler(logging.Handler):
    """
    Capture recent log messages for display in the dashboard.
    """

    def __init__(self, capacity: int = 200):
        super().__init__()
        self.capacity = capacity
        self.records: Deque[str] = deque(maxlen=capacity)

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        self.records.append(msg)

    def get_logs(self) -> List[str]:
        return list(self.records)


class ContextFilter(logging.Filter):
    def __init__(self, mode: str, symbol: str):
        super().__init__()
        self.mode = mode
        self.symbol = symbol

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "mode"):
            record.mode = self.mode
        if not hasattr(record, "symbol"):
            record.symbol = self.symbol
        if not hasattr(record, "tick"):
            record.tick = "-"
        if not hasattr(record, "action"):
            record.action = "-"
        return True


def configure_logging(
    log_level: str,
    mode: str,
    symbol: str,
    log_path: str = "logs/gridbot.log",
    in_memory_handler: Optional[logging.Handler] = None,
) -> None:
    logger = logging.getLogger()
    level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] mode=%(mode)s symbol=%(symbol)s tick=%(tick)s action=%(action)s %(message)s"
    )

    if not getattr(logger, "_cryptocosmo_configured", False):
        handlers: List[logging.Handler] = []
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        handlers.append(stream_handler)

        if log_path:
            path = Path(log_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(path, encoding="utf-8")
            file_handler.setFormatter(formatter)
            handlers.append(file_handler)

        for handler in handlers:
            handler.addFilter(ContextFilter(mode=mode, symbol=symbol))
            logger.addHandler(handler)

        logger._cryptocosmo_configured = True
    else:
        for handler in logger.handlers:
            for log_filter in handler.filters:
                if isinstance(log_filter, ContextFilter):
                    log_filter.mode = mode
                    log_filter.symbol = symbol

    if in_memory_handler and not any(isinstance(h, InMemoryLogHandler) for h in logger.handlers):
        in_memory_handler.setFormatter(formatter)
        in_memory_handler.addFilter(ContextFilter(mode=mode, symbol=symbol))
        logger.addHandler(in_memory_handler)
