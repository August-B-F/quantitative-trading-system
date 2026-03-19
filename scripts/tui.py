"""iStock - Terminal UI

A rich, animated terminal dashboard for monitoring and controlling the bot.

Tabs:
  [1] Dashboard   - equity curve sparkline, regime badge, key metrics
  [2] Performance - full metrics, daily P&L bar chart, trade history table
  [3] Positions   - live Alpaca positions with unrealized P&L colouring
  [4] Signals     - today's model predictions per symbol with confidence bars
  [5] Bot Control - start/stop bot, run download/train/backtest, live log

Usage:
    python scripts/tui.py
    python scripts/tui.py --config config   # custom config dir

Requires:
    pip install textual plotext
"""
from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Label,
    Log,
    ProgressBar,
    RichLog,
    Static,
    Switch,
    TabbedContent,
    TabPane,
)
from textual.widget import Widget
from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from rich.console import Console
from rich.style import Style
from rich import box

# ---- optional plotext for ASCII charts ----
try:
    import plotext as plt
    HAS_PLOTEXT = True
except ImportError:
    HAS_PLOTEXT = False

# ---- load config + DB lazily ----
try:
    from ultimate_trader.utils.config_loader import load_config
    from ultimate_trader.utils.logging import PerformanceDB
    _CONFIG_AVAILABLE = True
except ImportError:
    _CONFIG_AVAILABLE = False


# ═══════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════

REGIME_STYLE = {
    "bull": "bold green",
    "sideways": "bold yellow",
    "bear": "bold red",
}

CLASS_LABELS = {
    0: ("STRONG SELL", "bold red"),
    1: ("SELL",        "red"),
    2: ("HOLD",        "yellow"),
    3: ("BUY",         "green"),
    4: ("STRONG BUY",  "bold green"),
}

CONF_BAR_WIDTH = 20


def conf_bar(confidence: float, width: int = CONF_BAR_WIDTH) -> Text:
    filled = round(confidence * width)
    bar = "█" * filled + "░" * (width - filled)
    if confidence >= 0.8:
        style = "bold bright_green"
    elif confidence >= 0.65:
        style = "bright_green"
    elif confidence >= 0.5:
        style = "yellow"
    else:
        style = "dim white"
    return Text(f"{bar} {confidence:.0%}", style=style)


def sparkline(values: list[float], width: int = 40) -> str:
    """Render a Unicode sparkline from a list of floats."""
    if not values or len(values) < 2:
        return "─" * width
    blocks = " ▁▂▃▄▅▆▇█"
    mn, mx = min(values), max(values)
    rng = mx - mn or 1.0
    sampled = values[-width:]
    chars = [blocks[round((v - mn) / rng * (len(blocks) - 1))] for v in sampled]
    return "".join(chars)


def pnl_colour(val: float) -> str:
    if val > 0:
        return f"[bold green]+${val:,.2f}[/]"
    elif val < 0:
        return f"[bold red]-${abs(val):,.2f}[/]"
    return f"[white]${val:,.2f}[/]"


def pct_colour(val: float) -> str:
    if val > 0:
        return f"[bold green]+{val:.2%}[/]"
    elif val < 0:
        return f"[bold red]{val:.2%}[/]"
    return f"[white]{val:.2%}[/]"


def load_db_safe(cfg) -> Optional[PerformanceDB]:
    try:
        return PerformanceDB(cfg.paths.db_path)
    except Exception:
        return None


def load_alpaca_positions(cfg):
    """Pull live positions from Alpaca. Returns list of dicts."""
    try:
        from alpaca.trading.client import TradingClient
        client = TradingClient(cfg.alpaca.key_id, cfg.alpaca.secret_key,
                               paper=not cfg.trading.live)
        positions = client.get_all_positions()
        account = client.get_account()
        return positions, account
    except Exception:
        return [], None


def load_equity_series(db) -> list[float]:
    try:
        df = db.get_daily_pnl()
        return df["equity"].tolist() if not df.empty else []
    except Exception:
        return []


