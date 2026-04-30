/* Skylark — 9-strategy horse race UI
 * Pages (Phase A): Dashboard, Horse Race. Phase B pages are stubbed.
 */
(() => {
'use strict';

// ─── Constants ────────────────────────────────────────────────────────────
const TIER_COLORS = {
  confident: ['#28d4b0', '#1fb89a', '#5feaca'],
  neutral:   ['#e8a030', '#c47e1a', '#f4c060'],
  skeptical: ['#a878e8', '#8858c8', '#c098f4'],
};
const TIER_ORDER = ['confident', 'neutral', 'skeptical'];
const BENCH_COLORS = {
  'SPY':   '#f4f4f2',
  '60/40': '#8a9bb4',
};

const IS_MOBILE = () => window.innerWidth <= 768;

const fmt = {
  pct:  (v, d = 1) => v == null ? '—' : `${(v * 100).toFixed(d)}%`,
  pctS: (v, d = 1) => v == null ? '—' : `${v >= 0 ? '+' : ''}${(v * 100).toFixed(d)}%`,
  num:  (v, d = 2) => v == null ? '—' : Number(v).toFixed(d),
  money: v => v == null ? '—' : `$${Math.round(v).toLocaleString()}`,
};

const state = {
  page:        'dashboard',
  dashCache:   null,
  compareCache: null,
  charts:      {},
  tierFilter:  'all',
  sortKey:     'sharpe',
  sortDir:     'desc',
  sdSlot:      1,
  accTier:     'confident',
  rebPoll:     null,
  dashScale:   'linear',
  hrScale:     'linear',
  benchOn:     true,
};

// ─── Utilities ────────────────────────────────────────────────────────────
async function fetchJSON(url) {
  try {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.json();
  } catch (err) {
    console.error('fetch failed:', url, err);
    return null;
  }
}

function trackingLabel(status) {
  const map = { on_track: 'On Track', drifting: 'Drifting', diverged: 'Diverged', pending: 'Pending' };
  return map[status] || 'Pending';
}

function tierColor(tier, idx) {
  const palette = TIER_COLORS[tier] || ['#888'];
  return palette[idx % palette.length];
}

function destroyChart(id) {
  if (state.charts[id]) { state.charts[id].destroy(); delete state.charts[id]; }
}

Chart.defaults.color = '#6c6c6c';
Chart.defaults.font.family = "'JetBrains Mono', monospace";
Chart.defaults.font.size = 10;
Chart.defaults.borderColor = '#242424';

// ─── Routing ──────────────────────────────────────────────────────────────
function setPage(name) {
  state.page = name;
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  const el = document.getElementById('page-' + name);
  if (el) el.classList.add('active');
  document.querySelectorAll('.nav-item').forEach(n => n.classList.toggle('active', n.dataset.page === name));
  const titleMap = {
    dashboard: 'Dashboard', horserace: 'Horse Race', strategy: 'Strategy Detail',
    accounts: 'Accounts', datahealth: 'Data Health', regime: 'Regime',
    rebalance: 'Rebalance Log', system: 'System Health',
  };
  document.getElementById('page-title').textContent = titleMap[name] || name;
  loadPage(name);
}

async function loadPage(name) {
  // Rebalance page owns its own poll — tear it down when leaving.
  if (name !== 'rebalance' && state.rebPoll) { clearInterval(state.rebPoll); state.rebPoll = null; }
  switch (name) {
    case 'dashboard':  return renderDashboard();
    case 'horserace':  return renderHorseRace();
    case 'strategy':   return renderStrategy();
    case 'accounts':   return renderAccounts();
    case 'datahealth': return renderDataHealth();
    case 'regime':     return renderRegime();
    case 'rebalance':  return renderRebalance();
    case 'system':     return renderSystem();
  }
}

// ─── DASHBOARD ────────────────────────────────────────────────────────────
async function renderDashboard() {
  const data = await fetchJSON('/api/dashboard');
  if (!data) return;
  state.dashCache = data;

  document.getElementById('dash-aum').textContent = fmt.money(data.total_aum);
  document.getElementById('dash-aum-sub').textContent = `${data.n_strategies} strategies · ${data.live_mode ? 'LIVE' : 'paper'}`;

  if (data.best) {
    document.getElementById('dash-best').textContent = data.best.name;
    const el = document.getElementById('dash-best-sub');
    el.textContent = fmt.pctS(data.best.return_pct);
    el.className = 'card-sub ' + ((data.best.return_pct || 0) >= 0 ? 'text-pos' : 'text-neg');
  }
  if (data.worst) {
    document.getElementById('dash-worst').textContent = data.worst.name;
    const el = document.getElementById('dash-worst-sub');
    el.textContent = fmt.pctS(data.worst.return_pct);
    el.className = 'card-sub ' + ((data.worst.return_pct || 0) >= 0 ? 'text-pos' : 'text-neg');
  }
  // In Profit + Avg Sharpe
  const profitEl = document.getElementById('dash-profit');
  profitEl.textContent = data.n_profit ?? '—';
  profitEl.className = 'card-value ' +
    (data.n_profit >= 6 ? 'pos' : data.n_profit >= 3 ? 'warn' : 'neg');
  const profitSub = document.getElementById('dash-profit-sub');
  profitSub.textContent = `${data.n_profit}/${data.n_strategies} · ${data.n_loss || 0} in loss`;

  document.getElementById('dash-avg-sharpe').textContent = fmt.num(data.avg_sharpe);

  // Regime card
  const regime = data.regime || {};
  const regimeNames = { 0: 'HG·LI', 1: 'HG·HI', 2: 'LG·LI', 3: 'Stagflation' };
  const regimeEl = document.getElementById('dash-regime');
  if (regime.regime == null) {
    regimeEl.textContent = '—';
    document.getElementById('dash-regime-sub').textContent = 'no rebalance log';
  } else {
    const label = regimeNames[regime.regime] ?? `Regime ${regime.regime}`;
    regimeEl.textContent = label;
    const sub = [];
    if (regime.top1) sub.push(`top1 ${regime.top1}`);
    if (regime.fomc_def) sub.push('FOMC defer');
    document.getElementById('dash-regime-sub').textContent = sub.join(' · ') || regime.date || '';
  }

  document.getElementById('dash-days').textContent = data.days_to_rebalance ?? '—';

  const marketEl = document.getElementById('dash-market');
  marketEl.textContent = data.market_open == null ? 'offline' : data.market_open ? 'OPEN' : 'CLOSED';
  marketEl.className = 'card-value ' + (data.market_open ? 'pos' : data.market_open === false ? 'neg' : 'warn');
  marketEl.style.fontSize = '18px';

  const dh = data.data_health || {};
  const hEl = document.getElementById('dash-health');
  hEl.textContent = (dh.status || '—').toUpperCase();
  hEl.className = 'card-value ' + (dh.status === 'ok' ? 'pos' : dh.status === 'warning' ? 'warn' : 'neg');
  hEl.style.fontSize = '18px';

  const lp = document.getElementById('live-pill');
  lp.textContent = data.live_mode ? 'LIVE' : 'PAPER';
  lp.className = 'status-tag ' + (data.live_mode ? 'live' : 'paper');

  // Ranking table
  const tbody = document.getElementById('dash-rank-body');
  tbody.innerHTML = '';
  data.rows.forEach((r, i) => {
    const retClass = (r.return_pct || 0) >= 0 ? 't-pos' : 't-neg';
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="rank-idx ${i === 0 ? 'r1' : ''}">${i + 1}</td>
      <td>${r.name}</td>
      <td class="hide-mobile"><span class="tier-badge ${r.tier}">${r.tier}</span></td>
      <td class="${retClass}">${fmt.pctS(r.return_pct)}</td>
      <td class="hide-mobile">${fmt.pct(r.bt_cagr)}</td>
      <td>${fmt.num(r.bt_sharpe)}</td>
      <td class="hide-mobile t-neg">${fmt.pct(r.bt_max_dd)}</td>
      <td class="hide-mobile"><span class="status-tag ${r.connected ? 'active' : ''}">${r.connected ? 'connected' : 'offline'}</span></td>
      <td><span class="tracking-chip ${r.tracking || 'pending'}">${trackingLabel(r.tracking)}</span></td>`;
    tbody.appendChild(tr);
  });

  drawLiveEquityChart(data.live_curves || {});

  const alerts = document.getElementById('dash-alerts');
  const issues = (dh.sources || []).filter(s => s.status !== 'ok');
  alerts.innerHTML = !issues.length
    ? '<span class="log-ok">All systems nominal.</span>'
    : issues.map(s => `<div><span class="log-ts">${s.age || '—'}</span><span class="log-warn">${s.status.toUpperCase()}</span> ${s.name} — ${s.path}</div>`).join('');
}

function benchmarkDatasets(compare) {
  const out = [];
  const b = compare.benchmarks || {};
  Object.entries(b).forEach(([label, curve]) => {
    out.push({
      label: label,
      data:  curve.map(p => p.value),
      borderColor: BENCH_COLORS[label] || '#888',
      borderWidth: 1.5,
      borderDash: [5, 4],
      pointRadius: 0,
      tension: 0.1,
    });
  });
  return out;
}

function axisOpts(scale) {
  return scale === 'log'
    ? { type: 'logarithmic', ticks: { font: { size: 9 }, callback: v => `${v}x` }, grid: { color: '#1c1c1c' } }
    : { ticks: { font: { size: 9 }, callback: v => `${v.toFixed(1)}x` }, grid: { color: '#1c1c1c' } };
}

// Mobile-aware chart option helpers
function mobileLegend() {
  return IS_MOBILE()
    ? { display: false }
    : { labels: { font: { size: 10 }, boxWidth: 12 } };
}
function mobileXTicks(maxTicks = 10) {
  return { maxTicksLimit: IS_MOBILE() ? 5 : maxTicks, font: { size: 9 } };
}

function drawLiveEquityChart(lc) {
  destroyChart('dash-chart');
  const canvas = document.getElementById('dash-chart');
  if (!canvas) return;
  const labels = lc.labels || [];
  if (!labels.length) {
    // Fallback: show placeholder text when no live data
    const ctx = canvas.getContext('2d');
    canvas.height = 40; ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#6c6c6c'; ctx.font = '11px JetBrains Mono';
    ctx.fillText('No live portfolio history yet. Data populates after the first rebalance.', 10, 24);
    return;
  }

  // Tier counters for color indexing
  const compareCache = state.compareCache || { strategies: [] };
  const tierByName = {};
  (compareCache.strategies || []).forEach(s => { tierByName[s.name] = s.tier; });

  const tierCounters = { confident: 0, neutral: 0, skeptical: 0 };
  const datasets = Object.entries(lc.strategies || {}).map(([name, col]) => {
    const tier = tierByName[name] || 'confident';
    const idx = tierCounters[tier]++;
    const color = tierColor(tier, idx);
    return {
      label: name,
      data: col,
      borderColor: color,
      backgroundColor: color + '12',
      borderWidth: 1.4,
      pointRadius: 0,
      tension: 0.1,
      spanGaps: true,
    };
  });

  // SPY benchmark dashed
  if (lc.spy && lc.spy.some(v => v != null)) {
    datasets.push({
      label: 'SPY',
      data: lc.spy,
      borderColor: '#f4f4f2',
      borderWidth: 1.6,
      borderDash: [5, 4],
      pointRadius: 0,
      tension: 0.1,
      spanGaps: true,
    });
  }

  state.charts['dash-chart'] = new Chart(canvas, {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: mobileLegend(),
        tooltip: { callbacks: { label: c => `${c.dataset.label}: ${c.parsed.y != null ? '$' + Math.round(c.parsed.y).toLocaleString() : 'n/a'}` } },
      },
      scales: {
        x: { ticks: mobileXTicks(8), grid: { color: '#1c1c1c' } },
        y: state.dashScale === 'log'
          ? { type: 'logarithmic', ticks: { font: { size: 9 }, callback: v => '$' + (v / 1000).toFixed(0) + 'k' }, grid: { color: '#1c1c1c' } }
          : { ticks: { font: { size: 9 }, callback: v => '$' + (v / 1000).toFixed(0) + 'k' }, grid: { color: '#1c1c1c' } },
      },
    },
  });
}

function drawEquityChart(compare) {
  if (!compare) return;
  destroyChart('dash-chart');
  const canvas = document.getElementById('dash-chart');
  if (!canvas) return;

  const filter = state.tierFilter;
  const tierCounters = { confident: 0, neutral: 0, skeptical: 0 };
  const datasets = compare.strategies
    .filter(s => filter === 'all' || s.tier === filter)
    .map(s => {
      const idx = tierCounters[s.tier]++;
      const color = tierColor(s.tier, idx);
      const curve = compare.equity_curves[s.name] || [];
      return {
        label: s.name,
        data: curve.map(p => p.value),
        borderColor: color,
        backgroundColor: color + '20',
        borderWidth: 1.4,
        pointRadius: 0,
        tension: 0.15,
      };
    });
  if (state.benchOn) datasets.push(...benchmarkDatasets(compare));

  state.charts['dash-chart'] = new Chart(canvas, {
    type: 'line',
    data: { labels: compare.dates, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: mobileLegend(),
        tooltip: { callbacks: { label: c => `${c.dataset.label}: ${c.parsed.y != null ? c.parsed.y.toFixed(2) + 'x' : 'n/a'}` } },
      },
      scales: {
        x: { ticks: mobileXTicks(10), grid: { color: '#1c1c1c' } },
        y: axisOpts(state.dashScale),
      },
    },
  });
}

// ─── HORSE RACE ────────────────────────────────────────────────────────────
async function renderHorseRace() {
  const data = await fetchJSON('/api/comparison');
  if (!data) return;
  state.compareCache = data;

  if (!state.dashCache) state.dashCache = await fetchJSON('/api/dashboard');
  const liveByName = {};
  (state.dashCache?.rows || []).forEach(r => { liveByName[r.name] = r; });

  const grid = document.getElementById('hr-cards');
  grid.innerHTML = '';
  const sorted = [...data.strategies].sort((a, b) => {
    const ta = TIER_ORDER.indexOf(a.tier), tb = TIER_ORDER.indexOf(b.tier);
    return ta !== tb ? ta - tb : a.slot - b.slot;
  });
  sorted.forEach((s, i) => {
    const live = liveByName[s.name] || {};
    const ret = live.return_pct;
    const retCls = (ret ?? 0) >= 0 ? 'pos' : 'neg';
    const card = document.createElement('div');
    card.className = `strat-card ${s.tier}`;
    card.style.animationDelay = `${0.02 * i}s`;
    card.innerHTML = `
      <div class="strat-card-head">
        <div>
          <div class="strat-card-slot">SLOT ${s.slot} · <span class="tier-badge ${s.tier}">${s.tier}</span></div>
          <div class="strat-card-name">${s.name}</div>
        </div>
        <span class="tracking-chip ${live.tracking || 'pending'}">${trackingLabel(live.tracking)}</span>
      </div>
      <div class="strat-card-return ${retCls}">${fmt.pctS(ret)}</div>
      <div class="strat-card-sub">live since inception</div>
      <div class="strat-card-meta">
        <span>CAGR <b>${fmt.pct(s.cagr)}</b></span>
        <span>Sharpe <b>${fmt.num(s.sharpe)}</b></span>
        <span>MaxDD <b>${fmt.pct(s.max_dd)}</b></span>
      </div>`;
    card.addEventListener('click', () => setPage('strategy'));
    grid.appendChild(card);
  });

  drawMonthlyReturnsChart(data);
  drawComparisonTable(data);
  drawCorrelation(data);
}

function drawMonthlyReturnsChart(compare) {
  destroyChart('hr-monthly-chart');
  const canvas = document.getElementById('hr-monthly-chart');
  if (!canvas) return;

  // Full backtest window, not just last 60 months — user wants to see the whole race.
  const dates = compare.dates;
  const tierCounters = { confident: 0, neutral: 0, skeptical: 0 };
  const datasets = compare.strategies.map(s => {
    const idx = tierCounters[s.tier]++;
    const color = tierColor(s.tier, idx);
    const curve = compare.equity_curves[s.name] || [];
    return {
      label: s.name,
      data: curve.map(p => p.value),
      borderColor: color,
      borderWidth: 1.2,
      pointRadius: 0,
      tension: 0.15,
    };
  });
  // Benchmarks always on for horse race
  datasets.push(...benchmarkDatasets(compare));

  state.charts['hr-monthly-chart'] = new Chart(canvas, {
    type: 'line',
    data: { labels: dates, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: mobileLegend(),
        tooltip: { callbacks: { label: c => `${c.dataset.label}: ${c.parsed.y != null ? c.parsed.y.toFixed(2) + 'x' : 'n/a'}` } },
      },
      scales: {
        x: { ticks: mobileXTicks(10), grid: { color: '#1c1c1c' } },
        y: axisOpts(state.hrScale),
      },
    },
  });
}

function drawComparisonTable(compare) {
  const tbody = document.getElementById('hr-compare-body');
  const highlights = compare.highlights || {};
  const rows = [...compare.strategies].sort((a, b) => {
    const va = a[state.sortKey], vb = b[state.sortKey];
    const dir = state.sortDir === 'desc' ? -1 : 1;
    if (va == null) return 1;
    if (vb == null) return -1;
    if (typeof va === 'string') return va.localeCompare(vb) * dir;
    return (va - vb) * dir;
  });
  tbody.innerHTML = '';
  rows.forEach(s => {
    const hl = highlights[s.name] || {};
    const cell = (col, val, fmtFn, extra = '') => {
      const cls = (hl[col] ? `cell-${hl[col]} ` : '') + extra;
      return `<td class="${cls.trim()}">${fmtFn(val)}</td>`;
    };
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${s.slot}</td>
      <td>${s.name}</td>
      <td class="hide-mobile"><span class="tier-badge ${s.tier}">${s.tier}</span></td>
      ${cell('cagr',       s.cagr,       v => fmt.pct(v))}
      ${cell('sharpe',     s.sharpe,     v => fmt.num(v))}
      ${cell('max_dd',     s.max_dd,     v => fmt.pct(v))}
      ${cell('sortino',    s.sortino,    v => fmt.num(v),    'hide-mobile')}
      ${cell('win_pct',    s.win_pct,    v => fmt.pct(v, 0), 'hide-mobile')}
      ${cell('worst_year', s.worst_year, v => fmt.pct(v),    'hide-mobile')}`;
    tbody.appendChild(tr);
  });
  document.querySelectorAll('#hr-compare-table thead th[data-sort]').forEach(th => {
    const k = th.dataset.sort;
    th.classList.toggle('sort-asc',  k === state.sortKey && state.sortDir === 'asc');
    th.classList.toggle('sort-desc', k === state.sortKey && state.sortDir === 'desc');
  });
}

function drawCorrelation(compare) {
  const host = document.getElementById('hr-corr');
  const { labels, matrix } = compare.correlation || {};
  if (!labels || !matrix) { host.innerHTML = '<p class="mono text-xs text-muted">No correlation data.</p>'; return; }
  let html = '<table class="corr-table"><thead><tr><th></th>';
  labels.forEach(l => { html += `<th>${l.slice(0, 6)}</th>`; });
  html += '</tr></thead><tbody>';
  matrix.forEach((row, i) => {
    html += `<tr><th>${labels[i].slice(0, 10)}</th>`;
    row.forEach((v, j) => {
      if (i === j) { html += '<td class="corr-cell-diag">—</td>'; return; }
      if (v == null) { html += '<td>—</td>'; return; }
      const cls = v > 0.7 ? 'corr-cell-hi' : v > 0.4 ? 'corr-cell-md' : 'corr-cell-lo';
      html += `<td class="${cls}">${v.toFixed(2)}</td>`;
    });
    html += '</tr>';
  });
  html += '</tbody></table>';
  host.innerHTML = html;
}

// ─── STRATEGY DETAIL ──────────────────────────────────────────────────────
async function renderStrategy() {
  // Need the comparison payload for SPY overlay
  if (!state.compareCache) state.compareCache = await fetchJSON('/api/comparison');
  // Populate dropdown on first render
  const sel = document.getElementById('sd-select');
  if (!sel.options.length) {
    const list = await fetchJSON('/api/strategies');
    (list?.strategies || []).forEach(s => {
      const opt = document.createElement('option');
      opt.value = s.slot;
      opt.textContent = `${s.slot} · ${s.name}`;
      sel.appendChild(opt);
    });
    sel.value = state.sdSlot;
    sel.addEventListener('change', () => { state.sdSlot = parseInt(sel.value, 10); renderStrategy(); });
  }

  const data = await fetchJSON(`/api/strategy/${state.sdSlot}`);
  if (!data) return;

  document.getElementById('sd-tier-badge').textContent = data.tier;
  document.getElementById('sd-tier-badge').className   = 'tier-badge ' + data.tier;
  document.getElementById('sd-login').textContent = data.login ? `login: ${data.login}` : '';
  document.getElementById('sd-desc').textContent  = data.description || '';

  const live = data.live || {};
  const bt   = data.backtest || {};
  document.getElementById('sd-equity').textContent = fmt.money(live.equity);
  document.getElementById('sd-equity-sub').textContent = live.connected ? (live.live ? 'LIVE' : 'paper') : 'offline';
  document.getElementById('sd-return').textContent = fmt.pctS(live.return_pct);
  document.getElementById('sd-return').className   = 'card-value ' + ((live.return_pct || 0) >= 0 ? 'pos' : 'neg');
  document.getElementById('sd-sharpe').textContent = fmt.num(bt.sharpe);
  document.getElementById('sd-cagr').textContent   = fmt.pct(bt.cagr);
  document.getElementById('sd-dd').textContent     = fmt.pct(bt.max_dd);
  document.getElementById('sd-dd').className       = 'card-value neg';
  const nPos = Object.keys(data.positions || {}).length;
  document.getElementById('sd-npos').textContent = nPos;

  // Live vs backtest equity chart
  drawStrategyChart(data);

  // Holdings table
  const posBody = document.getElementById('sd-pos-body');
  const pos = data.positions || {};
  const syms = Object.keys(pos);
  if (!syms.length) {
    posBody.innerHTML = '<tr><td colspan="5" class="empty-state">No live positions.</td></tr>';
  } else {
    posBody.innerHTML = '';
    syms.forEach(sym => {
      const p = pos[sym];
      const pnlCls = (p.pnl || 0) >= 0 ? 't-pos' : 't-neg';
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${sym}</td><td>${fmt.num(p.qty, 2)}</td><td>${fmt.money(p.market_value)}</td><td>${fmt.num(p.avg_entry, 2)}</td><td class="${pnlCls}">${fmt.money(p.pnl)}</td>`;
      posBody.appendChild(tr);
    });
  }

  // Key stats grid + vs-SPY card
  state.sdKsData = { strat: data.key_stats || {}, spy: data.spy_key_stats || {} };
  drawKeyStats(state.sdKsData, state.sdKsCompare || 'strat');
  drawVsSpy(data.vs_spy || {});

  // Expectations tracking (monthly checkpoints vs backtest)
  drawExpectations(data.expectations || {});

  // Rolling sharpe + drawdowns + heatmap + attribution
  drawRollingSharpe(data.rolling_sharpe || []);
  drawDrawdowns(data.drawdowns || [], data.spy_drawdowns || []);
  drawHeatmap(data.monthly_heatmap || []);
  drawAttribution(data.attribution || [], data.has_attribution);

  // Annual returns chart (backtest)
  drawAnnualChart(data.annual_returns || {});

  // Orders
  const ordBody = document.getElementById('sd-orders-body');
  const orders = data.orders || [];
  if (!orders.length) {
    ordBody.innerHTML = '<tr><td colspan="6" class="empty-state">No orders.</td></tr>';
  } else {
    ordBody.innerHTML = '';
    orders.slice(0, 30).forEach(o => {
      const sideCls = o.side === 'buy' ? 't-pos' : 't-neg';
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${(o.submitted || '').slice(0, 16).replace('T', ' ')}</td><td>${o.symbol || ''}</td><td class="${sideCls}">${(o.side || '').toUpperCase()}</td><td>${o.qty || o.notional || ''}</td><td>${o.status || ''}</td><td>${o.filled_avg || '—'}</td>`;
      ordBody.appendChild(tr);
    });
  }

  // Universe tags
  const uniHost = document.getElementById('sd-universe');
  uniHost.innerHTML = (data.universe || []).map(u => `<span class="sym-tag">${u}</span>`).join('');

  // Rationale (markdown-lite → HTML)
  const rat = document.getElementById('sd-rationale');
  rat.innerHTML = mdLite(data.rationale || '*(no rationale on file)*');

  // Spec YAML dump
  document.getElementById('sd-spec').textContent = yamlDump(data.spec || {});
}

function drawStrategyChart(data) {
  destroyChart('sd-chart');
  const canvas = document.getElementById('sd-chart');
  if (!canvas) return;

  const bt = data.backtest_curve || [];
  const hist = (data.portfolio_history || {}).points || [];

  // Normalize live portfolio history to base 1.0 for direct overlay
  const initEq = hist.length ? hist[0].equity : null;
  const liveCurve = initEq ? hist.map(p => ({ date: p.date, value: p.equity / initEq })) : [];

  const datasets = [
    {
      label: 'Backtest', data: bt.map(p => p.value),
      borderColor: '#e8a030', borderWidth: 1.6, pointRadius: 0, tension: 0.15,
    },
  ];
  if (liveCurve.length) {
    datasets.push({
      label: 'Live', data: liveCurve.map(p => p.value),
      borderColor: '#28d4b0', borderWidth: 2, pointRadius: 0, tension: 0.1,
    });
  }
  // SPY overlay — aligned to the backtest date index via state.compareCache
  if (state.compareCache && state.compareCache.benchmarks && state.compareCache.benchmarks.SPY) {
    const spy = state.compareCache.benchmarks.SPY;
    // Only show SPY where backtest dates overlap (they share the same index since they come from the same call)
    datasets.push({
      label: 'SPY', data: spy.map(p => p.value),
      borderColor: '#f4f4f2', borderWidth: 1.3, borderDash: [5, 4], pointRadius: 0, tension: 0.1,
    });
  }
  state.charts['sd-chart'] = new Chart(canvas, {
    type: 'line',
    data: { labels: bt.map(p => p.date), datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: { legend: mobileLegend() },
      scales: {
        x: { ticks: mobileXTicks(10), grid: { color: '#1c1c1c' } },
        y: { ticks: { font: { size: 9 }, callback: v => `${v.toFixed(1)}x` }, grid: { color: '#1c1c1c' } },
      },
    },
  });
}

const KS_ITEMS = [
  { label: 'CAGR',        key: 'cagr',        fmt: v => fmt.pct(v) },
  { label: 'Sharpe',      key: 'sharpe',      fmt: v => fmt.num(v) },
  { label: 'Sortino',     key: 'sortino',     fmt: v => fmt.num(v) },
  { label: 'Calmar',      key: 'calmar',      fmt: v => fmt.num(v) },
  { label: 'Max DD',      key: 'max_dd',      fmt: v => fmt.pct(v), alwaysNeg: true },
  { label: 'Volatility',  key: 'vol_annual',  fmt: v => fmt.pct(v, 1) },
  { label: 'Win Rate',    key: 'win_rate',    fmt: v => fmt.pct(v, 0) },
  { label: 'Avg Month',   key: 'avg_month',   fmt: v => fmt.pctS(v, 2) },
  { label: 'Best Month',  key: 'best_month',  fmt: v => fmt.pctS(v), alwaysPos: true },
  { label: 'Worst Month', key: 'worst_month', fmt: v => fmt.pctS(v), alwaysNeg: true },
  { label: 'Best Year',   key: 'best_year',   fmt: v => fmt.pctS(v), alwaysPos: true },
  { label: 'Worst Year',  key: 'worst_year',  fmt: v => fmt.pctS(v), alwaysNeg: true },
];

function drawKeyStats(ksData, mode = 'strat') {
  const host = document.getElementById('sd-keystats');
  if (!host) return;
  const { strat = {}, spy = {} } = ksData || {};
  const isCompare = mode === 'both';
  host.classList.toggle('ks-compare', isCompare);

  host.innerHTML = KS_ITEMS.map(it => {
    const sv = strat[it.key];
    const pv = spy[it.key];
    const cls = it.alwaysNeg ? 'neg' : it.alwaysPos ? 'pos' : (typeof sv === 'number' && sv < 0 ? 'neg' : '');
    let body = `<div class="ks-val ${cls}">${it.fmt(sv)}</div>`;
    if (isCompare) {
      // diff color: positive diff where higher-is-better
      const higherBetter = !['max_dd', 'worst_month', 'worst_year', 'vol_annual'].includes(it.key);
      let diffCls = '';
      if (typeof sv === 'number' && typeof pv === 'number') {
        const diff = sv - pv;
        diffCls = (higherBetter ? diff > 0 : diff < 0) ? 'pos' : 'neg';
      }
      body += `<div class="ks-spy"><span class="ks-spy-label">SPY</span><span class="ks-spy-val ${diffCls}">${it.fmt(pv)}</span></div>`;
    }
    return `<div class="ks-cell"><div class="ks-label">${it.label}</div>${body}</div>`;
  }).join('');
}

function drawVsSpy(v) {
  const host = document.getElementById('sd-vs-spy');
  if (!host) return;
  if (!v || v.correlation == null) {
    host.innerHTML = '<div class="ks-cell"><div class="ks-label">—</div><div class="ks-val">No SPY overlap.</div></div>';
    return;
  }
  const items = [
    { label: 'CAGR Diff',     v: v.cagr_diff,     fmt: x => fmt.pctS(x, 2) },
    { label: 'Excess Total',  v: v.excess_total,  fmt: x => fmt.pctS(x, 1) },
    { label: 'Alpha (ann)',   v: v.alpha_annual,  fmt: x => fmt.pctS(x, 2) },
    { label: 'Beta',          v: v.beta,          fmt: x => fmt.num(x, 2) },
    { label: 'Correlation',   v: v.correlation,   fmt: x => fmt.num(x, 2) },
    { label: 'Info Ratio',    v: v.info_ratio,    fmt: x => fmt.num(x, 2) },
    { label: 'Up Capture',    v: v.up_capture,    fmt: x => x == null ? '—' : (x * 100).toFixed(0) + '%' },
    { label: 'Down Capture',  v: v.down_capture,  fmt: x => x == null ? '—' : (x * 100).toFixed(0) + '%' },
  ];
  host.innerHTML = items.map(it => {
    let cls = '';
    if (typeof it.v === 'number') {
      // Positive-is-good for all of these except beta (neutral) and down capture (lower-is-better)
      if (it.label === 'Down Capture') cls = it.v > 1 ? 'neg' : 'pos';
      else if (it.label === 'Beta') cls = '';
      else cls = it.v >= 0 ? 'pos' : 'neg';
    }
    return `<div class="ks-cell"><div class="ks-label">${it.label}</div><div class="ks-val ${cls}">${it.fmt(it.v)}</div></div>`;
  }).join('');
}

function drawExpectations(expect) {
  const statusEl = document.getElementById('sd-expect-status');
  const summaryHost = document.getElementById('sd-expect-summary');
  const tbody = document.getElementById('sd-expect-body');
  const tblWrap = document.getElementById('sd-expect-tbl-wrap');

  if (!expect || !statusEl) return;

  // Status chip
  const st = expect.status || 'pending';
  statusEl.textContent = trackingLabel(st);
  statusEl.className = 'tracking-chip ' + st;

  // Summary metrics
  const s = expect.summary || {};
  const summaryItems = [
    { label: 'BT Mean (mo)', v: s.bt_mean, fmt: v => fmt.pctS(v, 2) },
    { label: 'BT Std (mo)',  v: s.bt_std,  fmt: v => fmt.pct(v, 2) },
    { label: 'BT Sharpe',   v: s.bt_sharpe, fmt: v => fmt.num(v) },
    { label: 'Live Sharpe',  v: s.live_sharpe, fmt: v => fmt.num(v) },
    { label: 'Tracking Error', v: s.tracking_error, fmt: v => v == null ? '—' : (v * 100).toFixed(1) + '%' },
    { label: 'Cum. Drift',  v: s.cumulative_drift, fmt: v => v == null ? '—' : `${v >= 0 ? '+' : ''}${(v * 100).toFixed(1)}%` },
    { label: 'Avg Z-Score', v: s.avg_z, fmt: v => v == null ? '—' : v.toFixed(2) },
    { label: 'Live Months',  v: s.n_months, fmt: v => v == null ? '—' : v },
  ];
  summaryHost.innerHTML = summaryItems.map(it => {
    let cls = '';
    if (it.label === 'Avg Z-Score' && typeof it.v === 'number') {
      cls = Math.abs(it.v) < 1 ? 'pos' : Math.abs(it.v) < 2 ? 'warn' : 'neg';
    }
    if (it.label === 'Cum. Drift' && typeof it.v === 'number') {
      cls = it.v >= 0 ? 'pos' : 'neg';
    }
    return `<div class="ks-cell"><div class="ks-label">${it.label}</div><div class="ks-val ${cls}">${it.fmt(it.v)}</div></div>`;
  }).join('');

  // Monthly checkpoints table
  const months = expect.months || [];
  if (!months.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="empty-state">Waiting for first completed month after rebalance.</td></tr>';
  } else {
    tbody.innerHTML = '';
    months.slice().reverse().forEach(m => {
      const tr = document.createElement('tr');
      const retCls = (m.live_return || 0) >= 0 ? 't-pos' : 't-neg';
      const zCls = Math.abs(m.z_score) < 1 ? 't-pos' : Math.abs(m.z_score) < 2 ? 't-warn' : 't-neg';
      tr.innerHTML = `
        <td>${m.date}</td>
        <td class="${retCls}">${fmt.pctS(m.live_return, 2)}</td>
        <td>${fmt.pctS(m.bt_mean, 2)}</td>
        <td class="${zCls}">${m.z_score != null ? m.z_score.toFixed(2) : '—'}</td>
        <td><span class="tracking-chip ${m.status}">${trackingLabel(m.status)}</span></td>`;
      tbody.appendChild(tr);
    });
  }

  // Confidence band chart
  drawExpectationBand(expect.band || {});
}

function drawExpectationBand(band) {
  destroyChart('sd-expect-chart');
  const canvas = document.getElementById('sd-expect-chart');
  if (!canvas || !band.dates || !band.dates.length) return;

  const datasets = [];

  // 2-sigma band (filled between upper and lower)
  if (band.upper_2s) {
    datasets.push({
      label: '+2σ',
      data: band.upper_2s,
      borderColor: 'rgba(232,85,85,0.25)',
      backgroundColor: 'rgba(232,85,85,0.04)',
      borderWidth: 1, borderDash: [3, 3], pointRadius: 0, tension: 0.2,
      fill: '+1',
    });
  }
  if (band.lower_2s) {
    datasets.push({
      label: '-2σ',
      data: band.lower_2s,
      borderColor: 'rgba(232,85,85,0.25)',
      backgroundColor: 'rgba(232,85,85,0.04)',
      borderWidth: 1, borderDash: [3, 3], pointRadius: 0, tension: 0.2,
      fill: false,
    });
  }

  // 1-sigma band (filled between upper and lower)
  if (band.upper_1s) {
    datasets.push({
      label: '+1σ',
      data: band.upper_1s,
      borderColor: 'rgba(232,160,48,0.35)',
      backgroundColor: 'rgba(232,160,48,0.06)',
      borderWidth: 1, borderDash: [4, 3], pointRadius: 0, tension: 0.2,
      fill: '+1',
    });
  }
  if (band.lower_1s) {
    datasets.push({
      label: '-1σ',
      data: band.lower_1s,
      borderColor: 'rgba(232,160,48,0.35)',
      backgroundColor: 'rgba(232,160,48,0.06)',
      borderWidth: 1, borderDash: [4, 3], pointRadius: 0, tension: 0.2,
      fill: false,
    });
  }

  // Expected (center line)
  if (band.expected) {
    datasets.push({
      label: 'Expected',
      data: band.expected,
      borderColor: '#6c6c6c',
      borderWidth: 1.5, borderDash: [6, 4], pointRadius: 0, tension: 0.2,
      fill: false,
    });
  }

  // Live equity
  if (band.live) {
    datasets.push({
      label: 'Live',
      data: band.live,
      borderColor: '#28d4b0',
      borderWidth: 2.5, pointRadius: 3, pointBackgroundColor: '#28d4b0',
      tension: 0.1, spanGaps: false,
      fill: false,
    });
  }

  state.charts['sd-expect-chart'] = new Chart(canvas, {
    type: 'line',
    data: { labels: band.dates, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: mobileLegend(),
        tooltip: {
          callbacks: {
            label: c => {
              const v = c.parsed.y;
              return v != null ? `${c.dataset.label}: $${Math.round(v).toLocaleString()}` : '';
            },
          },
        },
      },
      scales: {
        x: { ticks: mobileXTicks(8), grid: { color: '#1c1c1c' } },
        y: { ticks: { font: { size: 9 }, callback: v => '$' + (v / 1000).toFixed(0) + 'k' }, grid: { color: '#1c1c1c' } },
      },
    },
  });
}

function drawRollingSharpe(data) {
  destroyChart('sd-rs-chart');
  const canvas = document.getElementById('sd-rs-chart');
  if (!canvas) return;
  const labels = data.map(p => p.date);
  const stratData = data.map(p => p.strategy);
  const spyData   = data.map(p => p.spy);
  const datasets = [{
    label: 'Strategy',
    data: stratData,
    borderColor: '#e8a030',
    backgroundColor: 'rgba(232,160,48,0.08)',
    borderWidth: 1.5, pointRadius: 0, tension: 0.15, fill: 'origin',
  }];
  if (spyData.some(v => v != null)) {
    datasets.push({
      label: 'SPY', data: spyData,
      borderColor: '#f4f4f2', borderWidth: 1.2, borderDash: [5, 4],
      pointRadius: 0, tension: 0.15,
    });
  }
  state.charts['sd-rs-chart'] = new Chart(canvas, {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: mobileLegend(),
        tooltip: { callbacks: { label: c => `${c.dataset.label}: ${c.parsed.y != null ? c.parsed.y.toFixed(2) : 'n/a'}` } },
      },
      scales: {
        x: { ticks: mobileXTicks(10), grid: { color: '#1c1c1c' } },
        y: { ticks: { font: { size: 9 } }, grid: { color: '#1c1c1c' },
             suggestedMin: -1, suggestedMax: 3 },
      },
    },
  });
}

