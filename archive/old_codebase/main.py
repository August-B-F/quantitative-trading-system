# ARCHIVED: pre-Phase-3 codebase, not imported by current pipeline.
"""iStock — entry point.

Launches the Terminal UI directly.

Usage:
    python main.py
    python main.py --config config
    python main.py --help
"""
import sys
import os

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(__file__))


def main():
    try:
        import textual  # noqa: F401
    except ImportError:
        print("ERROR: textual is not installed.")
        print("       pip install textual plotext")
        sys.exit(1)

    # Import here so sys.path patch above takes effect first
    from scripts.tui import TradingTUI
    import argparse

    p = argparse.ArgumentParser(
        description="iStock — AI Stock Trader Terminal UI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Keys inside the TUI:
  1-5    Switch tabs (Dashboard / Performance / Positions / Signals / Control)
  r      Force-refresh all data panels
  q      Quit
  F1     Show help

Tabs:
  Dashboard   — equity curve, regime badge, GPU monitor, model info
  Performance — daily P&L chart, trade history, strategy metrics
  Positions   — live Alpaca positions with unrealised P&L
  Signals     — today's model predictions per symbol
  Control     — run download / train / backtest / bot from the UI
""",
    )
    p.add_argument(
        "--config",
        default="config",
        metavar="DIR",
        help="Config directory (default: config)",
    )
    args = p.parse_args()

    app = TradingTUI(config_dir=args.config)
    app.run()


if __name__ == "__main__":
    main()
