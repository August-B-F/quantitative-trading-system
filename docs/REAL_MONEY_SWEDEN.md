# REAL MONEY IN SWEDEN — ISK vs depå for the blend_126_252 rotation

Date: 2026-07-02. Workstream G (study14). Model + numbers:
`research/droplets/study14_tax/` (HYPOTHESIS.md written before the math
was run; scenario grid in `scenario_results.csv`).

**Bottom line first.** For a Swedish resident running this strategy
(~8x/yr one-way turnover), the account wrapper is a first-order return
lever, comparable to or larger than the biggest signal droplet ever
adopted in this repo (+250 bps dev). At the honest forward scenario
(~12% CAGR) an ISK with a UCITS-mapped universe beats a US-broker depå
by **~+130 to +240 bps/yr after tax and after honest frictions**,
depending on account size. The one configuration that is NOT clearly
better in an ISK: a large account (≥3M SEK) combined with low CAGR
belief (8%) at a high-friction broker. And the single most important
practical fact: **the broker choice inside the ISK swings the result by
~190 bps/yr** (Nordnet with valutakonto vs Avanza auto-FX on every
trade) — the wrapper decision and the broker decision are one decision.

---

## 1. ISK rules, 2026 status (confirmed against Skatteverket)

- **Tax-free allowance (skattefri grundnivå): 300,000 SEK from
  2026-01-01.** Legislated and in force; it was 150,000 SEK during 2025.
  The allowance is per person and is shared across ISK + kapital-
  försäkring + PEPP (ISK gets the deduction first). It is applied
  automatically as a deduction in inkomstslaget kapital in the
  deklaration. ([Skatteverket][1], [Avanza][2], [Konsumenternas][3])
- **Schablonintäkt formula:** kapitalunderlag × (statslåneränta per
  Nov 30 prior year + 1.00pp, floor 1.25%). Statslåneränta 2025-11-30 =
  **2.55%**, so the 2026 rate is **3.55%**, taxed at 30% ⇒ **effective
  1.065%/yr on the capital base above 300k SEK** (2025: 0.888% above
  150k). ([Skatteverket][1], [Fondkollen][4], [Morningstar][5])
- **Kapitalunderlag** = (account value at the start of each quarter +
  ALL deposits made during the year) / 4. Deposits are deliberately
  double-counted in the funding year; transfers between own ISKs are
  not deposits. ([Skatteverket][1])
- **Key properties for this strategy:** no capital-gains tax, no K4, no
  per-trade reporting, unlimited turnover. The 8x/yr turnover that
  costs 30% of gains annually in a depå is **completely free** in an
  ISK. Losses are also not deductible, and the schablon is charged in
  down years too — the wrapper taxes the base, not the return.
- Historical schablon range for calibration: 0.375% (floor years,
  2021) to 1.086% (2024). Assume ~0.9–1.1% going forward; the math
  below holds the 2026 value constant and reports sensitivity.

## 2. The implied alternative: Alpaca = vanlig depå

Alpaca cannot offer ISK (only Swedish/EEA institutions in the ISK
regime can). Real money at Alpaca means a plain depå for Swedish tax:

- **30% tax on realized net gains.** At ~8x/yr turnover and a 1–2 month
  average holding period, effectively the entire year's gain is
  realized in-year: after-tax growth ≈ (1 + 0.70·r). Losses are
  deductible against gains (full) within the year; net losses only 70%
  against other capital income.
- **Reporting burden:** every sale must be declared on blankett K4.
  Lines can be aggregated per security per year, so it is ~13–26 K4
  lines, not hundreds — but the omkostnadsbelopp must be computed with
  genomsnittsmetoden across every buy, each converted USD→SEK at its
  trade-date FX rate. Alpaca provides **no kontrolluppgifter to
  Skatteverket**, so all of this is manual (or scripted) and
  audit-sensitive. On top of that the USD cash balance is itself a K4
  section C asset: currency gains taxable at 30%, losses only 70%
  deductible.
- **Dividends:** W-8BEN gives the 15% US treaty withholding, creditable
  against Swedish tax (avräkning) — roughly neutral, but one more form.
