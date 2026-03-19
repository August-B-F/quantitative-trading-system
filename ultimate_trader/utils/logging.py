import logging
import os
import datetime
from pathlib import Path


def get_logger(name: str, log_dir: str = "data/logs") -> logging.Logger:
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    date_str = datetime.date.today().isoformat()
    log_file = os.path.join(log_dir, f"{date_str}.log")

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.DEBUG)

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    fh.setFormatter(fmt)
    ch.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger
