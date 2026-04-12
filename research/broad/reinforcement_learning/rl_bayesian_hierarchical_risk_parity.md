# RL-BHRP: RL within Bayesian Hierarchical Risk Parity

**Citation:** Kang, S. and Tian, Z. (2025). "Optimal Portfolio Construction -- A Reinforcement Learning Embedded Bayesian Hierarchical Risk Parity (RL-BHRP) Approach." arXiv:2508.11856.

**Core mechanism:** Three-component system: (1) Bayesian hierarchical model estimates sector/asset return distributions with uncertainty and partial pooling, (2) risk parity allocates risk budgets across hierarchy, (3) RL agent adjusts allocation within risk parity constraints. RL operates within guardrails, preventing unconstrained overfitting.

**Signal:** Cluster assets into sectors. Bayesian model estimates distributions per sector and per asset within sector. Risk parity sets budgets. RL tilts within these budgets based on market conditions. Key insight: constrained RL prevents extreme allocations.

**Data needed:** US equities, sector classifications. Adaptable to ETFs with asset-class hierarchy.

**Performance:** Out-of-sample 2020-2025: ~120% cumulative wealth vs 101% static, 91% benchmark. ~15% annualized vs 13% and 12%.

**Weaknesses:** 15% vs 13% is meaningful but not dramatic. Bayesian estimation adds complexity. RL component may be doing little beyond what risk parity achieves alone. 2020-2025 is a single macro regime.

**Assessment:** Architecture is sensible -- constraining RL within principled framework addresses overfitting. Results are plausible (not spectacular enough to be suspicious). **Worth implementing if you want RL benefits with safety guardrails.**

**Application to 8-ETF rotation:** Structure ETFs hierarchically by asset class. Apply Bayesian risk parity at asset-class level, constrained RL to tilt within each class based on model predictions.