function drawDrawdowns(data, spyData) {
  destroyChart('sd-dd-chart');
  const canvas = document.getElementById('sd-dd-chart');
  if (!canvas) return;
  const labels = data.map(p => p.date);
  const vals   = data.map(p => (p.dd != null ? p.dd * 100 : null));

  const datasets = [{
    label: 'Strategy',
    data: vals,
    borderColor: '#e85555',
    backgroundColor: 'rgba(232,85,85,0.18)',
    borderWidth: 1.4, pointRadius: 0, tension: 0.15, fill: 'origin',
  }];

  // SPY overlay — aligned by date index
  if (spyData && spyData.length) {
    const spyByDate = {};
    spyData.forEach(p => { spyByDate[p.date] = (p.dd != null ? p.dd * 100 : null); });
    const spyAligned = labels.map(d => (d in spyByDate ? spyByDate[d] : null));
    datasets.push({
      label: 'SPY',
      data: spyAligned,
      borderColor: '#f4f4f2',
      borderWidth: 1.2,
      borderDash: [5, 4],
      pointRadius: 0,
      tension: 0.15,
      fill: false,
      spanGaps: true,
    });
  }

  state.charts['sd-dd-chart'] = new Chart(canvas, {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: mobileLegend(),
        tooltip: { callbacks: { label: c => `${c.dataset.label}: ${c.parsed.y != null ? c.parsed.y.toFixed(1) + '%' : 'n/a'}` } },
      },
      scales: {
        x: { ticks: mobileXTicks(10), grid: { color: '#1c1c1c' } },
        y: { ticks: { font: { size: 9 }, callback: v => `${v.toFixed(0)}%` }, grid: { color: '#1c1c1c' }, max: 0 },
      },
    },
  });
}