def load_backtest_results(output_dir="data/backtest_results") -> dict:
    metrics_path = os.path.join(output_dir, "metrics.json")
    eq_path = os.path.join(output_dir, "equity_curve.csv")
    trades_path = os.path.join(output_dir, "trades.csv")
    result = {}
    if os.path.exists(metrics_path):
        with open(metrics_path) as f:
            result["metrics"] = json.load(f)
    if os.path.exists(eq_path):
        result["equity_curve"] = pd.read_csv(eq_path, index_col=0)
    if os.path.exists(trades_path):
        result["trades"] = pd.read_csv(trades_path)
    return result


def load_predictions(output_dir="data/backtest_results") -> pd.DataFrame:
    path = os.path.join(output_dir, "predictions.csv")
    if os.path.exists(path):
        return pd.read_csv(path)
    return pd.DataFrame()


# ═══════════════════════════════════════════════════════
# Widgets
# ═══════════════════════════════════════════════════════

class MetricCard(Static):
    """A single KPI card: title + big value."""
    DEFAULT_CSS = """
    MetricCard {
        border: tall $accent;
        padding: 0 2;
        width: 1fr;
        height: 7;
        content-align: center middle;
    }
    """

    def __init__(self, title: str, value: str = "—",
                 value_style: str = "bold white", **kwargs):
        super().__init__(**kwargs)
        self._title = title
        self._value = value
        self._value_style = value_style

    def compose(self) -> ComposeResult:
        yield Label(self._title, id="card-title")
        yield Label(self._value, id="card-value")

    def update_value(self, value: str, style: str = None):
        self.query_one("#card-value", Label).update(Text(value, style=style or self._value_style))


class SparklineWidget(Static):
    """ASCII sparkline + plotext chart in a panel."""
    DEFAULT_CSS = """
    SparklineWidget {
        height: 12;
        border: round $accent;
        padding: 0 1;
    }
    """
    values: reactive[list] = reactive([])

    def __init__(self, title: str = "Equity Curve", **kwargs):
        super().__init__(**kwargs)
        self._title = title

    def render(self) -> str:
        vals = self.values
        if not vals:
            return f"[dim]{self._title}\n\nNo data yet — run the bot or a backtest first.[/]"

        if HAS_PLOTEXT:
            plt.clf()
            plt.plot(list(range(len(vals))), vals, color="green")
            plt.plotsize(self.size.width - 4, self.size.height - 3)
            plt.theme("dark")
            plt.xlabel("Days")
            plt.ylabel("Equity")
            plt.title(self._title)
            chart = plt.build()
            return chart

        spark = sparkline(vals, width=self.size.width - 6)
        start = vals[0]
        end = vals[-1]
        change = (end / start - 1) if start else 0
        colour = "green" if change >= 0 else "red"
        return (
            f"[bold]{self._title}[/]\n"
            f"[{colour}]{spark}[/]\n"
            f"  Start: [bold]${start:,.0f}[/]   "
            f"Now: [bold {colour}]${end:,.0f}[/]   "
            f"Change: [{colour}]{change:+.2%}[/]"
        )


class RegimeBadge(Static):
    DEFAULT_CSS = """
    RegimeBadge {
        height: 3;
        width: 20;
        content-align: center middle;
        border: tall $accent;
    }
    """
    regime: reactive[str] = reactive("unknown")

    def render(self) -> Text:
        style = REGIME_STYLE.get(self.regime, "white")
        icon = {"bull": "🐂", "bear": "🐻", "sideways": "↔", "unknown": "?"}.get(self.regime, "?")
        return Text(f"{icon}  {self.regime.upper()}", style=style, justify="center")


class DailyPnLChart(Static):
    """Bar chart of daily P&L using plotext."""
    DEFAULT_CSS = """
    DailyPnLChart {
        height: 14;
        border: round $accent;
        padding: 0 1;
    }
    """
    pnl_data: reactive[list] = reactive([])
    date_labels: reactive[list] = reactive([])

    def render(self) -> str:
        if not self.pnl_data:
            return "[dim]Daily P&L Chart\n\nNo P&L data yet.[/]"

        if HAS_PLOTEXT:
            plt.clf()
            colours = ["green" if v >= 0 else "red" for v in self.pnl_data]
            plt.bar(self.date_labels[-20:] if self.date_labels else
                    list(range(len(self.pnl_data[-20:]))),
                    self.pnl_data[-20:],
                    color=colours[-20:])
            plt.plotsize(self.size.width - 4, self.size.height - 2)
            plt.theme("dark")
            plt.title("Daily P&L (last 20 days)")
            return plt.build()

        lines = ["[bold]Daily P&L[/]"]
        mx = max(abs(v) for v in self.pnl_data[-15:]) or 1
        for i, v in enumerate(self.pnl_data[-15:]):
            bar_len = round(abs(v) / mx * 30)
            bar = "█" * bar_len
            colour = "green" if v >= 0 else "red"
            label = self.date_labels[-(15 - i)] if self.date_labels else str(i)
            lines.append(f"  {label[-5:]} [{colour}]{bar}[/] {pnl_colour(v)}")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════
