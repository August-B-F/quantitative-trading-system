"""QTS Terminal UI — presentation layer for the ETF Momentum Rotation strategy.

Read-only viewer. Reads results/backtest_presentation.json (single source
of truth) and configs/holdings.json. Does NOT re-run the backtest in-process.

Tabs: 📊 Overview · 📈 Performance · 💼 Holdings · 🎯 Backtest · ⚙ Control.

Usage:
    py scripts/tui.py              # local TTY
    py scripts/tui.py --serve      # textual-serve on 0.0.0.0:8765
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from rich.table import Table
from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Label,
    LoadingIndicator,
    RichLog,
    Static,
    TabbedContent,
    TabPane,
)

try:
    import plotext as plt
    HAS_PLOTEXT = True
except ImportError:
    HAS_PLOTEXT = False


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PRES_PATH = PROJECT_ROOT / "results" / "backtest_presentation.json"
HOLDINGS_PATH = PROJECT_ROOT / "configs" / "holdings.json"
DEFAULT_PORT = 8765


# ═══════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════

REGIME_STYLE = {
    "Hi-Growth/Lo-Inf":  "bold green",
    "Hi-Growth/Hi-Inf":  "bold yellow",
    "Lo-Growth/Lo-Inf":  "bold cyan",
    "Lo-Growth/Hi-Inf":  "bold red",
}
REGIME_ICON = {
    "Hi-Growth/Lo-Inf":  "🐂",
    "Hi-Growth/Hi-Inf":  "🔥",
    "Lo-Growth/Lo-Inf":  "❄",
    "Lo-Growth/Hi-Inf":  "🐻",
}

SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


def _clean(x: Any) -> float | None:
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def fmt_pct(v: Any, plus: bool = False) -> str:
    f = _clean(v)
    if f is None:
        return "—"
    return f"{f:+.2%}" if plus else f"{f:.2%}"


def fmt_num(v: Any, digits: int = 2) -> str:
    f = _clean(v)
    return "—" if f is None else f"{f:.{digits}f}"


def pct_colour(val: Any, plus: bool = True) -> str:
    f = _clean(val)
    if f is None:
        return "[dim]—[/]"
    s = f"{f:+.2%}" if plus else f"{f:.2%}"
    if f > 0:
        return f"[bold green]{s}[/]"
    if f < 0:
        return f"[bold red]{s}[/]"
    return f"[white]{s}[/]"


def colour_text(val: Any, plus: bool = True) -> Text:
    f = _clean(val)
    if f is None:
        return Text("—", style="dim")
    style = "bold green" if f > 0 else ("bold red" if f < 0 else "white")
    s = f"{f:+.2%}" if plus else f"{f:.2%}"
    return Text(s, style=style)


def sparkline(values: list[float], width: int = 48) -> str:
    clean = [v for v in values if _clean(v) is not None]
    if len(clean) < 2:
        return "─" * width
    blocks = " ▁▂▃▄▅▆▇█"
    sampled = clean[-width:] if len(clean) > width else clean
    mn, mx = min(sampled), max(sampled)
    rng = (mx - mn) or 1.0
    return "".join(blocks[round((v - mn) / rng * (len(blocks) - 1))] for v in sampled)


# ═══════════════════════════════════════════════════════
# Data
# ═══════════════════════════════════════════════════════

@dataclass
class Snapshot:
    presentation: dict
    holdings: dict
    pres_mtime: float
    holdings_mtime: float
    loaded_at: datetime


def load_snapshot() -> Snapshot:
    with open(PRES_PATH, "r", encoding="utf-8") as f:
        pres = json.load(f)
    holdings: dict = {}
    h_mtime = 0.0
    if HOLDINGS_PATH.exists():
        with open(HOLDINGS_PATH, "r", encoding="utf-8") as f:
            holdings = json.load(f)
        h_mtime = HOLDINGS_PATH.stat().st_mtime
    return Snapshot(
        presentation=pres,
        holdings=holdings,
        pres_mtime=PRES_PATH.stat().st_mtime,
        holdings_mtime=h_mtime,
        loaded_at=datetime.now(),
    )


# ═══════════════════════════════════════════════════════
# Widgets
# ═══════════════════════════════════════════════════════

class MetricCard(Static):
    """KPI card: italic title + big bold value, bordered."""
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
        yield Label(Text(self._value, style=self._value_style), id="card-value")

    def update_value(self, value: str, style: Optional[str] = None) -> None:
        self.query_one("#card-value", Label).update(
            Text(value, style=style or self._value_style)
        )


class RegimeBadge(Static):
    DEFAULT_CSS = """
    RegimeBadge {
        height: 5;
        width: 32;
        content-align: center middle;
        border: tall $accent;
        padding: 0 1;
    }
    """
    regime: reactive[str] = reactive("?")

    def render(self) -> Text:
        style = REGIME_STYLE.get(self.regime, "dim white")
        icon = REGIME_ICON.get(self.regime, "?")
        return Text(f"{icon}  {self.regime}", style=style, justify="center")


class PulsingDot(Static):
    DEFAULT_CSS = """
    PulsingDot { width: 3; height: 1; content-align: center middle; }
    """
    _frame: reactive[int] = reactive(0)

    def on_mount(self) -> None:
        self.set_interval(0.15, self._tick)

    def _tick(self) -> None:
        self._frame = (self._frame + 1) % len(SPINNER_FRAMES)
        self.refresh()

    def render(self) -> Text:
        return Text(SPINNER_FRAMES[self._frame], style="bold cyan")


class EquityChart(Static):
    """Plotext line chart of the strategy equity curve vs SPY."""
    DEFAULT_CSS = """
    EquityChart {
        height: 18;
        border: round $accent;
        padding: 0 1;
    }
    """
    series: reactive[dict] = reactive({})

    def render(self) -> str:
        s = self.series
        if not s:
            return "[dim]Equity Curve\n\nNo data.[/]"
        strat = [_clean(p.get("value")) for p in s.get("strategy", [])]
        spy = [_clean(p.get("value")) for p in s.get("spy", [])]
        strat = [v for v in strat if v is not None]
        spy = [v for v in spy if v is not None]
        if len(strat) < 2:
            return "[dim]Equity Curve\n\nNo data.[/]"

        if HAS_PLOTEXT:
            plt.clf()
            plt.plot(list(range(len(strat))), strat,
                     color="green", label="Strategy")
            if spy and len(spy) == len(strat):
                plt.plot(list(range(len(spy))), spy,
                         color="cyan", label="SPY")
            w = max(self.size.width - 4, 40)
            h = max(self.size.height - 3, 8)
            plt.plotsize(w, h)
            plt.theme("dark")
            plt.title("📊 Equity Curve  (strategy vs SPY)")
            return plt.build()

        spark = sparkline(strat, width=70)
        return (f"[bold]📊 Equity Curve[/]\n[green]{spark}[/]\n"
                f"  ${strat[0]:,.0f} → ${strat[-1]:,.0f}")


class AnnualBars(Static):
    """Plotext bar chart of annual returns."""
    DEFAULT_CSS = """
    AnnualBars {
        height: 16;
        border: round $accent;
        padding: 0 1;
    }
    """
    rows: reactive[list] = reactive([])

    def render(self) -> str:
        rows = self.rows
        if not rows:
            return "[dim]Annual Returns\n\nNo data.[/]"
        years = [str(r.get("year", "?")) for r in rows]
        vals = [(_clean(r.get("strategy")) or 0) * 100 for r in rows]
        if HAS_PLOTEXT:
            plt.clf()
            plt.bar(years, vals, color="green")
            w = max(self.size.width - 4, 40)
            h = max(self.size.height - 3, 6)
            plt.plotsize(w, h)
            plt.theme("dark")
            plt.title("📈 Annual Returns (%)")
            return plt.build()
        # Fallback ASCII bars
        out = ["[bold]📈 Annual Returns[/]"]
        mx = max(abs(v) for v in vals) or 1
        for y, v in zip(years, vals):
            blen = round(abs(v) / mx * 40)
            colour = "green" if v >= 0 else "red"
            out.append(f"  {y}  [{colour}]{'█' * blen}[/] {v:+6.2f}%")
        return "\n".join(out)


class RollingSharpePanel(Static):
    DEFAULT_CSS = """
    RollingSharpePanel {
        height: 16;
        border: round $accent;
        padding: 0 1;
    }
    """
    series: reactive[list] = reactive([])

    def render(self) -> str:
        rs = self.series
        vals = [_clean(p.get("strategy")) for p in rs if _clean(p.get("strategy")) is not None]
        if len(vals) < 2:
            return "[dim]Rolling Sharpe (36mo)\n\nNo data.[/]"
        if HAS_PLOTEXT:
            plt.clf()
            plt.plot(list(range(len(vals))), vals, color="cyan")
            plt.hline(1.0, color="white")
            w = max(self.size.width - 4, 40)
            h = max(self.size.height - 3, 6)
            plt.plotsize(w, h)
            plt.theme("dark")
            plt.title("⚡ Rolling Sharpe (36mo)")
            return plt.build()
        return (f"[bold]⚡ Rolling Sharpe[/]\n"
                f"[cyan]{sparkline(vals, 70)}[/]   "
                f"min={min(vals):.2f}  max={max(vals):.2f}")


# ═══════════════════════════════════════════════════════
# Tab: Overview
# ═══════════════════════════════════════════════════════

class OverviewTab(Container):
    DEFAULT_CSS = """
    OverviewTab {
        layout: vertical;
        padding: 1 2;
    }
    #ov-cards   { height: 9;  layout: horizontal; }
    #ov-chart   { height: 19; layout: horizontal; }
    #ov-status  { height: 7;  layout: horizontal; }
    #ov-meta    { height: 1fr; padding: 1 2; }
    """

    def compose(self) -> ComposeResult:
        with Horizontal(id="ov-cards"):
            yield MetricCard("💰 Final Equity", "—", id="card-equity")
            yield MetricCard("📈 CAGR", "—", id="card-cagr")
            yield MetricCard("⚡ Sharpe", "—", id="card-sharpe")
            yield MetricCard("📉 Max DD", "—", id="card-dd")
            yield MetricCard("🎯 Win Rate", "—", id="card-wr")
            yield MetricCard("🔢 Months", "—", id="card-n")
        with Horizontal(id="ov-chart"):
            yield EquityChart(id="ov-eq")
        with Horizontal(id="ov-status"):
            yield RegimeBadge(id="ov-regime")
            yield Static(id="ov-rebal")
        yield Static(id="ov-meta")

    def refresh_from(self, snap: Snapshot) -> None:
        head = snap.presentation.get("headline", {})
        ks = snap.presentation.get("key_stats", {}).get("strategy", {})
        eq = snap.presentation.get("equity", {}).get("strategy", [])

        cagr = _clean(head.get("cagr_full")) or 0
        sharpe = _clean(head.get("sharpe_full")) or 0
        dd = _clean(head.get("max_dd_full")) or 0
        wr = _clean(ks.get("win_rate")) or 0
        n = head.get("n_full", "?")
        last_eq = next((p["value"] for p in reversed(eq)
                        if _clean(p.get("value")) is not None), 0)

        cagr_style = "bold green" if cagr >= 0.15 else (
            "bold yellow" if cagr >= 0 else "bold red")
        sharpe_style = "bold green" if sharpe >= 1.0 else (
            "bold yellow" if sharpe > 0 else "bold red")
        dd_style = "bold red" if dd < -0.15 else "bold yellow"

        self.query_one("#card-equity", MetricCard).update_value(
            f"${last_eq:,.0f}", "bold white")
        self.query_one("#card-cagr", MetricCard).update_value(
            f"{cagr:+.2%}", cagr_style)
        self.query_one("#card-sharpe", MetricCard).update_value(
            f"{sharpe:.2f}", sharpe_style)
        self.query_one("#card-dd", MetricCard).update_value(
            f"{dd:.2%}", dd_style)
        self.query_one("#card-wr", MetricCard).update_value(
            f"{wr:.1%}", "bold cyan")
        self.query_one("#card-n", MetricCard).update_value(
            str(n), "bold white")

        self.query_one("#ov-eq", EquityChart).series = snap.presentation.get("equity", {})

        tl = snap.presentation.get("trade_log") or []
        last = tl[-1] if tl else {}
        reg = last.get("regime", "?")
        self.query_one("#ov-regime", RegimeBadge).regime = reg

        deferred = last.get("deferred", False)
        def_badge = "[bold magenta]⚠ DEFERRED[/]" if deferred else "[dim green]● clear[/]"
        val = snap.presentation.get("validation", {})
        match = val.get("match", False)
        match_badge = "[bold green]✓ VALIDATED[/]" if match else "[bold red]✗ MISMATCH[/]"
        self.query_one("#ov-rebal", Static).update(
            f"[bold]Last rebalance:[/]   [bold cyan]{last.get('date','?')}[/]\n"
            f"[bold]Lookback:[/]         {last.get('lookback','?')} days\n"
            f"[bold]FOMC gate:[/]        {def_badge}\n"
            f"[bold]Validation:[/]       {match_badge}"
        )

        meta = snap.presentation.get("meta", {})
        self.query_one("#ov-meta", Static).update(
            f"[dim]generated: {meta.get('generated','?')}   "
            f"snapshot: {snap.loaded_at:%Y-%m-%d %H:%M:%S}   "
            f"monthly turnover: {fmt_pct(head.get('monthly_turnover'))}   "
            f"annual turnover: {fmt_num(head.get('annual_turnover'))}x   "
            f"trades: {head.get('n_trades','?')}[/]"
        )


# ═══════════════════════════════════════════════════════
# Tab: Performance
# ═══════════════════════════════════════════════════════

class PerformanceTab(Container):
    DEFAULT_CSS = """
    PerformanceTab {
        layout: vertical;
        padding: 1 2;
    }
    #perf-top { height: 17; layout: horizontal; }
    .perf-summary {
        width: 38;
        padding: 1 2;
        border: round $accent;
        height: 17;
    }
    #perf-bottom { height: 17; layout: horizontal; }
    #perf-table { height: 1fr; }
    """

    def compose(self) -> ComposeResult:
        with Horizontal(id="perf-top"):
            yield AnnualBars(id="perf-bars")
            yield Static(id="perf-summary", classes="perf-summary")
        with Horizontal(id="perf-bottom"):
            yield RollingSharpePanel(id="perf-rs")
        with VerticalScroll(id="perf-table"):
            yield Label("[bold]Strategy vs SPY — full key statistics[/]")
            yield DataTable(id="perf-stats", zebra_stripes=True, cursor_type="row")

    def refresh_from(self, snap: Snapshot) -> None:
        self.query_one("#perf-bars", AnnualBars).rows = snap.presentation.get("annual_returns", [])
        self.query_one("#perf-rs", RollingSharpePanel).series = snap.presentation.get("rolling_sharpe", [])

        ks = snap.presentation.get("key_stats", {})
        s = ks.get("strategy", {})
        sr = _clean(s.get("sharpe")) or 0
        sharpe_colour = "bold green" if sr > 1.0 else ("yellow" if sr > 0 else "bold red")
        cagr = _clean(s.get("cagr")) or 0
        cagr_colour = "bold green" if cagr >= 0.15 else "yellow"
        lines = [
            "[bold underline]Strategy Metrics[/]",
            f"  CAGR     : [{cagr_colour}]{cagr:+.2%}[/]",
            f"  Sharpe   : [{sharpe_colour}]{sr:.2f}[/]",
            f"  Sortino  : [bold]{_clean(s.get('sortino')) or 0:.2f}[/]",
            f"  Calmar   : [bold]{_clean(s.get('calmar')) or 0:.2f}[/]",
            f"  Max DD   : [bold red]{_clean(s.get('max_dd')) or 0:.2%}[/]",
            f"  Win Rate : [bold cyan]{_clean(s.get('win_rate')) or 0:.1%}[/]",
            f"  Best mo  : [green]{_clean(s.get('best_month')) or 0:+.2%}[/]",
            f"  Worst mo : [red]{_clean(s.get('worst_month')) or 0:+.2%}[/]",
            f"  Best yr  : [green]{_clean(s.get('best_year')) or 0:+.2%}[/]",
            f"  Worst yr : [red]{_clean(s.get('worst_year')) or 0:+.2%}[/]",
            f"  Months   : [bold]{s.get('n_months','?')}[/]",
            f"  Up cap   : [cyan]{_clean(s.get('upside_capture')) or 0:.1%}[/]",
            f"  Dn cap   : [magenta]{_clean(s.get('downside_capture')) or 0:.1%}[/]",
        ]
        self.query_one("#perf-summary", Static).update("\n".join(lines))

        spy = ks.get("spy", {})
        table = self.query_one("#perf-stats", DataTable)
        table.clear(columns=True)
        table.add_columns("Metric", "Strategy", "SPY")
        for label, key, fmt in [
            ("CAGR", "cagr", "pct"),
            ("Sharpe", "sharpe", "num"),
            ("Sortino", "sortino", "num"),
            ("Calmar", "calmar", "num"),
            ("Max Drawdown", "max_dd", "pct"),
            ("Best month", "best_month", "pct"),
            ("Worst month", "worst_month", "pct"),
            ("Best year", "best_year", "pct"),
            ("Worst year", "worst_year", "pct"),
            ("Win rate", "win_rate", "pct"),
            ("Avg month", "avg_month", "pct"),
            ("Months", "n_months", "raw"),
            ("Upside capture", "upside_capture", "pct"),
            ("Downside capture", "downside_capture", "pct"),
        ]:
            sv, pv = s.get(key), spy.get(key)
            if fmt == "pct":
                table.add_row(label, fmt_pct(sv), fmt_pct(pv))
            elif fmt == "num":
                table.add_row(label, fmt_num(sv), fmt_num(pv))
            else:
                table.add_row(label, str(sv or "—"), str(pv or "—"))


# ═══════════════════════════════════════════════════════
# Tab: Holdings
# ═══════════════════════════════════════════════════════

class HoldingsTab(Container):
    DEFAULT_CSS = """
    HoldingsTab {
        layout: vertical;
        padding: 1 2;
    }
    #hold-cards { height: 9; layout: horizontal; }
    #hold-body { height: 1fr; layout: horizontal; }
    #hold-tbl-wrap { width: 1fr; padding: 0 1; }
    #hold-last {
        width: 50;
        border: round $accent;
        padding: 1 2;
    }
    """

    def compose(self) -> ComposeResult:
        with Horizontal(id="hold-cards"):
            yield MetricCard("💼 Holdings", "—", id="h-card-n")
            yield MetricCard("🔝 Top1", "—", id="h-card-top")
            yield MetricCard("🛡 SHY %", "—", id="h-card-shy")
            yield MetricCard("📅 Last Rebal", "—", id="h-card-date")
        with Horizontal(id="hold-body"):
            with VerticalScroll(id="hold-tbl-wrap"):
                yield Label("[bold]Current target weights — configs/holdings.json[/]")
                yield DataTable(id="hold-tbl", zebra_stripes=True, cursor_type="row")
            yield Static(id="hold-last")

    def refresh_from(self, snap: Snapshot) -> None:
        items = sorted(snap.holdings.items(), key=lambda kv: -kv[1])
        n = len(items)
        top_sym, top_w = (items[0] if items else ("—", 0))
        shy_w = snap.holdings.get("SHY", 0.0)

        tl = snap.presentation.get("trade_log") or []
        last = tl[-1] if tl else {}
        last_date = last.get("date", "—")

        self.query_one("#h-card-n", MetricCard).update_value(str(n), "bold white")
        self.query_one("#h-card-top", MetricCard).update_value(
            f"{top_sym} {top_w:.0%}", "bold green")
        self.query_one("#h-card-shy", MetricCard).update_value(
            f"{shy_w:.1%}", "bold cyan" if shy_w > 0 else "dim white")
        self.query_one("#h-card-date", MetricCard).update_value(
            str(last_date), "bold white")

        table = self.query_one("#hold-tbl", DataTable)
        table.clear(columns=True)
        table.add_columns("Ticker", "Weight", "Allocation")
        for sym, w in items:
            blen = int(w * 40)
            bar = "█" * blen
            if w >= 0.5:
                style = "bold green"
            elif w >= 0.2:
                style = "green"
            elif w >= 0.05:
                style = "yellow"
            else:
                style = "dim"
            table.add_row(sym, f"{w:.2%}", Text(bar, style=style))

        # Last rebalance panel
        to = last.get("to") or {}
        frm = last.get("from") or {}
        reg = last.get("regime", "?")
        rstyle = REGIME_STYLE.get(reg, "bold white")
        ricon = REGIME_ICON.get(reg, "?")
        lines = [
            "[bold underline]Most recent rebalance[/]",
            "",
            f"  date     : [bold cyan]{last.get('date','?')}[/]",
            f"  regime   : [{rstyle}]{ricon}  {reg}[/]",
            f"  lookback : [bold]{last.get('lookback','?')}[/] days",
            f"  deferred : "
            + ("[bold magenta]YES (FOMC)[/]" if last.get("deferred") else "[dim green]no[/]"),
            "",
            "  [bold]target allocation[/]",
        ]
        for sym, w in sorted(to.items(), key=lambda kv: -kv[1]):
            prev = frm.get(sym, 0.0)
            d = w - prev
            if d > 0.001:
                d_txt = f"[green]+{d:.2%}[/]"
            elif d < -0.001:
                d_txt = f"[red]{d:+.2%}[/]"
            else:
                d_txt = "[dim]   ·   [/]"
            lines.append(f"    {sym:<6} [bold]{w:6.2%}[/]   Δ {d_txt}")
        self.query_one("#hold-last", Static).update("\n".join(lines))


# ═══════════════════════════════════════════════════════
# Tab: Backtest (trade log + monthly heatmap)
# ═══════════════════════════════════════════════════════

class BacktestTab(Container):
    DEFAULT_CSS = """
    BacktestTab {
        layout: vertical;
        padding: 1 2;
    }
    #bt-filter { height: 3; layout: horizontal; padding: 0 1; }
    #bt-info { height: 3; padding: 0 1; }
    #bt-tabs { height: 1fr; }
    """

    _filter: reactive[str] = reactive("all")

    def compose(self) -> ComposeResult:
        with Horizontal(id="bt-filter"):
            yield Button("All", id="bt-all", variant="primary")
            yield Button("Profitable", id="bt-pos", variant="success")
            yield Button("Losing", id="bt-neg", variant="error")
            yield Button("Deferred", id="bt-def", variant="warning")
            yield Button("🔄 Reload", id="bt-reload")
        yield Static(id="bt-info")
        with TabbedContent(id="bt-tabs"):
            with TabPane("Trade Log", id="bt-tl-pane"):
                yield DataTable(id="bt-tl", zebra_stripes=True, cursor_type="row")
            with TabPane("Monthly Heatmap", id="bt-heat-pane"):
                yield Static(id="bt-heat")

    def on_mount(self) -> None:
        # Snapshot is set by the App after construction
        pass

    @on(Button.Pressed, "#bt-all")
    def _f_all(self) -> None:
        self._filter = "all"
        self._render_log()

    @on(Button.Pressed, "#bt-pos")
    def _f_pos(self) -> None:
        self._filter = "pos"
        self._render_log()

    @on(Button.Pressed, "#bt-neg")
    def _f_neg(self) -> None:
        self._filter = "neg"
        self._render_log()

    @on(Button.Pressed, "#bt-def")
    def _f_def(self) -> None:
        self._filter = "def"
        self._render_log()

    @on(Button.Pressed, "#bt-reload")
    def _f_reload(self) -> None:
        if isinstance(self.app, QtsTui):
            self.app.action_reload()

    def refresh_from(self, snap: Snapshot) -> None:
        self._snap = snap
        self._render_log()
        self._render_heat()

    def _render_log(self) -> None:
        snap: Snapshot | None = getattr(self, "_snap", None)
        if not snap:
            return
        tl = snap.presentation.get("trade_log", [])
        f = self._filter
        if f == "pos":
            rows = [r for r in tl if (_clean(r.get("ret")) or 0) > 0]
        elif f == "neg":
            rows = [r for r in tl if (_clean(r.get("ret")) or 0) < 0]
        elif f == "def":
            rows = [r for r in tl if r.get("deferred")]
        else:
            rows = tl

        n_def = sum(1 for r in tl if r.get("deferred"))
        rets = [_clean(r.get("ret")) for r in tl]
        rets = [r for r in rets if r is not None]
        n_pos = sum(1 for r in rets if r > 0)
        n_neg = sum(1 for r in rets if r < 0)
        avg = sum(rets) / len(rets) if rets else 0
        self.query_one("#bt-info", Static).update(
            f"[dim]{len(tl)} rebalances    "
            f"[green]{n_pos} profitable[/]    "
            f"[red]{n_neg} losing[/]    "
            f"[magenta]{n_def} deferred[/]    "
            f"avg monthly return: [bold]{avg:+.2%}[/]    "
            f"filter: [cyan]{f}[/][/]"
        )

        table = self.query_one("#bt-tl", DataTable)
        table.clear(columns=True)
        table.add_columns("Date", "Regime", "Lookback", "Deferred", "Top", "Return")
        for row in rows[-200:][::-1]:
            to = row.get("to") or {}
            top = max(to.items(), key=lambda kv: kv[1])[0] if to else "?"
            reg = row.get("regime", "?")
            defer = "[magenta]Y[/]" if row.get("deferred") else "[dim]·[/]"
            table.add_row(
                str(row.get("date", "?")),
                reg,
                str(row.get("lookback", "?")),
                defer,
                top,
                colour_text(row.get("ret"), plus=True),
            )

    def _render_heat(self) -> None:
        snap: Snapshot | None = getattr(self, "_snap", None)
        if not snap:
            return
        heat: dict[int, dict[int, Optional[float]]] = {}
        for cell in snap.presentation.get("monthly_heatmap", []):
            y, m = cell.get("year"), cell.get("month")
            r = _clean(cell.get("ret"))
            if y is None or m is None:
                continue
            heat.setdefault(int(y), {})[int(m)] = r

        rt = Table(show_header=True, header_style="bold cyan",
                   expand=False, pad_edge=False, border_style="dim")
        rt.add_column("Year", style="bold")
        for m in range(1, 13):
            rt.add_column(datetime(2000, m, 1).strftime("%b"), justify="right")
        rt.add_column("YTD", justify="right", style="bold")
        for y in sorted(heat.keys()):
            cells: list[Text | str] = [str(y)]
            ytd = 1.0
            seen = False
            for m in range(1, 13):
                v = heat[y].get(m)
                if v is None:
                    cells.append(Text("  · ", style="dim"))
                else:
                    seen = True
                    ytd *= 1 + v
                    if v > 0.04:
                        st = "bold green"
                    elif v > 0:
                        st = "green"
                    elif v > -0.04:
                        st = "red"
                    else:
                        st = "bold red"
                    cells.append(Text(f"{v:+.1%}", style=st))
            ytdv = (ytd - 1) if seen else None
            if ytdv is None:
                cells.append(Text("  — ", style="dim"))
            else:
                st = "bold green" if ytdv > 0 else "bold red"
                cells.append(Text(f"{ytdv:+.1%}", style=st))
            rt.add_row(*cells)
        self.query_one("#bt-heat", Static).update(rt)


# ═══════════════════════════════════════════════════════
# Tab: Control
# ═══════════════════════════════════════════════════════

class ControlTab(Container):
    DEFAULT_CSS = """
    ControlTab {
        layout: vertical;
        padding: 1 2;
    }
    #ctl-top { height: 7; layout: horizontal; }
    #ctl-status-row { height: 3; padding: 0 1; }
    #ctl-log { height: 1fr; border: round $accent; }
    """

    _proc: Optional[subprocess.Popen] = None
    _process_running: reactive[bool] = reactive(False)
    _spinner: reactive[int] = reactive(0)

    def compose(self) -> ComposeResult:
        with Horizontal(id="ctl-top"):
            with Vertical():
                yield Label("[bold]Pipeline[/]")
                with Horizontal():
                    yield Button("📊 Regenerate JSON", id="btn-pres", variant="primary")
                    yield Button("📄 Build PDF", id="btn-pdf", variant="default")
                    yield Button("🛡 Validate Stress", id="btn-validate", variant="warning")
            with Vertical():
                yield Label("[bold]View[/]")
                with Horizontal():
                    yield Button("🔄 Reload", id="btn-reload", variant="success")
                    yield Button("⏹ Stop Job", id="btn-stop", variant="error")
        with Horizontal(id="ctl-status-row"):
            yield PulsingDot(id="ctl-dot")
            yield Static(id="ctl-status")
        yield Label("[bold]Live Log[/]")
        yield RichLog(id="ctl-log", highlight=True, markup=True,
                      wrap=True, max_lines=2000)

    def on_mount(self) -> None:
        self._log("[dim cyan]QTS TUI ready.[/]  "
                  "[dim]Tabs: [1] Overview  [2] Performance  "
                  "[3] Holdings  [4] Backtest  [5] Control[/]")
        self.set_interval(0.4, self._update_status)

    def _update_status(self) -> None:
        running = self._proc and self._proc.poll() is None
        self._process_running = bool(running)
        line = self.query_one("#ctl-status", Static)
        if running:
            self._spinner = (self._spinner + 1) % len(SPINNER_FRAMES)
            sp = SPINNER_FRAMES[self._spinner]
            line.update(f"[bold cyan]{sp} Process running...[/]   "
                        f"[dim]PID {self._proc.pid}[/]")
        else:
            line.update("[dim]Idle.[/]")

    def _log(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.query_one("#ctl-log", RichLog).write(f"[dim]{ts}[/]  {msg}")

    @on(Button.Pressed, "#btn-reload")
    def _on_reload(self) -> None:
        if isinstance(self.app, QtsTui):
            self.app.action_reload()
            self._log("[bold green]✓ snapshot reloaded[/]")

    @on(Button.Pressed, "#btn-stop")
    def _on_stop(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            self._log("[bold red]⏹ Job terminated.[/]")
        else:
            self._log("[dim]No job running.[/]")

    @on(Button.Pressed, "#btn-pres")
    def _on_pres(self) -> None:
        self._log("[bold]▶ Regenerating presentation JSON...[/]")
        self._run([sys.executable, "scripts/generate_presentation.py"])

    @on(Button.Pressed, "#btn-pdf")
    def _on_pdf(self) -> None:
        self._log("[bold]▶ Building PDF report...[/]")
        self._run([sys.executable, "scripts/generate_pdf_report.py"])

    @on(Button.Pressed, "#btn-validate")
    def _on_validate(self) -> None:
        self._log("[bold]▶ Validating stress harness...[/]")
        self._run([sys.executable, "scripts/model/stress_harness.py", "--validate"])

    def _run(self, cmd: list[str]) -> None:
        if self._proc and self._proc.poll() is None:
            self._log("[yellow]A job is already running. Stop it first.[/]")
            return
        self._log(f"[dim]$ {' '.join(cmd)}[/]")
        try:
            self._proc = subprocess.Popen(
                cmd,
                cwd=str(PROJECT_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except FileNotFoundError as e:
            self._log(f"[bold red]spawn failed: {e}[/]")
            return
        self._stream(self._proc)

    @work(thread=True)
    def _stream(self, proc: subprocess.Popen) -> None:
        assert proc.stdout is not None
        for raw in iter(proc.stdout.readline, ""):
            line = raw.rstrip()
            if not line:
                continue
            low = line.lower()
            if "error" in low or "traceback" in low:
                styled = f"[bold red]{line}[/]"
            elif "warning" in low or "warn" in low:
                styled = f"[yellow]{line}[/]"
            elif any(k in low for k in ("complete", "done", "saved",
                                         "loaded", "finished", "✓", "ok")):
                styled = f"[bold green]{line}[/]"
            elif any(k in low for k in ("epoch", "fold", "regime",
                                         "validating", "rebalance")):
                styled = f"[cyan]{line}[/]"
            else:
                styled = line
            self.app.call_from_thread(self._log, styled)
        proc.wait()
        rc = proc.returncode
        if rc == 0:
            self.app.call_from_thread(
                self._log, "[bold green]✓ Process finished successfully (exit 0)[/]")
            if isinstance(self.app, QtsTui):
                self.app.call_from_thread(self.app.action_reload)
        else:
            self.app.call_from_thread(
                self._log, f"[bold red]✗ Process exited with code {rc}[/]")


# ═══════════════════════════════════════════════════════
# Loading splash
# ═══════════════════════════════════════════════════════

class LoadingScreen(ModalScreen):
    DEFAULT_CSS = """
    LoadingScreen { align: center middle; }
    #loading-panel {
        width: 56;
        height: 14;
        border: double $accent;
        background: $surface;
        padding: 2 4;
        align: center middle;
        content-align: center middle;
    }
    """

    def compose(self) -> ComposeResult:
        with Container(id="loading-panel"):
            yield Static(
                "[bold cyan]QTS[/]\n"
                "[dim]ETF Momentum Rotation — AI-Enhanced[/]\n\n"
                "[dim]Loading presentation snapshot...[/]",
                id="loading-text",
            )
            yield LoadingIndicator()

    def on_mount(self) -> None:
        self.set_timer(1.4, self._close)

    def _close(self) -> None:
        self.app.pop_screen()


# ═══════════════════════════════════════════════════════
# App
# ═══════════════════════════════════════════════════════

APP_CSS = """
Screen { background: $surface; }
Header { background: #0f2744; color: #00d4ff; }
Footer { background: #0f2744; }
TabbedContent { height: 1fr; }
TabPane { padding: 0; }
MetricCard #card-title {
    color: $text-muted;
    text-style: italic;
    content-align: center middle;
}
MetricCard #card-value {
    text-style: bold;
    content-align: center middle;
}
Button { margin: 0 1; }
RegimeBadge { margin: 0 2; }
DataTable { height: auto; }
"""


class QtsTui(App):
    """QTS Terminal UI — read-only viewer."""

    TITLE = "QTS"
    SUB_TITLE = "ETF Momentum Rotation · AI-Enhanced · read-only"
    CSS = APP_CSS

    BINDINGS = [
        Binding("1", "switch_tab('tab-overview')", "Overview", show=True),
        Binding("2", "switch_tab('tab-perf')", "Performance", show=True),
        Binding("3", "switch_tab('tab-hold')", "Holdings", show=True),
        Binding("4", "switch_tab('tab-bt')", "Backtest", show=True),
        Binding("5", "switch_tab('tab-ctl')", "Control", show=True),
        Binding("r", "reload", "Reload", show=True),
        Binding("q", "quit", "Quit", show=True),
        Binding("ctrl+c", "quit", "Quit", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.snap: Snapshot | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(initial="tab-overview", id="tabs"):
            with TabPane("📊 Overview", id="tab-overview"):
                yield OverviewTab(id="t-overview")
            with TabPane("📈 Performance", id="tab-perf"):
                yield PerformanceTab(id="t-perf")
            with TabPane("💼 Holdings", id="tab-hold"):
                yield HoldingsTab(id="t-hold")
            with TabPane("🎯 Backtest", id="tab-bt"):
                yield BacktestTab(id="t-bt")
            with TabPane("⚙ Control", id="tab-ctl"):
                yield ControlTab(id="t-ctl")
        yield Footer()

    def on_mount(self) -> None:
        self.push_screen(LoadingScreen())
        self._reload()
        self.set_interval(2.0, self._poll_mtime)

    def action_switch_tab(self, tab_id: str) -> None:
        self.query_one("#tabs", TabbedContent).active = tab_id

    def action_reload(self) -> None:
        self._reload()
        self.notify("Snapshot reloaded", timeout=2)

    def _reload(self) -> None:
        try:
            self.snap = load_snapshot()
        except Exception as e:
            self.notify(f"load error: {e}", severity="error")
            return
        for w in self.query(OverviewTab):
            w.refresh_from(self.snap)
        for w in self.query(PerformanceTab):
            w.refresh_from(self.snap)
        for w in self.query(HoldingsTab):
            w.refresh_from(self.snap)
        for w in self.query(BacktestTab):
            w.refresh_from(self.snap)

    def _poll_mtime(self) -> None:
        if not self.snap:
            return
        try:
            cur = PRES_PATH.stat().st_mtime
        except FileNotFoundError:
            return
        if cur > self.snap.pres_mtime + 0.001:
            self._reload()
            self.notify("presentation JSON reloaded", timeout=3)


# ═══════════════════════════════════════════════════════
# Entrypoint
# ═══════════════════════════════════════════════════════

def _run_serve(host: str, port: int) -> int:
    """Serve the React/Recharts backtest dashboard over plain HTTP.

    Hosts results/ at http://host:port/, with backtest_dashboard.html as
    the index. The dashboard fetches ./backtest_presentation.json on load.
    """
    import http.server
    import socketserver

    web_root = PROJECT_ROOT / "results"
    index_file = web_root / "backtest_dashboard.html"
    if not index_file.exists():
        print(f"ERROR: {index_file} not found", file=sys.stderr)
        return 2
    if not (web_root / "backtest_presentation.json").exists():
        print(f"WARNING: {web_root / 'backtest_presentation.json'} missing — "
              "regenerate with `py scripts/generate_presentation.py`",
              file=sys.stderr)

    import re as _re

    _NAN_RE = _re.compile(rb'(?<![A-Za-z0-9_"])(NaN|-?Infinity)(?![A-Za-z0-9_"])')

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(web_root), **kw)

        def do_GET(self) -> None:  # noqa: N802
            if self.path in ("/", "/index.html"):
                self.path = "/backtest_dashboard.html"
            # Sanitize JSON responses on the fly: Python's json.dump emits
            # the literal tokens `NaN`, `Infinity`, `-Infinity`, which
            # browsers' JSON.parse rejects. Rewrite them to null so the
            # React dashboard can load.
            if self.path.endswith(".json"):
                target = (web_root / self.path.lstrip("/")).resolve()
                if target.is_file() and str(target).startswith(str(web_root.resolve())):
                    try:
                        body = target.read_bytes()
                        body = _NAN_RE.sub(b"null", body)
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Content-Length", str(len(body)))
                        self.send_header(
                            "Cache-Control",
                            "no-store, no-cache, must-revalidate, max-age=0")
                        self.send_header("Pragma", "no-cache")
                        self.end_headers()
                        self.wfile.write(body)
                        return
                    except OSError:
                        pass
            return super().do_GET()

        def end_headers(self) -> None:
            # No caching — picks up regenerated JSON on hard refresh.
            self.send_header("Cache-Control",
                             "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            super().end_headers()

        def log_message(self, fmt: str, *args) -> None:
            sys.stdout.write("[%s] %s\n" % (self.log_date_time_string(),
                                              fmt % args))
            sys.stdout.flush()

    class ReusableTCPServer(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    print("=" * 64)
    print(" QTS dashboard — static HTTP server")
    print(f"   web root  : {web_root}")
    print(f"   host      : {host}")
    print(f"   port      : {port}")
    print(f"   url       : http://{host}:{port}/")
    print("   NOTE: firewall rule must restrict 8765 to the ZeroTier iface.")
    print("=" * 64, flush=True)

    with ReusableTCPServer((host, port), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nshutdown")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="QTS TUI (read-only viewer)")
    ap.add_argument("--serve", action="store_true",
                    help="serve via textual-serve on 0.0.0.0:8765")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = ap.parse_args()
    if args.serve:
        return _run_serve(args.host, args.port)
    QtsTui().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
