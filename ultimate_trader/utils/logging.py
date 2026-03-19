import logging
import os
from pathlib import Path
from datetime import datetime


def get_logger(name: str, log_dir: str = "data/logs") -> logging.Logger:
    """
    Create a logger that writes to both console and a daily rotating log file.

    Args:
        name: logger name (usually __name__ of the calling module)
        log_dir: directory to store log files

    Returns:
        Configured logger instance
    """
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    log_file = Path(log_dir) / f"{datetime.now().strftime('%Y-%m-%d')}.log"

    logger = logging.getLogger(name)
    if logger.handlers:  # Avoid duplicate handlers on re-import
        return logger

    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    return logger