# Tab: Dashboard
# ═══════════════════════════════════════════════════════

class DashboardTab(Widget):
    DEFAULT_CSS = """
    DashboardTab {
        layout: vertical;
        padding: 1 2;
    }
    #metric-row { height: 9; layout: horizontal; }
    #chart-row  { height: 14; layout: horizontal; }
    #info-row   { height: 6;  layout: horizontal; }
    """

    def __init__(self, cfg, db, **kwargs):
        super().__init__(**kwargs)
        self.cfg = cfg
        self.db = db

    def compose(self) -> ComposeResult:
        with Horizontal(id="metric-row"):
            yield MetricCard("💰 Equity",      "—", id="card-equity")
            yield MetricCard("📈 Total Return", "—", id="card-return")
            yield MetricCard("⚡ Sharpe",      "—", id="card-sharpe")
            yield MetricCard("📉 Max Drawdown", "—", id="card-drawdown")
            yield MetricCard("🎯 Win Rate",    "—", id="card-winrate")
            yield MetricCard("🔢 Trades",      "—", id="card-trades")
        with Horizontal(id="chart-row"):
            yield SparklineWidget("📊 Equity Curve", id="sparkline")
        with Horizontal(id="info-row"):
            yield RegimeBadge(id="regime-badge")
            yield Static(id="last-update", classes="dim")

    def on_mount(self) -> None:
        self.refresh_data()
        self.set_interval(30, self.refresh_data)

    def refresh_data(self) -> None:
        self._load_live_data()

    def _load_live_data(self) -> None:
        bt = load_backtest_results()
        metrics = bt.get("metrics", {})

        eq_vals = []
        if "equity_curve" in bt:
            eq_vals = bt["equity_curve"]["equity"].tolist()
        elif self.db:
            eq_vals = load_equity_series(self.db)

        if eq_vals:
            self.query_one("#sparkline", SparklineWidget).values = eq_vals

        if metrics:
            eq = metrics.get("final_equity", 0)
            ret = metrics.get("total_return", 0)
            sharpe = metrics.get("sharpe", 0)
            dd = metrics.get("max_drawdown", 0)
            wr = metrics.get("win_rate", 0)
            ntrades = metrics.get("n_trades", 0)

            ret_style = "bold green" if ret >= 0 else "bold red"
            dd_style  = "bold red" if dd < -0.1 else "bold yellow"

            self.query_one("#card-equity",   MetricCard).update_value(f"${eq:,.0f}")
            self.query_one("#card-return",   MetricCard).update_value(f"{ret:+.2%}", ret_style)
            self.query_one("#card-sharpe",   MetricCard).update_value(f"{sharpe:.3f}")
            self.query_one("#card-drawdown", MetricCard).update_value(f"{dd:.2%}", dd_style)
            self.query_one("#card-winrate",  MetricCard).update_value(f"{wr:.1%}")
            self.query_one("#card-trades",   MetricCard).update_value(str(ntrades))

        regime = "unknown"
        if self.db:
            try:
                pnl_df = self.db.get_daily_pnl()
                if not pnl_df.empty:
                    regime = pnl_df.iloc[-1].get("regime", "unknown")
            except Exception:
                pass
        self.query_one("#regime-badge", RegimeBadge).regime = regime

        self.query_one("#last-update", Static).update(
            f"[dim]Last refreshed: {datetime.now().strftime('%H:%M:%S')}[/]"
        )


# ═══════════════════════════════════════════════════════
# Tab: Performance
# ═══════════════════════════════════════════════════════

