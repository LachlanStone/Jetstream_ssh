from __future__ import annotations

import logging
import os
from typing import Optional

DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOGGING_ENV_VAR = "JETSTREAM_LOGGING"


def get_logger(
    name: str = "netmiko",
    level: int = logging.DEBUG,
    handler_level: int = logging.INFO,
    enabled: Optional[bool] = None,
    fmt: str = DEFAULT_FORMAT,
) -> logging.Logger:
    """Return an idempotently configured logger for JetStream modules.

    Args:
        name: Logger name (defaults to 'netmiko' to capture transport traces).
        level: Base logger severity threshold.
        handler_level: StreamHandler severity threshold.
        enabled: Explicit toggle. If None, checks JETSTREAM_LOGGING env var (defaults to True).
        fmt: Log format string.
    """
    logger = logging.getLogger(name=name)
    logger.setLevel(level=level)
    logger.propagate = False

    if enabled is None:
        raw = os.environ.get(LOGGING_ENV_VAR, "").strip().lower()
        enabled = raw not in ("0", "false", "no", "off") if raw else True

    if enabled and not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(level=handler_level)
        handler.setFormatter(fmt=logging.Formatter(fmt=fmt))
        logger.addHandler(hdlr=handler)

    return logger


# Shared default instance ready for import
logger = get_logger()