- **Deferral loss:** in a depå, high turnover destroys the deferral
  that buy-and-hold enjoys. Measured in the model: at the same 12%
  CAGR, buy-and-hold-SPY-in-depå nets 9.5%/yr while the 8x-turnover
  strategy nets 8.4%/yr — i.e. **in a depå the rotation must beat SPY
  by ~50–180 bps/yr (rising with CAGR) before it adds anything**. In an
  ISK that hurdle is exactly zero.

## 3. PRIIPs: the universe must be re-mapped to UCITS

Confirmed still in force in 2026: US-domiciled ETFs publish no PRIIPs
KID, so EEA brokers (Avanza, Nordnet, IBKR-retail, DEGIRO, …) may not
sell them to retail clients. SPY/QQQ/SOXX etc. are unbuyable in any
Swedish ISK; the workaround is the UCITS clone universe. ([finorum][6],
[justETF][7], [EU Parliament][8]) (Loopholes — professional-client
opt-up at IBKR, US-listed options exercise — are not compatible with an
ISK and not worth the complexity here.)

### UCITS mapping table

TERs marked (v) were verified this session; others are from provider
data as of the 2026-07 research pass — re-verify each line on
justETF/provider before funding. All the iShares/Invesco/SPDR/Xtrackers
lines below trade on Xetra and are orderable online at both Avanza and
Nordnet; EXUS additionally has a Nasdaq Stockholm SEK line.

| US (TER) | UCITS twin | TER | Repl. | AUM (~) | Exchange / SEK line | Notes on the delta |
|---|---|---|---|---|---|---|
| SPY 0.09% | iShares Core S&P 500 (CSPX/SXR8) | 0.07% | phys | >$100B | Xetra, LSE | −2 bps; unit ~€590 → at small accounts prefer Invesco S&P 500 (SPXS, 0.05%, synthetic) or Vanguard VUAA (~$110 units) |
| QQQ 0.20% | Invesco EQQQ Nasdaq-100 (EQQQ) | 0.30% (v) | phys | ~$10B | Xetra, LSE, MI | +10 bps; Amundi Nasdaq-100 II (0.22%) is the cheaper alt |
| SOXX 0.35% | VanEck Semiconductor UCITS (SMH/VVSM) | 0.35% (v) | phys | $9.6B (v, 2026-06) | Xetra, LSE | Same TER but DIFFERENT index (MarketVector US-listed 25 vs ICE Semi 30). Study1 measured SMH↔SOXX TE 6.6% — the largest single implementation gap in the mapping. Broader alt: iShares MSCI Global Semiconductors (SEMI, 0.35% (v)) |
| XLK 0.08% | iShares S&P 500 Info Tech Sector (IUIT/QDVE) | 0.15% | phys | ~$10B | Xetra | +7 bps; index match good (S&P 500 IT both) |
| VGT 0.10% | same QDVE (no Vanguard IT UCITS) | 0.15% | phys | — | Xetra | XLK and VGT collapse to ONE UCITS line → the universe loses a name; note the ledger already flags dropping VGT as a lead |
| IGV 0.41% | **NO UCITS twin exists** (only European-companies tech funds) | — | — | — | — | Confirmed gap: no US-software UCITS. Nearest usable proxy is QDVE (US IT sector). The rotation universe must be respecified ex-ante without IGV — a new universe spec, per constitution rule 9 |
| XLE 0.09% | SPDR S&P U.S. Energy Select Sector (SXLE) | 0.15% | phys | ~$0.5B | Xetra | +6 bps; iShares S&P 500 Energy Sector alt at 0.15% |
| GLD 0.40% | Invesco Physical Gold ETC (SGLD) | 0.12% | phys ETC | ~$18B | Xetra, LSE | **−28 bps (UCITS-side cheaper!)**; iShares Physical Gold (SGLN) also 0.12%. ETC wrapper, ISK-eligible, KID exists |
| SHY 0.15% | iShares $ Treasury Bond 1-3yr (IBTA acc / IBTS dist) | 0.07% (v) | phys | ~$10B | Xetra, LSE | −8 bps; this is the gate park — liquid and fine |
| EFA 0.33% | Xtrackers MSCI World ex USA (EXUS) | 0.15% (v) | phys | £5.2B (v, 2026-06) | Xetra + **Nasdaq Stockholm SEK line** | −18 bps; index includes Canada (World ex-US ⊃ EAFE) — small composition delta |
| AGG 0.03% | iShares US Aggregate Bond UCITS (IUAG/SUAG) | 0.25% | phys | ~$2B | Xetra, LSE | **+22 bps, worst delta in the table**; SPDR US Aggregate (0.17%) slightly better |
| IEF 0.15% | iShares $ Treasury Bond 7-10yr (IBTM) | 0.07% | phys | ~$4B | Xetra, LSE | −8 bps |
| TLT 0.15% | iShares $ Treasury Bond 20+yr (IDTL) | 0.07% | phys | ~$6B | Xetra, LSE | −8 bps |

