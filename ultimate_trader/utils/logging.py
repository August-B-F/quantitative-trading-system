import sys
from pathlib import Path
from loguru import logger

_configured = False


def setup_logging(log_dir: str = "data/logs", level: str = "INFO") -> None:
    global _configured
    if _configured:
        return

    Path(log_dir).mkdir(parents=True, exist_ok=True)

    logger.remove()
    # Console — clean, coloured
    logger.add(sys.stdout, level=level, colorize=True,
               format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                      "<level>{level: <8}</level> | "
                      "<cyan>{name}</cyan>:<cyan>{function}</cyan> — <level>{message}</level>")
    # Rolling file — full detail
    logger.add(Path(log_dir) / "trader_{time:YYYY-MM-DD}.log",
               level="DEBUG",
               rotation="1 day",
               retention="30 days",
               compression="gz",
               format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} — {message}")

    # Separate transaction log
    logger.add(Path(log_dir) / "transactions_{time:YYYY-MM-DD}.log",
               level="INFO",
               filter=lambda r: "TRADE" in r["extra"],
               rotation="1 day",
               retention="90 days")

    _configured = True


def get_logger(name: str = ""):
    setup_logging()
    return logger.bind(module=name)


def log_trade(msg: str) -> None:
    setup_logging()
    logger.bind(TRADE=True).info(msg)