function heatmapColor(ret) {
  // ret in decimal (e.g. 0.05 = 5%). Full scale ±15%.
  if (ret == null) return '';
  const clip = Math.max(-0.15, Math.min(0.15, ret));
  const intensity = Math.abs(clip) / 0.15;  // 0..1
  const rgb = ret >= 0
    ? `40, 212, 176`   // teal
    : `232, 85, 85`;   // red
  return `background-color: rgba(${rgb}, ${0.12 + 0.72 * intensity}); color: ${intensity > 0.45 ? '#0a0a0a' : 'var(--text)'};`;
}

function drawHeatmap(data) {
  const host = document.getElementById('sd-heatmap');
  if (!host) return;
  if (!data.length) { host.innerHTML = '<p class="mono text-xs text-muted">No data.</p>'; return; }
  // Pivot into {year: {month: ret}}
  const pivot = {};
  const years = new Set();
  data.forEach(p => {
    pivot[p.year] = pivot[p.year] || {};
    pivot[p.year][p.month] = p.ret;
    years.add(p.year);
  });
  const yrs = [...years].sort();
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  let html = '<table class="heatmap"><thead><tr><th class="yr">Year</th>';
  months.forEach(m => { html += `<th>${m}</th>`; });
  html += '<th>Total</th></tr></thead><tbody>';
  yrs.forEach(y => {
    html += `<tr><th class="yr">${y}</th>`;
    let total = 1.0; let hasAny = false;
    for (let m = 1; m <= 12; m++) {
      const r = pivot[y][m];
      if (r == null) {
        html += '<td class="hm-empty">—</td>';
      } else {
        total *= (1 + r); hasAny = true;
        html += `<td style="${heatmapColor(r)}">${(r * 100).toFixed(1)}</td>`;
      }
    }
    const yrRet = hasAny ? total - 1 : null;
    html += yrRet == null ? '<td class="hm-year">—</td>'
                          : `<td class="hm-year" style="${heatmapColor(yrRet / 2)}">${(yrRet * 100).toFixed(1)}</td>`;
    html += '</tr>';
  });
  html += '</tbody></table>';
  host.innerHTML = html;
}

function drawAttribution(data, hasAttribution) {
  destroyChart('sd-attr-chart');
  const canvas = document.getElementById('sd-attr-chart');
  const card   = document.getElementById('sd-attr-card');
  const note   = document.getElementById('sd-attr-note');
  if (!canvas || !card) return;

  if (!hasAttribution || !data.length) {
    canvas.style.display = 'none';
    note.textContent = 'Component attribution is only available for OPTIMIZED (slot 1), which was fit by the autonomous suite. Other slots lack per-layer return decomposition.';
    return;
  }
  canvas.style.display = '';
  note.textContent = 'Per-year contribution from each component layer. Positive bars lift total CAGR, negative drag it down. Total bar = sum of all components.';

  const years   = data.map(d => d.year);
  const components = [
    { key: 'base',     label: 'Base Momentum', color: '#e8a030' },
    { key: 'regime',   label: 'Regime Switch', color: '#5898e8' },
    { key: 'inv_vol',  label: 'Inv-Vol',       color: '#28d4b0' },
    { key: 'sma_gate', label: 'SMA Gate',      color: '#a878e8' },
    { key: 'm26',      label: 'FOMC Defer',    color: '#c47e1a' },
  ];
  const datasets = components.map(c => ({
    label: c.label,
    data: data.map(d => (d[c.key] ?? 0) * 100),
    backgroundColor: c.color + 'cc',
    borderColor: c.color,
    borderWidth: 1,
    stack: 'comp',
  }));
  // Overlay total as a line
  datasets.push({
    type: 'line',
    label: 'Total',
    data: data.map(d => (d.total ?? 0) * 100),
    borderColor: '#f4f4f2',
    borderWidth: 2,
    pointRadius: 3,
    pointBackgroundColor: '#f4f4f2',
    tension: 0,
    stack: undefined,
  });

  state.charts['sd-attr-chart'] = new Chart(canvas, {
    data: { labels: years, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { labels: { boxWidth: 10, font: { size: 9 } } },
        tooltip: { mode: 'index', intersect: false,
                   callbacks: { label: c => `${c.dataset.label}: ${c.parsed.y.toFixed(1)}%` } },
      },
      scales: {
        x: { stacked: true, ticks: { font: { size: 9 } }, grid: { display: false } },
        y: { stacked: true, ticks: { font: { size: 9 }, callback: v => `${v.toFixed(0)}%` }, grid: { color: '#1c1c1c' } },
      },
    },
  });
}

function drawAnnualChart(annual) {
  destroyChart('sd-annual-chart');
  const canvas = document.getElementById('sd-annual-chart');
  if (!canvas) return;
  const years = Object.keys(annual).sort();
  const vals  = years.map(y => annual[y] * 100);
  state.charts['sd-annual-chart'] = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: years,
      datasets: [{
        label: 'Annual Return',
        data: vals,
        backgroundColor: vals.map(v => v >= 0 ? '#28d4b0' : '#e85555'),
        borderWidth: 0,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { font: { size: 9 } }, grid: { display: false } },
        y: { ticks: { font: { size: 9 }, callback: v => `${v.toFixed(0)}%` }, grid: { color: '#1c1c1c' } },
      },
    },
  });
}

function mdLite(md) {
  // Tiny markdown subset: **bold**, `code`, paragraphs, - bullets
  const lines = md.split('\n');
  let html = ''; let inList = false;
  const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const inline = s => esc(s)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>');
  for (const raw of lines) {
    const line = raw.trimEnd();
    if (!line.trim()) { if (inList) { html += '</ul>'; inList = false; } html += ''; continue; }
    if (/^[-*]\s+/.test(line)) {
      if (!inList) { html += '<ul>'; inList = true; }
      html += `<li>${inline(line.replace(/^[-*]\s+/, ''))}</li>`;
    } else {
      if (inList) { html += '</ul>'; inList = false; }
      html += `<p>${inline(line)}</p>`;
    }
  }
  if (inList) html += '</ul>';
  return html;
}