**Weighted TER delta for the actual rotation sleeve ≈ 0** (the +10/+22
on QQQ/AGG are offset by −28/−18/−8 on gold, ex-US, and Treasuries).
The real UCITS penalties are elsewhere: (i) courtage (Alpaca $0 vs
~0.06–0.25%/side), (ii) Xetra spreads (+3–10 bps/side vs US), (iii) FX
(0.25% per auto-converted trade at Avanza vs 0.075% manual with a
Nordnet valutakonto), (iv) the SOXX→SMH tracking gap, (v) IGV has no
twin at all. Accumulating share classes remove dividend handling
entirely (a small plus inside ISK).

## 4. THE MATH — 10-year terminal wealth (SEK)

Model per `research/droplets/study14_tax/HYPOTHESIS.md`: ISK pays
1.065% on the quarterly-average base above 300k (allowance held nominal,
rate held at the 2026 level); depå compounds at (1+0.70r); buy-and-hold
pays 30% once in year 10. ISK friction (extra cost of the UCITS
implementation vs the Alpaca baseline, from 8x turnover × extra
per-side cost): LOW 60 bps/yr (Nordnet + valutakonto, good courtage
tier), MID 120 bps/yr (central), HIGH 250 bps/yr (Avanza-style 0.25%
auto-FX on every trade + min-courtage at small size).

| Size | CAGR | Depå (Alpaca) | B&H SPY depå | ISK low-f | ISK mid-f | ISK high-f | ISK adv @mid (bps/yr) | Breakeven friction |
|---|---|---|---|---|---|---|---|---|
| 100k | 8% | 172,440 | 181,125 | 204,194 | 193,069 | 170,814 | **+120** | 240 bps |
| 100k | 12% | 224,023 | 247,409 | 294,342 | 278,867 | 247,823 | **+240** | 360 bps |
| 100k | 16% | 289,100 | 338,800 | 417,571 | 396,666 | 354,482 | **+357** | 480 bps |
| 300k | 8% | 517,321 | 543,374 | 594,298 | 562,871 | 499,964 | **+90** | 213 bps |
| 300k | 12% | 672,069 | 742,228 | 848,624 | 805,002 | 717,449 | **+197** | 323 bps |
| 300k | 16% | 867,300 | 1,016,401 | 1,199,283 | 1,139,399 | 1,018,901 | **+308** | 435 bps |
| 1M | 8% | 1,724,405 | 1,811,247 | 1,881,309 | 1,779,309 | 1,575,305 | **+33** | 154 bps |
| 1M | 12% | 2,240,231 | 2,474,094 | 2,708,265 | 2,566,261 | 2,281,438 | **+148** | 270 bps |
| 1M | 16% | 2,890,999 | 3,388,005 | 3,851,505 | 3,656,080 | 3,263,068 | **+264** | 387 bps |
| 3M | 8% | 5,173,214 | 5,433,742 | 5,558,481 | 5,254,848 | 4,647,711 | **+17** | 137 bps |
| 3M | 12% | 6,720,693 | 7,422,281 | 8,021,527 | 7,598,432 | 6,749,979 | **+134** | 255 bps |
| 3M | 16% | 8,672,996 | 10,164,014 | 11,429,283 | 10,846,600 | 9,674,971 | **+252** | 373 bps |

