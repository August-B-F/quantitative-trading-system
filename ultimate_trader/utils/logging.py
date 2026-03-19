import logging
import sqlite3
import os
from datetime import datetime


def get_logger(name: str, log_dir: str = "data/logs") -> logging.Logger:
    """
    Returns a logger that writes to both stdout and a rotating daily log file.
    """
    os.makedirs(log_dir, exist_ok=True)
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # already configured

    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s")

    # console
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # file
    log_file = os.path.join(log_dir, f"{datetime.now().strftime('%Y-%m-%d')}.log")
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger


class PerformanceDB:
    """
    SQLite-backed performance tracker.
    Stores every trade, daily P&L, and model evaluation scores.
    """

    def __init__(self, db_path: str = "data/performance.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._create_tables()

    def _create_tables(self):
        cur = self.conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS trades (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ts          TEXT NOT NULL,
                symbol      TEXT NOT NULL,
                side        TEXT NOT NULL,
                qty         REAL NOT NULL,
                price       REAL NOT NULL,
                confidence  REAL,
                uncertainty REAL,
                regime      TEXT,
                reason      TEXT
            );

            CREATE TABLE IF NOT EXISTS daily_pnl (
                date            TEXT PRIMARY KEY,
                portfolio_value REAL,
                cash            REAL,
                gross_return    REAL,
                benchmark_return REAL,
                sharpe_30d      REAL,
                max_drawdown    REAL
            );

            CREATE TABLE IF NOT EXISTS model_evals (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ts          TEXT NOT NULL,
                model_name  TEXT NOT NULL,
                window_start TEXT,
                window_end   TEXT,
                val_sharpe  REAL,
                val_return  REAL,
                val_drawdown REAL,
                promoted    INTEGER DEFAULT 0
            );
        """)
        self.conn.commit()

    def log_trade(self, symbol: str, side: str, qty: float, price: float,
                  confidence: float = None, uncertainty: float = None,
                  regime: str = None, reason: str = None):
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO trades (ts, symbol, side, qty, price, confidence, uncertainty, regime, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (datetime.utcnow().isoformat(), symbol, side, qty, price,
               confidence, uncertainty, regime, reason))
        self.conn.commit()

    def log_daily_pnl(self, date: str, portfolio_value: float, cash: float,
                      gross_return: float, benchmark_return: float,
                      sharpe_30d: float = None, max_drawdown: float = None):
        cur = self.conn.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO daily_pnl
            (date, portfolio_value, cash, gross_return, benchmark_return, sharpe_30d, max_drawdown)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (date, portfolio_value, cash, gross_return, benchmark_return, sharpe_30d, max_drawdown))
        self.conn.commit()

    def log_model_eval(self, model_name: str, window_start: str, window_end: str,
                       val_sharpe: float, val_return: float, val_drawdown: float,
                       promoted: bool = False):
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO model_evals
            (ts, model_name, window_start, window_end, val_sharpe, val_return, val_drawdown, promoted)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (datetime.utcnow().isoformat(), model_name, window_start, window_end,
               val_sharpe, val_return, val_drawdown, int(promoted)))
        self.conn.commit()

    def get_recent_trades(self, n: int = 50):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM trades ORDER BY ts DESC LIMIT ?", (n,))
        return cur.fetchall()

    def close(self):
        self.conn.close()