function yamlDump(obj, indent = 0) {
  const pad = '  '.repeat(indent);
  if (obj == null) return 'null';
  if (Array.isArray(obj)) {
    if (!obj.length) return '[]';
    return obj.map(v => {
      if (v && typeof v === 'object') return `${pad}- \n${yamlDump(v, indent + 1)}`;
      return `${pad}- ${v}`;
    }).join('\n');
  }
  if (typeof obj === 'object') {
    return Object.entries(obj).map(([k, v]) => {
      if (v && typeof v === 'object') {
        const nested = yamlDump(v, indent + 1);
        return `${pad}${k}:\n${nested}`;
      }
      return `${pad}${k}: ${v}`;
    }).join('\n');
  }
  return `${pad}${obj}`;
}

// ─── ACCOUNTS ──────────────────────────────────────────────────────────────
async function renderAccounts() {
  // Mark active chip
  document.querySelectorAll('#acc-tier-chips .chip').forEach(c =>
    c.classList.toggle('active', c.dataset.tier === state.accTier));

  const data = await fetchJSON(`/api/account/${state.accTier}`);
  if (!data) return;

  let totalEq = 0, totalPos = 0, totalOrd = 0, retSum = 0, retN = 0;
  const host = document.getElementById('acc-cards');
  host.innerHTML = '';

  (data.strategies || []).forEach(s => {
    const live = s.live || {};
    const pos  = s.positions || {};
    const orders = s.orders || [];
    totalEq  += live.equity || 0;
    totalPos += Object.keys(pos).length;
    totalOrd += orders.filter(o => (o.status || '').match(/new|open|accepted|pending/)).length;
    if (live.return_pct != null) { retSum += live.return_pct; retN++; }

    const retCls = (live.return_pct || 0) >= 0 ? 'pos' : 'neg';
    const card = document.createElement('div');
    card.className = 'acc-strat-card';
    let posHtml = '<tr><td colspan="5" class="empty-state">No positions.</td></tr>';
    const syms = Object.keys(pos);
    if (syms.length) {
      posHtml = syms.map(sym => {
        const p = pos[sym];
        const pnlCls = (p.pnl || 0) >= 0 ? 't-pos' : 't-neg';
        return `<tr><td>${sym}</td><td>${fmt.num(p.qty, 1)}</td><td>${fmt.money(p.market_value)}</td><td>${fmt.num(p.avg_entry, 2)}</td><td class="${pnlCls}">${fmt.money(p.pnl)}</td></tr>`;
      }).join('');
    }
    let ordHtml = '<tr><td colspan="5" class="empty-state">No orders.</td></tr>';
    if (orders.length) {
      ordHtml = orders.slice(0, 10).map(o => {
        const sideCls = o.side === 'buy' ? 't-pos' : 't-neg';
        return `<tr><td>${(o.submitted || '').slice(5, 16).replace('T', ' ')}</td><td>${o.symbol || ''}</td><td class="${sideCls}">${(o.side || '').toUpperCase()}</td><td>${o.status || ''}</td><td>${o.filled_avg || '—'}</td></tr>`;
      }).join('');
    }
    card.innerHTML = `
      <div class="acc-strat-head">
        <div>
          <div class="acc-strat-name">${s.name}</div>
          <div class="acc-strat-sub">slot ${s.slot} · ${live.connected ? (live.live ? 'LIVE' : 'paper') : 'offline'}</div>
        </div>
        <div style="text-align:right">
          <div class="acc-strat-eq ${retCls}">${fmt.money(live.equity)}</div>
          <div class="acc-strat-sub">${fmt.pctS(live.return_pct)} · cash ${fmt.money(live.cash)}</div>
        </div>
      </div>
      <div class="acc-strat-grid">
        <div>
          <div class="card-label mb-8">Positions</div>
          <table><thead><tr><th>Sym</th><th>Qty</th><th>Value</th><th>Avg</th><th>P&amp;L</th></tr></thead><tbody>${posHtml}</tbody></table>
        </div>
        <div>
          <div class="card-label mb-8">Recent Orders</div>
          <table><thead><tr><th>Time</th><th>Sym</th><th>Side</th><th>Status</th><th>Avg</th></tr></thead><tbody>${ordHtml}</tbody></table>
        </div>
      </div>`;
    host.appendChild(card);
  });

  const avgRet = retN ? retSum / retN : null;
  document.getElementById('acc-equity').textContent = fmt.money(totalEq);
  document.getElementById('acc-return').textContent = fmt.pctS(avgRet);
  document.getElementById('acc-return').className   = 'card-value ' + ((avgRet || 0) >= 0 ? 'pos' : 'neg');
  document.getElementById('acc-npos').textContent = totalPos;
  document.getElementById('acc-nord').textContent = totalOrd;
  document.getElementById('acc-tier-sub').textContent = `${(data.strategies || []).length} strategies · ${state.accTier}`;
}

