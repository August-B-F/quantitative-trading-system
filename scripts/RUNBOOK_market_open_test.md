# Market-open execution test — runbook

Target: **15:30 local (market open)**, 2026-04-14.
Purpose: end-to-end test of the 9-strategy paper-trading execution
pipeline before the real start date (2026-04-30). After the test
succeeds, flatten everything with `--kill-all` so we don't carry 16
days of unplanned exposure.

---

## Preflight verified (2026-04-14 ~13:55, Aug + Claude)

- [x] `scripts/run_rebalance.py` exists, all 6 flags parse correctly
  (`--force --execute --no-refresh --strategy --status --kill-all`)
- [x] `.env` has `ALPACA_PAPER_MODE=true` (required by `--execute`)
- [x] All 9 `ALPACA_S{1..9}_KEY` + `ALPACA_S{1..9}_SECRET` pairs present
- [x] `tests/autonomous/cache/pred_reg.pkl` present (~49 KB, from 2026-04-13)
- [x] **Step 1 dry-run executed as preflight and works**:
      S5 TREND_SIMPLE signal = SPY 100%, equity $100k pulled from
      Alpaca, trade = BUY SPY, 100% turnover, $100 est cost
- [x] `--status` command works: all 9 accounts return $100k / 0% /
      CASH 0.0%, next rebalance 2026-04-30 (16 days)
- [x] `--kill-all` prompt is interactive (`input("Type CONFIRM ...")`)
      — pipe `echo CONFIRM | py -3 scripts/run_rebalance.py --kill-all`
      to bypass. Pipe mechanism verified with abort response.

---

## Execution sequence

Wait until 15:30 local (15:30 CEST = 9:30 ET = US market open).
**Do not start early** — the signal works off panel data but live order
fills need an open market.

### STEP 1 — dry-run S5 (signal verification)

```
py -3 scripts/run_rebalance.py --force --no-refresh --strategy 5
```

**Expected**: `S5 TREND_SIMPLE | Signal: SPY 100.0% | Trades: BUY SPY | Status: DRY RUN`.
No order is submitted.

**Checkpoint**: signal must be `SPY 100%`. If it says anything else
(SHY, CASH, empty), **abort** — the SMA-gate logic is broken or the
panel date is stale.

### STEP 2 — live execute S5 (real order on TREND_SIMPLE)

```
py -3 scripts/run_rebalance.py --force --no-refresh --execute --strategy 5
```

**Expected**: Same signal, status changes to `EXECUTED`. A real
market order is submitted to the S5 Alpaca paper account.

**Checkpoint**:
1. Script exits 0 with status `EXECUTED`.
2. Open Alpaca dashboard for the S5 paper account — confirm:
   - A BUY order for SPY was submitted and (likely) filled within
     seconds at market price.
   - Position = SPY with market value ~$100k, qty ~150-170 shares.
   - Cash drops to near zero.

If the fill fails (partial fill, rejected, too far from market) —
**abort**, do not run step 3. Investigate first.

### STEP 3 — live execute all 9 (the real test)

```
py -3 scripts/run_rebalance.py --force --execute
```

Note: **no `--no-refresh`** here — this lets the pipeline pull fresh
price/macro data before computing all 9 signals. If refresh fails,
the script exits with code 2 and nothing is submitted.

**Expected**: Rebalance report prints per-tier tables (confident /
neutral / skeptical). Each strategy shows signal + trades + EXECUTED.
9 separate sets of orders go out, one per Alpaca account.

**Checkpoint**: every strategy should print `Status: EXECUTED`. Any
`PARTIAL/FAILED` means an individual account had an issue — note the
slot number and which ticker failed.

### STEP 4 — verify positions

```
py -3 scripts/run_rebalance.py --status
```

**Expected**: each strategy shows the top holding matching its signal,
equity close to $100k (small drag from slippage/spread), P&L near zero.

**Checkpoint**: if any account still shows `CASH 0.0%`, its orders
didn't land. Cross-reference the Alpaca dashboard for that account.

### STEP 5 — flatten everything

```
echo CONFIRM | py -3 scripts/run_rebalance.py --kill-all
```

**Expected**: prints `closed N positions` per account across all 9.
Appends a `kill_all` event to `logs/rebalance_log.json`.

**Checkpoint**: run `--status` again and confirm all 9 accounts back
to $100k cash / CASH 0.0%. This is the starting-line state for
2026-04-30.

---

## Abort / recovery

- **Before step 3**: if anything in steps 1-2 is wrong, stop. Running
  step 3 with 9 strategies in parallel will multiply any bug by 9.
- **Mid-step 3**: Ctrl-C. Orders already submitted will still fill.
  Run step 5 (`--kill-all`) immediately to flatten what got through.
- **If --kill-all fails** for any account: go to the Alpaca dashboard
  for that specific account and flatten manually. Do not leave live
  positions over the 16-day gap before 2026-04-30.

---

## After the test succeeds

Remaining work before 2026-04-30:
1. SSH into `the-tower`
2. Clone the repo + install deps
3. Copy `.env` over (or populate per-machine)
4. Install the monthly-rebalance cron (last trading day of the month,
   post-market-close window)
5. Verify with `--status` from the-tower
