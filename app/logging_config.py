import logging
import logging.handlers
import os
from pathlib import Path


def configure_logging() -> None:
    root = logging.getLogger()
    if getattr(root, "_gridwise_configured", False):
        return

    level_name = os.getenv("GRIDWISE_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    log_dir = Path(os.getenv("GRIDWISE_LOG_DIR", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    console = logging.StreamHandler()
    console.setFormatter(formatter)

    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "gridwise.log",
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    root.setLevel(level)
    root.addHandler(console)
    root.addHandler(file_handler)
    root._gridwise_configured = True