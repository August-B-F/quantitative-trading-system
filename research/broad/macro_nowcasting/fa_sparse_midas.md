# Factor-Augmented Sparse MIDAS

**Citation:** Beyhum, J. and Striaukas, J. (2023). "Factor-Augmented Sparse MIDAS Regressions with an Application to Nowcasting." *Journal of Business & Economic Statistics*. arXiv:2306.13362.

**Core mechanism:** Combines factor extraction (dense dimensionality reduction) with LASSO-type sparsity (sparse dimensionality reduction) in a MIDAS framework for mixed-frequency data. Key insight: in stable times, sparse signals dominate; in stress, dense factor information is crucial. Method adaptively combines both.

**Signal:** (1) Collect weekly financial + monthly macro indicators. (2) Extract factors from dense block. (3) Apply LASSO to select sparse predictors. (4) Combine via MIDAS weighting for GDP nowcast. (5) Use nowcast as regime-conditioning variable. Below-trend = defensive allocation.

**Data needed:** Weekly financial data (yield spreads, equity returns, commodities) + monthly FRED-MD. All freely available.

**Performance:** Outperforms purely sparse and purely dense models. Especially strong during COVID period. Published in top econometrics journal.

**Weaknesses:** MIDAS weighting requires lag polynomial parameter choices. Nowcasts GDP, not directly a regime label. Factor + LASSO + MIDAS is a complex pipeline.

**Assessment:** The adaptive sparse+dense combination is genuinely novel. Addresses known failure mode of each approach alone. Economically sensible that dense info dominates in stress. **Strong methodological contribution, implementable with standard tools.**

**Application to 8-ETF rotation:** Use FA-sparse-MIDAS to nowcast GDP growth at monthly frequency. Below-trend nowcast = defensive. Adaptive behavior (switching dense/sparse in crises) provides more timely regime detection than waiting for official GDP releases.
