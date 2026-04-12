import logging
import sqlite3
import os
from datetime import datetime


def get_logger(name: str, log_dir: str = "logs") -> logging.Logger:
    """
    Returns a logger that writes to both stdout and a daily rotating log file.
    Each module should call get_logger(__name__).
    """
    os.makedirs(log_dir, exist_ok=True)
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # File handler – one file per day
    date_str = datetime.now().strftime("%Y-%m-%d")
    fh = logging.FileHandler(os.path.join(log_dir, f"{date_str}.log"))
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger


class PerformanceDB:
    """
    SQLite-backed store for trade history and daily P&L.
    Lets you query Sharpe, drawdown, win rate, etc. at any time.
    """

    def __init__(self, db_path: str = "data/performance.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_tables()

    def _init_tables(self):
        c = self.conn.cursor()
        c.executescript("""
            CREATE TABLE IF NOT EXISTS trades (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ts          TEXT,
                symbol      TEXT,
                side        TEXT,
                qty         REAL,
                price       REAL,
                confidence  REAL,
                regime      TEXT,
                stop_loss   REAL,
                take_profit REAL
            );
            CREATE TABLE IF NOT EXISTS daily_pnl (
                date        TEXT PRIMARY KEY,
                equity      REAL,
                cash        REAL,
                pnl         REAL,
                num_trades  INTEGER,
                regime      TEXT
            );
            CREATE TABLE IF NOT EXISTS predictions (
                ts          TEXT,
                symbol      TEXT,
                pred_class  INTEGER,
                confidence  REAL,
                uncertainty REAL,
                regime      TEXT
            );
        """)
        self.conn.commit()

    def log_trade(self, symbol, side, qty, price, confidence, regime, stop_loss, take_profit):
        self.conn.execute(
            "INSERT INTO trades (ts,symbol,side,qty,price,confidence,regime,stop_loss,take_profit) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (datetime.now().isoformat(), symbol, side, qty, price, confidence, regime, stop_loss, take_profit)
        )
        self.conn.commit()

    def log_daily(self, date, equity, cash, pnl, num_trades, regime):
        self.conn.execute(
            "INSERT OR REPLACE INTO daily_pnl (date,equity,cash,pnl,num_trades,regime) VALUES (?,?,?,?,?,?)",
            (date, equity, cash, pnl, num_trades, regime)
        )
        self.conn.commit()

    def log_prediction(self, symbol, pred_class, confidence, uncertainty, regime):
        self.conn.execute(
            "INSERT INTO predictions (ts,symbol,pred_class,confidence,uncertainty,regime) VALUES (?,?,?,?,?,?)",
            (datetime.now().isoformat(), symbol, pred_class, confidence, uncertainty, regime)
        )
        self.conn.commit()

    def get_all_trades(self):
        import pandas as pd
        return pd.read_sql("SELECT * FROM trades ORDER BY ts", self.conn)

    def get_daily_pnl(self):
        import pandas as pd
        return pd.read_sql("SELECT * FROM daily_pnl ORDER BY date", self.conn)
