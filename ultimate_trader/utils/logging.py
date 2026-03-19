"""Structured logging with Rich console output and rotating file logs."""
import logging
import sqlite3
from pathlib import Path
from datetime import datetime
from rich.logging import RichHandler
from rich.console import Console

console = Console()


def get_logger(name: str, log_dir: str = "data/logs") -> logging.Logger:
    """
    Returns a logger that writes to:
      - Rich formatted console output
      - Rotating daily log file in log_dir
    """
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    log_file = Path(log_dir) / f"{datetime.now().strftime('%Y-%m-%d')}.log"

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # file handler
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))

    # rich console handler
    rh = RichHandler(console=console, rich_tracebacks=True, show_path=False)
    rh.setLevel(logging.INFO)

    logger.addHandler(fh)
    logger.addHandler(rh)
    return logger


class PerformanceDB:
    """
    SQLite database for tracking trades, daily equity, and metrics.
    Tables:
        trades      - every buy/sell order placed
        equity      - daily portfolio equity snapshots
        predictions - model predictions per symbol per day
    """

    def __init__(self, db_path: str = "data/performance.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._create_tables()

    def _create_tables(self):
        c = self.conn.cursor()
        c.executescript("""
        CREATE TABLE IF NOT EXISTS trades (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            symbol      TEXT NOT NULL,
            side        TEXT NOT NULL,
            qty         REAL NOT NULL,
            price       REAL NOT NULL,
            reason      TEXT,
            confidence  REAL,
            regime      TEXT
        );

        CREATE TABLE IF NOT EXISTS equity (
            date        TEXT PRIMARY KEY,
            equity      REAL NOT NULL,
            cash        REAL NOT NULL,
            positions   INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS predictions (
            timestamp   TEXT NOT NULL,
            symbol      TEXT NOT NULL,
            action      TEXT NOT NULL,
            confidence  REAL NOT NULL,
            uncertainty REAL NOT NULL,
            regime      TEXT,
            PRIMARY KEY (timestamp, symbol)
        );
        """)
        self.conn.commit()

    def log_trade(self, symbol: str, side: str, qty: float, price: float,
                  reason: str = "", confidence: float = 0.0, regime: str = ""):
        self.conn.execute(
            "INSERT INTO trades (timestamp,symbol,side,qty,price,reason,confidence,regime) VALUES (?,?,?,?,?,?,?,?)",
            (datetime.utcnow().isoformat(), symbol, side, qty, price, reason, confidence, regime)
        )
        self.conn.commit()

    def log_equity(self, equity: float, cash: float, positions: int):
        self.conn.execute(
            "INSERT OR REPLACE INTO equity (date,equity,cash,positions) VALUES (?,?,?,?)",
            (datetime.utcnow().date().isoformat(), equity, cash, positions)
        )
        self.conn.commit()

    def log_prediction(self, symbol: str, action: str, confidence: float,
                       uncertainty: float, regime: str = ""):
        self.conn.execute(
            "INSERT OR REPLACE INTO predictions (timestamp,symbol,action,confidence,uncertainty,regime) VALUES (?,?,?,?,?,?)",
            (datetime.utcnow().isoformat(), symbol, action, confidence, uncertainty, regime)
        )
        self.conn.commit()

    def get_equity_curve(self):
        """Returns list of (date, equity) tuples."""
        rows = self.conn.execute("SELECT date, equity FROM equity ORDER BY date").fetchall()
        return rows