class PerformanceTab(Widget):
    DEFAULT_CSS = """
    PerformanceTab {
        layout: vertical;
        padding: 1 2;
    }
    #perf-top { height: 16; layout: horizontal; }
    #perf-trades { height: 1fr; }
    """

    def __init__(self, db, **kwargs):
        super().__init__(**kwargs)
        self.db = db

    def compose(self) -> ComposeResult:
        with Horizontal(id="perf-top"):
            yield DailyPnLChart(id="pnl-chart")
            yield Static(id="perf-summary", classes="perf-summary")
        with Vertical(id="perf-trades"):
            yield Label("[bold]Trade History[/]")
            yield DataTable(id="trades-table")

    def on_mount(self) -> None:
        self._init_table()
        self.refresh_data()
        self.set_interval(30, self.refresh_data)

    def _init_table(self):
        t = self.query_one("#trades-table", DataTable)
        t.add_columns("Symbol", "Entry", "Exit", "Side", "P&L %", "P&L $", "Reason", "Regime")
        t.cursor_type = "row"
        t.zebra_stripes = True

    def refresh_data(self) -> None:
        bt = load_backtest_results()
        metrics = bt.get("metrics", {})

        if self.db:
            try:
                pnl_df = self.db.get_daily_pnl()
                if not pnl_df.empty:
                    chart = self.query_one("#pnl-chart", DailyPnLChart)
                    chart.pnl_data = pnl_df["pnl"].tolist()
                    chart.date_labels = pnl_df["date"].tolist()
            except Exception:
                pass
        elif "equity_curve" in bt:
            eq = bt["equity_curve"]["equity"]
            pnl = eq.diff().fillna(0).tolist()
            dates = list(bt["equity_curve"].index.astype(str))
            chart = self.query_one("#pnl-chart", DailyPnLChart)
            chart.pnl_data = pnl
            chart.date_labels = dates

        if metrics:
            lines = [
                "[bold underline]Strategy Metrics[/]",
                f"  Return   : {pct_colour(metrics.get('total_return', 0))}",
                f"  Sharpe   : [bold]{metrics.get('sharpe', 0):.3f}[/]",
                f"  Sortino  : [bold]{metrics.get('sortino', 0):.3f}[/]",
                f"  Max DD   : [bold red]{metrics.get('max_drawdown', 0):.2%}[/]",
                f"  Win Rate : [bold]{metrics.get('win_rate', 0):.1%}[/]",
                f"  # Trades : [bold]{metrics.get('n_trades', 0)}[/]",
                f"  Final Eq : [bold]${metrics.get('final_equity', 0):,.2f}[/]",
            ]
            self.query_one("#perf-summary", Static).update("\n".join(lines))

        t = self.query_one("#trades-table", DataTable)
        t.clear()

        trades_df = bt.get("trades", pd.DataFrame())
        if self.db and (trades_df is None or trades_df.empty):
            try:
                trades_df = self.db.get_all_trades()
            except Exception:
                trades_df = pd.DataFrame()

        if trades_df is not None and not trades_df.empty:
            for _, row in trades_df.tail(200).iterrows():
                pnl_pct = float(row.get("pnl_pct", 0))
                pnl_dollar = float(row.get("pnl_dollar", 0))
                pnl_style = "green" if pnl_dollar >= 0 else "red"
                t.add_row(
                    str(row.get("symbol", "")),
                    str(row.get("entry_date", ""))[:10],
                    str(row.get("exit_date",  ""))[:10],
                    str(row.get("side", "buy")),
                    Text(f"{pnl_pct:+.2%}", style=pnl_style),
                    Text(f"${pnl_dollar:+,.2f}", style=pnl_style),
                    str(row.get("exit_reason", "")),
                    str(row.get("regime", "")),
                )


# ═══════════════════════════════════════════════════════
# Tab: Positions
# ═══════════════════════════════════════════════════════