// ─── Secondary pages ──────────────────────────────────────────────────────
async function renderDataHealth() {
  const data = await fetchJSON('/api/data/health');
  if (!data) return;

  // Banner
  const banner = document.getElementById('dh-banner');
  banner.className = 'sys-banner' + (data.status === 'ok' ? ' ok' : '');
  banner.textContent = data.status === 'ok' ? 'Data Nominal'
                     : data.status === 'warning' ? 'Data Warnings'
                     : 'Data Alert';

  // Top summary metric cards
  const sum = data.summary || {};
  document.getElementById('dh-m-files').textContent   = sum.total_files ?? '—';
  document.getElementById('dh-m-size').textContent    = sum.total_size_fmt ?? '—';
  document.getElementById('dh-m-sources').textContent = sum.n_sources ?? '—';
  document.getElementById('dh-m-etfs').textContent    = sum.n_required_etfs ?? '—';
  const etfsSub = [];
  if (sum.n_missing_etfs) etfsSub.push(`${sum.n_missing_etfs} missing`);
  if (sum.n_stale_etfs)   etfsSub.push(`${sum.n_stale_etfs} stale`);
  document.getElementById('dh-m-etfs-sub').textContent = etfsSub.join(' · ') || 'all fresh';
  document.getElementById('dh-m-etfs-sub').className   =
    'card-sub ' + (sum.n_missing_etfs ? 'text-neg' : sum.n_stale_etfs ? 'text-acc' : 'text-pos');
  document.getElementById('dh-m-fred').textContent    = (data.fred_series || []).length;
  const statusEl = document.getElementById('dh-m-status');
  statusEl.textContent = (data.status || '—').toUpperCase();
  statusEl.className   = 'card-value ' + (data.status === 'ok' ? 'pos' : data.status === 'warning' ? 'warn' : 'neg');
  statusEl.style.fontSize = '18px';

  // Sources table
  const srcBody = document.getElementById('dh-src-body');
  srcBody.innerHTML = '';
  (data.sources || []).forEach(s => {
    const cls = s.status === 'ok' ? 'done' : s.status === 'stale' ? 'running' : 'error';
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${s.name}<div class="mono text-xs text-muted">${s.path}</div></td>
      <td class="hide-mobile">${s.kind}</td>
      <td>${s.n_files}</td>
      <td class="hide-mobile">${s.size_fmt}</td>
      <td>${s.age}</td>
      <td><span class="status-tag ${cls}">${s.status}</span></td>`;
    srcBody.appendChild(tr);
  });

  // Required ETFs
  const etfBody = document.getElementById('dh-etf-body');
  const etfs = data.required_etfs || [];
  if (!etfs.length) {
    etfBody.innerHTML = '<tr><td colspan="4" class="empty-state">No strategies loaded.</td></tr>';
  } else {
    etfBody.innerHTML = '';
    etfs.forEach(e => {
      const cls = e.status === 'ok' ? 'done' : e.status === 'stale' ? 'running' : 'error';
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${e.symbol}</td><td>${e.latest || '—'}</td><td>${e.age}</td><td><span class="status-tag ${cls}">${e.status}</span></td>`;
      etfBody.appendChild(tr);
    });
  }

  // FRED series
  const fredBody = document.getElementById('dh-fred-body');
  const fred = data.fred_series || [];
  if (!fred.length) {
    fredBody.innerHTML = '<tr><td colspan="4" class="empty-state">No FRED series.</td></tr>';
  } else {
    fredBody.innerHTML = '';
    fred.forEach(f => {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${f.code}</td><td class="hide-mobile">${f.label}</td><td>${f.latest || '—'}</td><td>${f.age}</td>`;
      fredBody.appendChild(tr);
    });
  }
}

async function renderRegime() {
  const data = await fetchJSON('/api/data/regime');
  const host = document.getElementById('regime-body');
  if (!data || data.regime == null) { host.innerHTML = '<p class="mono text-xs text-muted">No regime data yet (no rebalance log).</p>'; return; }
  host.innerHTML = `
    <div class="kv-list">
      <div class="kv-row"><span class="kv-key">Current Regime</span><span class="kv-val">${data.regime}</span></div>
      <div class="kv-row"><span class="kv-key">Predicted</span><span class="kv-val">${data.predicted}</span></div>
      <div class="kv-row"><span class="kv-key">Lookback</span><span class="kv-val">${data.lookback ?? '—'}d</span></div>
      <div class="kv-row"><span class="kv-key">SMA Distance</span><span class="kv-val">${data.sma_dist != null ? (data.sma_dist * 100).toFixed(2) + '%' : '—'}</span></div>
      <div class="kv-row"><span class="kv-key">FOMC Defer</span><span class="kv-val">${data.fomc_def ? 'yes' : 'no'}</span></div>
      <div class="kv-row"><span class="kv-key">Top-1</span><span class="kv-val">${data.top1 ?? '—'}</span></div>
      <div class="kv-row"><span class="kv-key">Top-K</span><span class="kv-val">${(data.topk || []).join(', ') || '—'}</span></div>
      <div class="kv-row"><span class="kv-key">Last Rebalance</span><span class="kv-val">${data.date ?? '—'}</span></div>
    </div>`;
}

async function renderRebalance() {
  // Log history table
  const data = await fetchJSON('/api/rebalance/log');
  const host = document.getElementById('reb-body');
  if (!data || !data.entries?.length) {
    host.innerHTML = '<p class="mono text-xs text-muted">No rebalance history.</p>';
  } else {
    let html = '<div class="tbl-wrap" style="border:none"><table><thead><tr><th>Date</th><th>Top-1</th><th>Top-K</th><th>Lookback</th><th>Regime</th><th>FOMC</th><th>Weights</th></tr></thead><tbody>';
    data.entries.slice(0, 50).forEach(e => {
      const w = Object.entries(e.target_weights || {}).map(([k, v]) => `${k} ${(v * 100).toFixed(0)}%`).join(', ');
      html += `<tr><td>${e.date}</td><td>${e.top1 ?? '—'}</td><td>${(e.topk || []).join(',')}</td><td>${e.lookback ?? '—'}d</td><td>${e.regime_info?.current ?? '—'}</td><td>${e.fomc_deferred ? 'def' : '—'}</td><td class="t-mono">${w}</td></tr>`;
    });
    host.innerHTML = html + '</tbody></table></div>';
  }

  // Process status + log polling
  await refreshRebalanceStatus();
  if (!state.rebPoll) {
    state.rebPoll = setInterval(refreshRebalanceStatus, 2000);
  }
}

async function refreshRebalanceStatus() {
  const [status, log] = await Promise.all([
    fetchJSON('/api/process/status'),
    fetchJSON('/api/process/log'),
  ]);
  const statusEl = document.getElementById('reb-status');
  const pidEl    = document.getElementById('reb-pid');
  const stopBtn  = document.getElementById('btn-reb-stop');
  const dryBtn   = document.getElementById('btn-reb-dry');
  const liveBtn  = document.getElementById('btn-reb-live');

  if (status?.running) {
    statusEl.textContent = status.name || 'Running';
    statusEl.className   = 'status-tag running';
    pidEl.textContent    = `pid ${status.pid} · ${status.uptime}s`;
    stopBtn.disabled = false;
    dryBtn.disabled  = true;
    liveBtn.disabled = true;
  } else {
    const rc = status?.rc;
    statusEl.textContent = rc == null ? 'Idle' : rc === 0 ? 'Done' : `Exit ${rc}`;
    statusEl.className   = 'status-tag ' + (rc == null ? '' : rc === 0 ? 'done' : 'error');
    pidEl.textContent    = '';
    stopBtn.disabled = true;
    dryBtn.disabled  = false;
    // Live button stays disabled — enabled only when the server is in LIVE mode (see below).
  }

  const panel = document.getElementById('reb-log-panel');
  const lines = log?.lines || [];
  if (!lines.length) {
    panel.innerHTML = '<span class="log-plain">No run yet.</span>';
  } else {
    panel.innerHTML = lines.map(l => {
      const cls = l.rc === 0 ? 'log-ok' : l.rc != null ? 'log-err' :
                  /error|traceback/i.test(l.msg) ? 'log-err' :
                  /warn/i.test(l.msg) ? 'log-warn' : 'log-plain';
      return `<div><span class="log-ts">${l.t}</span><span class="${cls}">${escapeHtml(l.msg)}</span></div>`;
    }).join('');
    panel.scrollTop = panel.scrollHeight;
  }

  // Enable Live button only if server-side live mode flag is on (from last dashboard snapshot).
  if (state.dashCache?.live_mode && !status?.running) {
    liveBtn.disabled = false;
  }
}

function escapeHtml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

async function startRebalance(dryRun) {
  if (!dryRun && !confirm('Run LIVE rebalance? This will place real orders against your Alpaca accounts.')) return;
  const r = await fetch(`/api/rebalance/run?dry_run=${dryRun}`, { method: 'POST' });
  if (!r.ok) { alert('Failed to start: ' + r.status); return; }
  refreshRebalanceStatus();
}

async function stopRebalance() {
  await fetch('/api/process/stop', { method: 'POST' });
  refreshRebalanceStatus();
}

function fmtSecs(s) {
  if (s == null) return '—';
  const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
  return (d ? `${d}d ` : '') + `${h}h ${m}m`;
}

async function renderSystem() {
  const d = await fetchJSON('/api/system/health');
  if (!d) return;

  // Top cards
  document.getElementById('sys-host').textContent   = d.hostname || '—';
  document.getElementById('sys-os').textContent     = d.os || '';
  document.getElementById('sys-srv-up').textContent = fmtSecs(d.server_uptime_s);
  document.getElementById('sys-srv-mode').textContent = d.live_mode ? 'LIVE' : 'paper';
  document.getElementById('sys-pc-up').textContent  = d.uptime || '—';
  document.getElementById('sys-np').textContent     = d.n_processes ?? '—';
  document.getElementById('sys-nt').textContent     = d.n_threads ? `${d.n_threads} threads` : '';
  document.getElementById('sys-temp').textContent   = d.temp_c != null ? `${d.temp_c}°C` : '—';
  document.getElementById('sys-py').textContent     = d.python ? `v${d.python}` : '—';

  // Overall banner
  const warnCpu = (d.cpu_pct || 0) > 90, warnMem = (d.mem_pct || 0) > 90, warnDisk = (d.disk_pct || 0) > 92;
  const banner = document.getElementById('sys-banner');
  if (warnCpu || warnMem || warnDisk) {
    banner.className = 'sys-banner'; banner.textContent = 'Resource Pressure';
  } else {
    banner.className = 'sys-banner ok'; banner.textContent = 'Skylark Nominal';
  }

  // CPU
  document.getElementById('sys-cpu-pct').textContent = `${(d.cpu_pct ?? 0).toFixed(0)}%`;
  const meta = [];
  if (d.cpu_count) meta.push(`${d.cpu_count} logical`);
  if (d.cpu_physical) meta.push(`${d.cpu_physical} cores`);
  if (d.cpu_ghz) meta.push(`${d.cpu_ghz} GHz`);
  document.getElementById('sys-cpu-meta').textContent = meta.join(' · ');

  const bar = document.getElementById('sys-cpu-bar');
  bar.style.width = `${Math.min(d.cpu_pct || 0, 100)}%`;
  bar.className = 'bar-fill' + ((d.cpu_pct || 0) > 85 ? ' crit' : (d.cpu_pct || 0) > 65 ? ' warn' : '');

  const grid = document.getElementById('sys-core-grid');
  grid.innerHTML = '';
  (d.cpu_per_core || []).forEach((v, i) => {
    const cell = document.createElement('div');
    const cls = v > 85 ? 'crit' : v > 65 ? 'warn' : '';
    cell.className = `core-cell ${cls}`;
    cell.style.setProperty('--fill', `${v}%`);
    cell.innerHTML = `<span class="core-label">C${i}</span><span class="core-val">${v.toFixed(0)}%</span>`;
    grid.appendChild(cell);
  });

  // Memory
  document.getElementById('sys-mem-pct').textContent = `${(d.mem_pct ?? 0).toFixed(0)}%`;
  document.getElementById('sys-mem-sub').textContent = `${d.mem_used_gb ?? 0} / ${d.mem_total_gb ?? 0} GB · ${d.mem_free_gb ?? 0} GB free`;
  const mbar = document.getElementById('sys-mem-bar');
  mbar.style.width = `${Math.min(d.mem_pct || 0, 100)}%`;
  mbar.className = 'bar-fill' + ((d.mem_pct || 0) > 90 ? ' crit' : (d.mem_pct || 0) > 75 ? ' warn' : '');

  // Swap
  document.getElementById('sys-swap-sub').textContent = `${d.swap_used_gb ?? 0} GB · ${(d.swap_pct ?? 0).toFixed(0)}%`;
  const sbar = document.getElementById('sys-swap-bar');
  sbar.style.width = `${Math.min(d.swap_pct || 0, 100)}%`;
  sbar.className = 'bar-fill' + ((d.swap_pct || 0) > 50 ? ' warn' : '');

  // Disk
  document.getElementById('sys-disk-sub').textContent = `${d.disk_used_gb ?? 0} / ${d.disk_total_gb ?? 0} GB · ${d.disk_free_gb ?? 0} GB free`;
  const dbar = document.getElementById('sys-disk-bar');
  dbar.style.width = `${Math.min(d.disk_pct || 0, 100)}%`;
  dbar.className = 'bar-fill' + ((d.disk_pct || 0) > 92 ? ' crit' : (d.disk_pct || 0) > 80 ? ' warn' : '');

  // GPU
  const gpuCard = document.getElementById('sys-gpu-card');
  const gpuList = document.getElementById('sys-gpu-list');
  if (d.gpus && d.gpus.length) {
    gpuCard.style.display = '';
    gpuList.innerHTML = '';
    d.gpus.forEach(g => {
      const row = document.createElement('div');
      row.className = 'gpu-row';
      row.innerHTML = `
        <div class="gpu-head">
          <span class="gpu-name">${g.name}</span>
          <span class="gpu-stats">${g.util_pct}% util · ${g.mem_used_gb}/${g.mem_total_gb} GB${g.temp_c != null ? ` · ${g.temp_c}°C` : ''}</span>
        </div>
        <div class="bar-track"><div class="bar-fill ${g.util_pct > 85 ? 'crit' : g.util_pct > 65 ? 'warn' : ''}" style="width:${g.util_pct}%"></div></div>`;
      gpuList.appendChild(row);
    });
  } else {
    gpuCard.style.display = 'none';
  }

  // Network
  document.getElementById('sys-net-sent').textContent = d.net_sent_gb != null ? `${d.net_sent_gb} GB` : '—';
  document.getElementById('sys-net-recv').textContent = d.net_recv_gb != null ? `${d.net_recv_gb} GB` : '—';

  // Process
  const p = d.process || {};
  document.getElementById('sys-proc-name').textContent = p.running ? p.name : 'idle';
  document.getElementById('sys-proc-pid').textContent  = p.pid ?? '—';
  document.getElementById('sys-proc-up').textContent   = p.uptime ? `${p.uptime}s` : '—';

  // Access log table
  const body = document.getElementById('sys-access-body');
  const entries = d.access_log || [];
  if (!entries.length) {
    body.innerHTML = '<tr><td colspan="5" class="empty-state">No recent requests.</td></tr>';
  } else {
    body.innerHTML = '';
    entries.slice(0, 30).forEach(e => {
      const cls = e.status >= 500 ? 't-neg' : e.status >= 400 ? 't-warn' : 't-pos';
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${e.t}</td><td>${e.method}</td><td class="t-mono">${e.path}</td><td class="${cls}">${e.status}</td><td>${e.ms}</td>`;
      body.appendChild(tr);
    });
  }
}

