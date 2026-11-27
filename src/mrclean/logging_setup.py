"""Logging with personal data redacted before any handler sees it.

Every record passes through :class:`RedactingFilter`, which replaces
email addresses, phone numbers and any literal values registered at runtime
(e.g. the identity being scanned) with ``[REDACTED]``. The filter is attached
to handlers, so third-party library logs are covered too.
"""

from __future__ import annotations

import logging
import logging.handlers
import re
import threading
from collections.abc import Iterable
from pathlib import Path

REDACTED = "[REDACTED]"

_PATTERNS = (
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    re.compile(r"(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}"),
)


class RedactingFilter(logging.Filter):
    """Scrub PII from the fully formatted message and from exception text."""

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self._literals: tuple[re.Pattern[str], ...] = ()

    def add_literals(self, values: Iterable[str]) -> None:
        """Register exact strings (case-insensitive) to redact, e.g. a person's name."""
        new = tuple(re.compile(re.escape(v), re.IGNORECASE) for v in values if v.strip())
        with self._lock:
            # Longest first so "Jane Q Public" is redacted before "Jane".
            self._literals = tuple(
                sorted((*self._literals, *new), key=lambda p: len(p.pattern), reverse=True)
            )

    def redact(self, text: str) -> str:
        for pattern in (*self._literals, *_PATTERNS):
            text = pattern.sub(REDACTED, text)
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self.redact(record.getMessage())
        record.args = None
        if record.exc_info:
            formatted = logging.Formatter().formatException(record.exc_info)
            record.exc_text = self.redact(formatted)
            record.exc_info = None
        return True


redactor = RedactingFilter()


def configure_logging(level: int = logging.INFO, log_dir: Path | None = None) -> None:
    """Configure root logging: redacted console output plus an optional rotating file."""
    fmt = logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        handlers.append(
            logging.handlers.RotatingFileHandler(
                log_dir / "mrclean.log", maxBytes=1_000_000, backupCount=5, encoding="utf-8"
            )
        )
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    for handler in handlers:
        handler.setFormatter(fmt)
        handler.addFilter(redactor)
        root.addHandler(handler)