class PositionsTab(Widget):
    DEFAULT_CSS = """
    PositionsTab {
        layout: vertical;
        padding: 1 2;
    }
    #account-row { height: 5; layout: horizontal; }
    """

    def __init__(self, cfg, **kwargs):
        super().__init__(**kwargs)
        self.cfg = cfg

    def compose(self) -> ComposeResult:
        with Horizontal(id="account-row"):
            yield MetricCard("💵 Equity",    "—", id="pos-equity")
            yield MetricCard("💴 Cash",       "—", id="pos-cash")
            yield MetricCard("📊 Exposure",  "—", id="pos-exposure")
            yield MetricCard("🔢 Positions", "—", id="pos-count")
        yield Label("[bold]Open Positions[/]")
        yield DataTable(id="pos-table")
        yield Button("🔄 Refresh", id="btn-refresh-pos", variant="primary")

    def on_mount(self) -> None:
        t = self.query_one("#pos-table", DataTable)
        t.add_columns("Symbol", "Qty", "Avg Entry", "Current", "Mkt Value", "Unreal P&L", "P&L %")
        t.cursor_type = "row"
        t.zebra_stripes = True
        self.refresh_positions()

    @on(Button.Pressed, "#btn-refresh-pos")
    def refresh_positions(self) -> None:
        self._load_positions()

    @work(thread=True)
    def _load_positions(self) -> None:
        positions, account = load_alpaca_positions(self.cfg)
        self.app.call_from_thread(self._update_positions_ui, positions, account)

    def _update_positions_ui(self, positions, account) -> None:
        t = self.query_one("#pos-table", DataTable)
        t.clear()

        if account:
            equity = float(account.equity)
            cash = float(account.cash)
            invested = sum(float(p.market_value) for p in positions)
            exposure = invested / max(equity, 1)

            self.query_one("#pos-equity",  MetricCard).update_value(f"${equity:,.2f}")
            self.query_one("#pos-cash",    MetricCard).update_value(f"${cash:,.2f}")
            self.query_one("#pos-exposure",MetricCard).update_value(f"{exposure:.1%}")
            self.query_one("#pos-count",   MetricCard).update_value(str(len(positions)))

        for pos in positions:
            qty = float(pos.qty)
            avg = float(pos.avg_entry_price)
            cur = float(pos.current_price)
            mv = float(pos.market_value)
            upnl = float(pos.unrealized_pl)
            pct = (cur - avg) / avg if avg else 0
            style = "green" if upnl >= 0 else "red"
            t.add_row(
                pos.symbol,
                f"{qty:.2f}",
                f"${avg:.2f}",
                f"${cur:.2f}",
                f"${mv:,.2f}",
                Text(f"${upnl:+,.2f}", style=style),
                Text(f"{pct:+.2%}", style=style),
            )


# ═══════════════════════════════════════════════════════
# Tab: Signals
# ═══════════════════════════════════════════════════════

class SignalsTab(Widget):
    DEFAULT_CSS = """
    SignalsTab {
        layout: vertical;
        padding: 1 2;
    }
    #signals-filter { height: 3; layout: horizontal; }
    """

    def compose(self) -> ComposeResult:
        with Horizontal(id="signals-filter"):
            yield Button("All",        id="btn-all",   variant="primary")
            yield Button("Buys only",  id="btn-buys",  variant="success")
            yield Button("Sells only", id="btn-sells", variant="error")
            yield Button("🔄 Reload",  id="btn-reload-signals")
        yield DataTable(id="signals-table")

    def on_mount(self) -> None:
        t = self.query_one("#signals-table", DataTable)
        t.add_columns("Symbol", "Signal", "Confidence", "Uncertainty", "Date")
        t.cursor_type = "row"
        t.zebra_stripes = True
        self._load_signals(filter_mode="all")

    @on(Button.Pressed, "#btn-all")
    def show_all(self): self._load_signals("all")

    @on(Button.Pressed, "#btn-buys")
    def show_buys(self): self._load_signals("buys")

    @on(Button.Pressed, "#btn-sells")
    def show_sells(self): self._load_signals("sells")

    @on(Button.Pressed, "#btn-reload-signals")
    def reload_signals(self): self._load_signals("all")

    def _load_signals(self, filter_mode: str = "all") -> None:
        df = load_predictions()
        t = self.query_one("#signals-table", DataTable)
        t.clear()

        if df.empty:
            t.add_row("[dim]No predictions found[/]", "", "", "", "")
            return

        latest_date = df["date"].max()
        df = df[df["date"] == latest_date].sort_values("confidence", ascending=False)

        if filter_mode == "buys":
            df = df[df["pred_class"].isin([3, 4])]
        elif filter_mode == "sells":
            df = df[df["pred_class"].isin([0, 1])]

        for _, row in df.iterrows():
            pc = int(row["pred_class"])
            label, sig_style = CLASS_LABELS.get(pc, ("HOLD", "yellow"))
            conf = float(row["confidence"])
            unc = float(row.get("uncertainty", 0))
            unc_style = "red" if unc > 0.7 else ("yellow" if unc > 0.4 else "green")
            t.add_row(
                row["symbol"],
                Text(label, style=sig_style),
                conf_bar(conf),
                Text(f"{unc:.2f}", style=unc_style),
                str(row["date"])[:10],
            )