// ─── Wiring ────────────────────────────────────────────────────────────────
function wireNav() {
  document.querySelectorAll('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => {
      setPage(btn.dataset.page);
      // Auto-close sidebar on mobile after navigating
      if (window.innerWidth <= 768) closeSidebar();
    });
  });

  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebar-overlay');
  const hamb    = document.getElementById('btn-hamburger');
  const openSidebar  = () => { sidebar?.classList.add('open'); overlay?.classList.add('visible'); };
  const closeSidebar = () => { sidebar?.classList.remove('open'); overlay?.classList.remove('visible'); };
  if (hamb) hamb.addEventListener('click', () => {
    if (sidebar?.classList.contains('open')) closeSidebar();
    else openSidebar();
  });
  if (overlay) overlay.addEventListener('click', closeSidebar);
  // Expose for other wiring
  window.__sky_closeSidebar = closeSidebar;
  document.getElementById('btn-refresh').addEventListener('click', () => {
    state.dashCache = null;
    state.compareCache = null;
    loadPage(state.page);
  });
  document.querySelectorAll('#dash-tier-filter .chip').forEach(c => {
    c.addEventListener('click', () => {
      document.querySelectorAll('#dash-tier-filter .chip').forEach(x => x.classList.remove('active'));
      c.classList.add('active');
      state.tierFilter = c.dataset.tierFilter;
      if (state.compareCache) drawEquityChart(state.compareCache);
    });
  });
  document.querySelectorAll('#dash-scale .chip').forEach(c => {
    c.addEventListener('click', () => {
      document.querySelectorAll('#dash-scale .chip').forEach(x => x.classList.remove('active'));
      c.classList.add('active');
      state.dashScale = c.dataset.scale;
      if (state.dashCache?.live_curves) drawLiveEquityChart(state.dashCache.live_curves);
    });
  });
  document.querySelectorAll('#dash-bench .chip').forEach(c => {
    c.addEventListener('click', () => {
      state.benchOn = !state.benchOn;
      c.classList.toggle('active', state.benchOn);
      if (state.compareCache) drawEquityChart(state.compareCache);
    });
  });
  document.querySelectorAll('#hr-scale .chip').forEach(c => {
    c.addEventListener('click', () => {
      document.querySelectorAll('#hr-scale .chip').forEach(x => x.classList.remove('active'));
      c.classList.add('active');
      state.hrScale = c.dataset.scale;
      if (state.compareCache) drawMonthlyReturnsChart(state.compareCache);
    });
  });
  // Key stats compare toggle
  document.querySelectorAll('#sd-ks-compare .chip').forEach(c => {
    c.addEventListener('click', () => {
      document.querySelectorAll('#sd-ks-compare .chip').forEach(x => x.classList.remove('active'));
      c.classList.add('active');
      state.sdKsCompare = c.dataset.show;
      if (state.sdKsData) drawKeyStats(state.sdKsData, state.sdKsCompare);
    });
  });

  // Strategy detail toggles
  const specToggle = document.getElementById('sd-spec-toggle');
  if (specToggle) specToggle.addEventListener('click', () =>
    document.getElementById('sd-spec').classList.toggle('collapsed'));
  const ratToggle = document.getElementById('sd-rationale-toggle');
  if (ratToggle) ratToggle.addEventListener('click', () =>
    document.getElementById('sd-rationale').classList.toggle('collapsed'));

  // Account tier chips
  document.querySelectorAll('#acc-tier-chips .chip').forEach(c => {
    c.addEventListener('click', () => { state.accTier = c.dataset.tier; renderAccounts(); });
  });

  // Rebalance buttons
  const dryBtn  = document.getElementById('btn-reb-dry');
  const liveBtn = document.getElementById('btn-reb-live');
  const stopBtn = document.getElementById('btn-reb-stop');
  if (dryBtn)  dryBtn .addEventListener('click', () => startRebalance(true));
  if (liveBtn) liveBtn.addEventListener('click', () => startRebalance(false));
  if (stopBtn) stopBtn.addEventListener('click', stopRebalance);

  document.querySelectorAll('#hr-compare-table thead th[data-sort]').forEach(th => {
    th.addEventListener('click', () => {
      const k = th.dataset.sort;
      if (state.sortKey === k) state.sortDir = state.sortDir === 'desc' ? 'asc' : 'desc';
      else { state.sortKey = k; state.sortDir = 'desc'; }
      if (state.compareCache) drawComparisonTable(state.compareCache);
    });
  });
}

function wireClock() {
  const el = document.getElementById('clock');
  const tick = () => { el.textContent = new Date().toTimeString().slice(0, 8); };
  tick();
  setInterval(tick, 1000);
}

let _lastMobile = IS_MOBILE();
window.addEventListener('resize', () => {
  const now = IS_MOBILE();
  if (now !== _lastMobile) {
    _lastMobile = now;
    // Crossing the mobile/desktop threshold — re-render the current page so
    // charts pick up the new legend/tick options and tables reflow.
    loadPage(state.page);
  }
});

document.addEventListener('DOMContentLoaded', () => {
  wireNav();
  wireClock();
  setPage('dashboard');
  setInterval(() => {
    if (state.page === 'dashboard') { state.dashCache = null; renderDashboard(); }
  }, 60_000);
});

})();
