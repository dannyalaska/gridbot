import logging
from collections import deque
from typing import Deque, List


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