# ═══════════════════════════════════════════════════════
# Tab: Bot Control
# ═══════════════════════════════════════════════════════

class ControlTab(Widget):
    DEFAULT_CSS = """
    ControlTab {
        layout: vertical;
        padding: 1 2;
    }
    #ctrl-buttons { height: 5; layout: horizontal; }
    #ctrl-log { height: 1fr; border: round $accent; }
    """

    _bot_process: Optional[subprocess.Popen] = None

    def __init__(self, cfg, **kwargs):
        super().__init__(**kwargs)
        self.cfg = cfg
        self._scripts_dir = str(Path(__file__).parent)

    def compose(self) -> ComposeResult:
        with Horizontal(id="ctrl-buttons"):
            yield Button("▶  Download Data", id="btn-download", variant="default")
            yield Button("🧠 Train Model",   id="btn-train",    variant="primary")
            yield Button("📊 Run Backtest",  id="btn-backtest",  variant="default")
            yield Button("🚀 Start Bot",     id="btn-start",    variant="success")
            yield Button("⏹  Stop Bot",      id="btn-stop",     variant="error")
        yield Label("[bold]Live Log[/]")
        yield RichLog(id="ctrl-log", highlight=True, markup=True, max_lines=500)

    def on_mount(self) -> None:
        self._log("[dim]iStock ready. Use the buttons above to run pipeline steps.[/]")
        self._log(f"[dim]Scripts dir: {self._scripts_dir}[/]")

    def _log(self, msg: str) -> None:
        log_widget = self.query_one("#ctrl-log", RichLog)
        ts = datetime.now().strftime("%H:%M:%S")
        log_widget.write(f"[dim]{ts}[/]  {msg}")

    def _run_script(self, script: str, extra_args: list[str] = None) -> None:
        script_path = os.path.join(self._scripts_dir, script)
        cmd = [sys.executable, script_path] + (extra_args or [])
        self._log(f"[bold yellow]Running:[/] {' '.join(cmd)}")
        self._stream_process(cmd)

    @work(thread=True)
    def _stream_process(self, cmd: list[str]) -> None:
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            self._bot_process = proc
            for line in iter(proc.stdout.readline, ""):
                line = line.rstrip()
                if line:
                    if "ERROR" in line or "error" in line.lower():
                        self.app.call_from_thread(self._log, f"[red]{line}[/]")
                    elif "WARNING" in line or "warning" in line.lower():
                        self.app.call_from_thread(self._log, f"[yellow]{line}[/]")
                    elif any(k in line for k in ["complete", "done", "saved", "loaded"]):
                        self.app.call_from_thread(self._log, f"[green]{line}[/]")
                    else:
                        self.app.call_from_thread(self._log, line)
            proc.wait()
            code = proc.returncode
            if code == 0:
                self.app.call_from_thread(self._log, f"[bold green]✓ Process finished (exit 0)[/]")
            else:
                self.app.call_from_thread(self._log, f"[bold red]✗ Process exited with code {code}[/]")
            self._bot_process = None
        except Exception as e:
            self.app.call_from_thread(self._log, f"[bold red]Failed to run process: {e}[/]")

    @on(Button.Pressed, "#btn-download")
    def run_download(self) -> None:
        self._log("[bold]Starting data download...[/]")
        self._run_script("download_data.py")

    @on(Button.Pressed, "#btn-train")
    def run_train(self) -> None:
        self._log("[bold]Starting model training...[/]")
        self._run_script("train.py")

    @on(Button.Pressed, "#btn-backtest")
    def run_backtest(self) -> None:
        self._log("[bold]Starting backtest...[/]")
        self._run_script("backtest.py")

    @on(Button.Pressed, "#btn-start")
    def start_bot(self) -> None:
        if self._bot_process and self._bot_process.poll() is None:
            self._log("[yellow]Bot is already running.[/]")
            return
        self._log("[bold green]Starting bot (paper mode)...[/]")
        self._run_script("run_live_bot.py", ["--now"])

    @on(Button.Pressed, "#btn-stop")
    def stop_bot(self) -> None:
        if self._bot_process and self._bot_process.poll() is None:
            self._bot_process.terminate()
            self._log("[bold red]Bot process terminated.[/]")
        else:
            self._log("[dim]No running bot process to stop.[/]")