Readings (per the pre-registered decision rule):

1. **ISK wins every cell at LOW and MID friction.** At the honest
   forward scenario (12% CAGR): +240 bps/yr at 100k, +197 at 300k,
   +148 at 1M, +134 at 3M. Over 10 years at 1M SEK that is **+326k SEK
   (2.57M vs 2.24M)**.
2. **The advantage shrinks as the account grows** (the 300k allowance
   covers a shrinking share) and **grows with CAGR** (depå tax scales
   with return, ISK tax does not). Asymptotically the ISK drag is
   ~106.5 bps/yr flat vs the depå's 30%·CAGR (240/360/480 bps at
   8/12/16%).
3. **The HIGH-friction column is the warning.** With per-trade 0.25%
   auto-FX (Avanza without a currency-account equivalent), the ISK
   advantage at 8% CAGR is NEGATIVE at every size ≥300k. The breakeven
   friction at 3M/8% is only 137 bps/yr. **Broker/FX setup is worth
   more than the wrapper itself in the bad corner.**
4. **Only friction-dominated cell:** 3M SEK + 8% CAGR (+17 bps at MID,
   −113 at HIGH) → "either", decided entirely by execution setup.
5. **Deferral check:** buy-and-hold SPY in a depå beats running the
   8x-turnover strategy in a depå at equal CAGR by 52/108/178 bps/yr
   (8/12/16%). A depå structurally punishes exactly what this strategy
   does; the ISK removes that punishment.
6. **Schablon sensitivity** (in `scenario_results.csv`): at the 1.25%
   floor the 1M/12% advantage rises from +148 to +217 bps/yr; at the
   2024-peak rate (1.086% eff.) it is +146 — i.e. the conclusion is
   insensitive to plausible statslåneränta paths.
7. **Falsification check from HYPOTHESIS.md:** the 1M/12% MID cell
   (+148 bps/yr) clears the pre-declared 100 bps bar, so "the wrapper
   is among the largest levers in the project" is SUPPORTED — it is on
   par with the blend_126_252 droplet (+250 bps dev) and larger than
   every engineering droplet, but "dwarfs every droplet" is an
   overstatement for accounts ≥1M at MID friction.

Small-account integer-share drag (kept outside f): top-3 rotation at
100k SEK ⇒ ~33k SEK/leg. With sensibly chosen low-unit-price lines
(~200–500 SEK units: QDVE ~€30, SMH ~$40, EXUS ~€35, IBTA ~$5), the
expected rounding residual is ~half a unit per leg ≈ 750 SEK ≈ 0.75% of
the account idle ⇒ **~6–12 bps/yr** at 100k, <2 bps at 1M. Avoid CSPX
(~€590/unit ⇒ up to ~3–5% idle at 100k) in favor of VUAA/SPXS. This is
real but an order of magnitude smaller than the tax effect.

## 5. Practicalities

- **Automation:** there is NO sanctioned API path today. Nordnet's nExt
  API exists and can trade, but is **"currently not onboarding new
  customers"** (confirmed on the official docs this session). Avanza
  has no public API; the community `avanza` Python package rides the
  app's private endpoints (TOTP login) — ToS-gray, can break any day,
  unacceptable for real money. ([Nordnet API][9], [Sifferkoll][10])
- **Manual execution IS viable at this cadence.** The 4-tranche
  schedule means 4 execution days per month (+0/+5/+10/+15 td), 1–3
  orders each ⇒ ~48 short sessions/yr, ~10–15 min each. Keep the whole
  signal pipeline automated; have the scheduler emit a **trade ticket**
  (ticker, side, quantity, limit band) the evening before, and execute
  at the Xetra open (09:00 CET — convenient in Stockholm, unlike the
  15:30 CET US open). The constitution's freshness gate still applies:
  no ticket, no trade.
