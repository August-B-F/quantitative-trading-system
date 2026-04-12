# Feature Catalog

Phase 4 notes on feature usage, gotchas, and fold-dependent handling.

## Fold-dependent features

| Feature | Pre-2019-10-04 | Post-2019-10-04 | Reason |
|---------|----------------|-----------------|--------|
| cboe_putcall_total_spliced | USE (real CBOE data) | **DO NOT USE** — substitute raw VIX features (vix level, vix 21d chg, vix 5d MA) | Overlap R²=0.248. Synthetic portion is a weak VIX reconstruction and adds no information beyond VIX itself. |
| cboe_putcall_equity_spliced | USE (real CBOE data) | **DO NOT USE** — substitute raw VIX features | Overlap R²=0.347. Same rationale as total. |
| cboe_putcall_index_spliced | n/a | n/a | Dropped at splice stage (R²=0.022). Use `cboe_putcall_index.parquet` directly for the 2003-2019 window only. |

**Implementation note for Phase 4 fold logic:**
- Gate the put/call columns on `is_proxy == False` in training/CV folds that cross 2019-10-04.
- For post-2019 folds, rely on VIX-derived sentiment features from `data/clean/prices/_VIX.parquet` (close, 21d diff, 5d MA) — the same regressors used in the splice. The VIX features carry the full signal that the synthetic PCR would have provided, without the lossy regression step.
- Do not re-fit the splice model in Phase 4; it is intentionally a data-layer artifact for the 2003-2019 period only.