# ═══════════════════════════════════════════════════════
# Main App
# ═══════════════════════════════════════════════════════

APP_CSS = """
Screen {
    background: $surface;
}
Header {
    background: #0f2744;
    color: #00d4ff;
}
Footer {
    background: #0f2744;
}
TabbedContent {
    height: 1fr;
}
TabPane {
    padding: 0;
}
.perf-summary {
    width: 35;
    padding: 1 2;
    border: round $accent;
    height: 14;
}
MetricCard #card-title {
    color: $text-muted;
    text-style: italic;
    content-align: center middle;
}
MetricCard #card-value {
    text-style: bold;
    content-align: center middle;
    font-size: 2;
}
Button {
    margin: 0 1;
}
#ctrl-buttons {
    padding: 1 0;
}
RegimeBadge {
    margin: 0 2;
}
#last-update {
    content-align: left middle;
    padding: 0 2;
}
"""


class TradingTUI(App):
    """iStock - Terminal UI"""

    TITLE = "iStock"
    CSS = APP_CSS
    BINDINGS = [
        Binding("1", "switch_tab('dashboard')",  "Dashboard",   show=True),
        Binding("2", "switch_tab('performance')", "Performance", show=True),
        Binding("3", "switch_tab('positions')",   "Positions",   show=True),
        Binding("4", "switch_tab('signals')",     "Signals",     show=True),
        Binding("5", "switch_tab('control')",     "Control",     show=True),
        Binding("r", "refresh_all",               "Refresh",     show=True),
        Binding("q", "quit",                      "Quit",        show=True),
        Binding("ctrl+c", "quit",                 "Quit",        show=False),
    ]

    def __init__(self, config_dir: str = "config", **kwargs):
        super().__init__(**kwargs)
        self._config_dir = config_dir
        self.cfg = None
        self.db = None

        if _CONFIG_AVAILABLE:
            try:
                self.cfg = load_config(config_dir)
                self.db = load_db_safe(self.cfg)
            except Exception:
                pass

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(initial="dashboard", id="tabs"):
            with TabPane("📊 Dashboard",   id="dashboard"):
                if self.cfg:
                    yield DashboardTab(self.cfg, self.db)
                else:
                    yield Static("[red]Could not load config. Check config/config.yaml[/]")
            with TabPane("📈 Performance", id="performance"):
                yield PerformanceTab(self.db)
            with TabPane("💼 Positions",   id="positions"):
                if self.cfg:
                    yield PositionsTab(self.cfg)
                else:
                    yield Static("[red]Config not loaded.[/]")
            with TabPane("🎯 Signals",     id="signals"):
                yield SignalsTab()
            with TabPane("⚙️  Control",     id="control"):
                if self.cfg:
                    yield ControlTab(self.cfg)
                else:
                    yield Static("[red]Config not loaded.[/]")
        yield Footer()

    def action_switch_tab(self, tab_id: str) -> None:
        self.query_one("#tabs", TabbedContent).active = tab_id

    def action_refresh_all(self) -> None:
        for widget in self.query(DashboardTab):
            widget.refresh_data()
        for widget in self.query(PerformanceTab):
            widget.refresh_data()
        for widget in self.query(SignalsTab):
            widget._load_signals("all")


# ═══════════════════════════════════════════════════════
# Entry
# ═══════════════════════════════════════════════════════

def main():
    p = argparse.ArgumentParser(description="iStock Terminal UI")
    p.add_argument("--config", default="config", help="Config directory")
    args = p.parse_args()

    try:
        import textual
    except ImportError:
        print("ERROR: textual is not installed.")
        print("Install it with:  pip install textual plotext")
        sys.exit(1)

    app = TradingTUI(config_dir=args.config)
    app.run()


if __name__ == "__main__":
    main()