- **Broker choice:** Nordnet supports **valutakonton (USD/EUR/…) inside
  ISK** for Private Banking and Active Trading customers — manual FX at
  0.075% instead of 0.25% auto-FX per trade, which is most of the gap
  between the MID and HIGH friction columns. Avanza charges 0.25% FX on
  every foreign-currency trade with no currency-account option, but
  pays some interest on ISK cash (0.25% bas / ~1.94% trading tier)
  while Nordnet pays ~0. ([Nordnet valutakonto][11], [Nordnet FX
  FAQ][12], [Avanza prislista][13], [iskkonto.se][14]) Also check
  Montrose (Carnegie) — newer Swedish ISK broker with aggressive
  courtage — before funding.
- **No SHV equivalent / cash handling:** park gate periods in IBTA
  (SHY twin, 0.07%) exactly as the spec's SHY park; do not rely on ISK
  cash interest. Note a Nordnet quirk: drawing on the kreditkonto
  during auto-FX counts as a deposit and inflates the schablon base —
  keep a small cash buffer instead.
- **Fractional shares:** none at Avanza/Nordnet for exchange-traded
  lines — integer shares only (quantified above; manageable).
- **Backtest fidelity caveat (honesty item):** every ledger number in
  this repo is on US ETFs. The UCITS book differs (SMH≠SOXX TE 6.6%,
  no IGV, XLK+VGT merge, Xetra opens vs NYSE opens). Before real money,
  the universe must be respecified ex-ante on the UCITS menu and run
  through the daily-ledger engine as its own pre-registered spec — the
  mapping above is an implementation plan, not a measured backtest.

## 6. Recommendation and migration path

**Recommendation: ISK at Nordnet (with valutakonto, Active
Trading/Private Banking tier) or, second choice, Avanza accepting the
FX drag with SEK-listed lines where possible.** Specifically:

- **≤300k SEK: ISK, unconditionally.** Zero tax below the allowance;
  +120 to +360 bps/yr over the Alpaca depå at central frictions.
- **300k–1M at ≥12% CAGR belief: ISK**, +150–260 bps/yr.
- **≥3M with low (8%) CAGR belief: friction-dominated** — ISK only
  wins with the low-friction broker setup; a depå is defensible there
  but buys a K4/genomsnittsmetoden bookkeeping burden.
- **Never run this 8x-turnover strategy in a depå as the long-term
  home** when an ISK is available: the 30% annual-realization drag
  (240–480 bps/yr at 8–16% CAGR) is the single largest recurring cost
  anywhere in this system, and in a depå the strategy must first beat
  buy-and-hold's tax deferral (~50–180 bps/yr) before adding value.

Migration path (respects constitution rule 6 — ≥3 months paper +
fidelity gate before any real capital):

1. **Now → paper-race end:** keep the Alpaca paper race exactly as is;
   it remains the signal-fidelity instrument.
2. **In parallel (no capital):** open the ISK; activate
   valutakonto/knowledge test; confirm every mapped UCITS line is
   orderable online and record 09:00–09:30 CET spreads for a few weeks.
3. **Pre-register the UCITS respec** (new ex-ante universe: SMH-U,
   EQQQ/Amundi, QDVE, SXLE, SGLD, IBTA, EXUS, IBTM, IDTL, CSPX/VUAA; IGV
   dropped) and run it through `run_ledger_backtest` as its own spec
   with the friction assumptions above — one spec, both cost levels.
4. **Shadow month(s):** generate UCITS trade tickets alongside Alpaca
   paper fills; measure realized all-in friction against the 120 bps/yr
   MID assumption. If measured friction >240 bps/yr at the intended
   size, stop and fix the broker setup first (that number flips the 8%
   scenario).
5. **Fund 300k SEK first** (entirely inside the tax-free band — the
   real-money learning period is tax-free), scale only after the
   implementation-fidelity gate passes.
6. Revisit this document each December when the new statslåneränta and
   any allowance changes are announced.

Sources:

- [1] Skatteverket — Investeringssparkonto (ISK): https://www.skatteverket.se/privat/skatter/vardepapper/investeringssparkontoisk.4.5fc8c94513259a4ba1d800037851.html
- [2] Avanza blogg — Så blir skatten på ISK och KF 2026 (skattefritt upp till 300 000 kr): https://blogg.avanza.se/sa-blir-skatten-pa-isk-och-kf-2026-skattefritt-upp-till-300-000-kronor/
- [3] Konsumenternas — Höjt skattefritt sparande på ISK: https://www.konsumenternas.se/arkiv---nyheter-bloggar-och-poddar/nyheter/2025/december/hojt-skattefritt-sparande-pa-isk/
- [4] Fondkollen — Så blir ISK-skatten 2026: https://fondkollen.se/skatt/sa-blir-isk-skatten-2026/
- [5] Morningstar Sverige — ISK-skatten 2026 blir näst högsta någonsin: https://global.morningstar.com/sv/privatekonomi/isk-skatten-2026-blir-nst-hgsta-ngonsin
- [6] Finorum — US ETFs in Europe: Why PRIIPs Blocks Retail Access: https://finorum.com/us-etfs-in-europe/
- [7] justETF — US-domiciled ETFs no longer available: https://www.justetf.com/en/news/etf/us-domiciled-etfs.html
- [8] European Parliament question E-004745/2021 (PRIIPs / US ETF retail access): https://www.europarl.europa.eu/doceo/document/E-9-2021-004745_EN.html
- [9] Nordnet External API — Getting started ("currently not onboarding new customers"): https://www.nordnet.se/externalapi/docs/getting_started
- [10] Sifferkoll — Automated Trading using the Nordnet nExt API: https://www.sifferkoll.se/algo-trading/automated-trading-using-nordnet-next-api/
- [11] Nordnet — Valutakonto på ISK (press/blogg): https://nordnetab.com/press_release/nordnet-lanserar-valutakonto-pa-isk/ and https://www.nordnet.se/blogg/valutakonto-isk/
- [12] Nordnet FAQ — Hur fungerar valutaväxling och vad kostar det? (0.075% manuell / 0.25% automatisk): https://www.nordnet.se/faq/handel-vardepapper/valutakonto/hur-fungerar-valutavaexling-och-vad-kostar-det
- [13] Avanza — Prislista handel utland (0.25% valutaväxlingsavgift): https://www.avanza.se/konton-lan-prislista/prislista/handel-utland.html
- [14] iskkonto.se — ISK-ränta hos Avanza, Nordnet, SEB & storbankerna: https://www.iskkonto.se/ranta/
- [15] justETF — VanEck Semiconductor UCITS ETF (IE00BMC38736, TER 0.35%, AUM $9.6B 2026-06): https://www.justetf.com/en/etf-profile.html?isin=IE00BMC38736
- [16] DWS — Xtrackers MSCI World ex USA UCITS ETF 1C (EXUS, TER 0.15%): https://etf.dws.com/en-gb/IE0006WW1TQ4-msci-world-ex-usa-ucits-etf-1c/
- [17] iShares — $ Treasury Bond 1-3yr UCITS ETF (IBTS/IBTA, TER 0.07%): https://www.ishares.com/uk/individual/en/products/251715/ishares-treasury-bond-13yr-ucits-etf
- [18] iShares — $ Treasury Bond 20+yr UCITS ETF (IDTL): https://www.ishares.com/uk/individual/en/products/272124/ishares-usd-treasury-bond-20-yr-ucits-etf
- [19] justETF — Invesco EQQQ Nasdaq-100 UCITS ETF (TER 0.30%): https://www.justetf.com/en/etf-profile.html?isin=IE0032077012
- [20] Handelsbanken — Så beräknas skatt på ISK: https://www.handelsbanken.se/sv/privat/spara/investeringssparkonto/sa-beraknas-skatt-pa-isk
- [21] Skatteverket — Blankett K4 (försäljning av värdepapper), genomsnittsmetoden: https://www.skatteverket.se/privat/skatter/vardepapper.4.18e1b10334ebe8bc80001217.html
