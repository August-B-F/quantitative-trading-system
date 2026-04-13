/* ─── iStock — Frontend ──────────────────────────────────────────────────── */
'use strict';

const CLASS_LABELS = ['STRONG SELL','SELL','HOLD','BUY','STRONG BUY'];
const CLASS_STYLES = ['strong-sell','sell','hold','buy','strong-buy'];

// ─── Routing ──────────────────────────────────────────────────────────────────
const pages    = document.querySelectorAll('.page');
const navItems = document.querySelectorAll('.nav-item');
let currentPage = 'overview';

const PAGE_TITLES = {
  overview: 'Overview', download: 'Data Download',
  train: 'Model Training', data: 'Data Browser',
  backtest: 'Backtest', live: 'Live Trading',
  signals: 'Signals', system: 'System',
};

function navigate(page) {
  currentPage = page;
  pages.forEach(p => p.classList.toggle('active', p.id === 'page-' + page));
  navItems.forEach(n => n.classList.toggle('active', n.dataset.page === page));
  document.querySelector('.page-title').textContent = PAGE_TITLES[page] || page;
  onActivated(page);
}
// ─── Mobile sidebar ───────────────────────────────────────────────────────────
const _sidebar  = document.getElementById('sidebar');
const _overlay  = document.getElementById('sidebar-overlay');
function _closeSidebar() { _sidebar?.classList.remove('open'); _overlay?.classList.remove('visible'); }
function _openSidebar()  { _sidebar?.classList.add('open');    _overlay?.classList.add('visible'); }
document.getElementById('btn-hamburger')?.addEventListener('click', () => {
  _sidebar?.classList.contains('open') ? _closeSidebar() : _openSidebar();
});
_overlay?.addEventListener('click', _closeSidebar);

navItems.forEach(n => n.addEventListener('click', () => {
  navigate(n.dataset.page);
  if (window.innerWidth <= 768) _closeSidebar();
}));

function onActivated(page) {
  if (page === 'overview')  loadOverview();
  if (page === 'download')  loadDownload();
  if (page === 'train')     loadTrain();
  if (page === 'data')      loadData();
  if (page === 'backtest')  loadBacktest();
  if (page === 'live')      loadLive();
  if (page === 'signals')   loadSignals();
  if (page === 'system')    loadSystem();
}

// ─── Clock ────────────────────────────────────────────────────────────────────
setInterval(() => {
  const e = document.getElementById('clock');
  if (e) e.textContent = new Date().toLocaleTimeString('en-US', {hour12: false});
}, 1000);

// ─── Utils ────────────────────────────────────────────────────────────────────
const api = async (path, opts) => {
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
};
const el = id => document.getElementById(id);

function fmt$(v)   { return v == null ? '—' : '$' + Math.round(v).toLocaleString(); }
function fmt$2(v)  { if (v == null) return '—'; const s = v >= 0 ? '+$' : '-$'; return s + Math.abs(v).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}); }
function fmtPct(v, sign=true) { if (v == null) return '—'; return (sign && v > 0 ? '+' : '') + (v*100).toFixed(2)+'%'; }
function fmtPct1(v){ return v == null ? '—' : (v>0?'+':'') + (v*100).toFixed(1)+'%'; }
function fmtN(v,d=3){ return v == null ? '—' : parseFloat(v).toFixed(d); }

function setVal(id, val, cls='') {
  const e = el(id); if (!e) return;
  e.textContent = val ?? '—';
  if (cls) { e.className = e.className.replace(/\b(pos|neg|warn)\b/g,''); if(cls) e.classList.add(cls); }
}

// ─── Counter animation ────────────────────────────────────────────────────────
function countUp(id, target, formatter, duration=900) {
  const e = el(id); if (!e || target == null || isNaN(target)) return;
  const start = performance.now();
  const from  = 0;
  function step(now) {
    const t = Math.min(1, (now - start) / duration);
    const ease = 1 - Math.pow(1 - t, 3); // ease-out cubic
    e.textContent = formatter(from + (target - from) * ease);
    e.classList.add('pop');
    if (t < 1) requestAnimationFrame(step);
    else { e.textContent = formatter(target); setTimeout(() => e.classList.remove('pop'), 300); }
  }
  requestAnimationFrame(step);
}

function setBarFill(id, pct) {
  const e = el(id); if (!e) return;
  e.style.width = Math.min(100, pct).toFixed(1) + '%';
  e.className = 'bar-fill' + (pct > 85 ? ' crit' : pct > 65 ? ' warn' : '');
}

function setRegime(r) {
  const p = el('regime-pill'); if (!p) return;
  const MAP = { bull:'▲ BULL', bear:'▼ BEAR', sideways:'◆ SIDE', crisis:'!! CRISIS', unknown:'? —' };
  p.textContent = MAP[r] || r.toUpperCase();
  p.className   = 'regime-pill ' + (r || 'unknown');
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ─── Charts ───────────────────────────────────────────────────────────────────
const charts = {};
Chart.defaults.color = '#6c6c6c';
Chart.defaults.borderColor = '#242424';
Chart.defaults.font.family = "'JetBrains Mono', monospace";
Chart.defaults.font.size   = 10;

function makeLineChart(id, labels, data, opts={}) {
  const ctx = el(id); if (!ctx) return;
  if (charts[id]) charts[id].destroy();
  const isPos = data.length ? data[data.length-1] >= data[0] : true;
  const color = opts.color || (opts.autoColor ? (isPos ? '#22c4d8' : '#c04848') : '#c8bc4a');
  charts[id] = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        data, borderColor: color, borderWidth: 1.5,
        pointRadius: 0, pointHoverRadius: 3,
        fill: { target: 'origin', above: color+'14', below: color+'14' },
        tension: 0.25,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false, animation: { duration: 300 },
      plugins: { legend: { display: false }, tooltip: {
        mode: 'index', intersect: false, backgroundColor: '#141414',
        borderColor: '#242424', borderWidth: 1,
        callbacks: { label: c => opts.pct ? fmtPct1(c.raw/100) : fmt$2(c.raw) },
      }},
      scales: {
        x: { ticks: { maxTicksLimit: 6, maxRotation: 0 }, grid: { display: false }, border: { display: false } },
        y: { ticks: { maxTicksLimit: 5, callback: v => opts.pct ? fmtPct1(v/100) : fmt$(v) },
             grid: { color: '#24242488' }, border: { display: false } },
      },
    },
  });
}

function makeBarChart(id, labels, data) {
  const ctx = el(id); if (!ctx) return;
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        data,
        backgroundColor: data.map(v => v >= 0 ? '#22c4d828' : '#c0484828'),
        borderColor:     data.map(v => v >= 0 ? '#22c4d8'   : '#c04848'),
        borderWidth: 1, borderRadius: 1,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false, animation: { duration: 300 },
      plugins: { legend: { display: false }, tooltip: {
        backgroundColor: '#141414', borderColor: '#242424', borderWidth: 1,
        callbacks: { label: c => fmt$2(c.raw) },
      }},
      scales: {
        x: { ticks: { maxTicksLimit: 10, maxRotation: 0 }, grid: { display: false }, border: { display: false } },
        y: { ticks: { maxTicksLimit: 5, callback: v => fmt$2(v) },
             grid: { color: '#24242488' }, border: { display: false } },
      },
    },
  });
}

// ─── Sidebar process badge ────────────────────────────────────────────────────
async function refreshStatus() {
  try {
    const s = await api('/api/status');
    const dot = el('proc-dot'), lbl = el('proc-label');
    if (!dot || !lbl) return;
    if (s.running) {
      dot.className = 'process-dot running';
      lbl.textContent = s.name + '…';
    } else if (s.rc === 0) {
      dot.className = 'process-dot done';
      lbl.textContent = (s.name || 'Process') + ' done';
    } else if (s.rc != null) {
      dot.className = 'process-dot error';
      lbl.textContent = 'Error (exit ' + s.rc + ')';
    } else {
      dot.className = 'process-dot';
      lbl.textContent = 'No process running';
    }
  } catch {}
}
setInterval(refreshStatus, 2500);

// Refresh button
el('btn-refresh')?.addEventListener('click', () => onActivated(currentPage));

// ─── Model info renderer ──────────────────────────────────────────────────────
function renderModel(containerId, info) {
  const c = el(containerId); if (!c) return;
  if (!info || !info.epoch) { c.innerHTML = '<p class="mono text-xs text-muted">No checkpoint found.<br>Run Training first.</p>'; return; }
  const sh = info.val_sharpe != null ? fmtN(info.val_sharpe) : '—';
  c.innerHTML = `<div class="kv-list">
    <div class="kv-row"><span class="kv-key">Val Accuracy</span><span class="kv-val pos">${fmtN(info.val_acc)}</span></div>
    <div class="kv-row"><span class="kv-key">Val Sharpe</span><span class="kv-val">${sh}</span></div>
    <div class="kv-row"><span class="kv-key">Fold / Epoch</span><span class="kv-val">${info.fold} / ${info.epoch}</span></div>
    <div class="kv-row"><span class="kv-key">Temperature</span><span class="kv-val">${fmtN(info.temperature, 3)}</span></div>
    <div class="kv-row"><span class="kv-key">Tech Dim</span><span class="kv-val">${info.tech_dim ?? '—'}</span></div>
    <div class="kv-row"><span class="kv-key">Saved</span><span class="kv-val text-muted">${info.age_str ?? '—'}</span></div>
  </div>`;
}

function renderGPU(containerId, gpu) {
  const c = el(containerId); if (!c) return;
  if (!gpu || !gpu.name) { c.innerHTML = '<p class="mono text-xs text-muted">CUDA not available</p>'; return; }
  const pct = (gpu.pct || 0) * 100;
  const cls = pct > 85 ? 'crit' : pct > 65 ? 'warn' : '';
  c.innerHTML = `<div class="kv-list">
    <div class="kv-row"><span class="kv-key">Name</span><span class="kv-val">${gpu.name}</span></div>
    <div class="kv-row"><span class="kv-key">VRAM Used</span><span class="kv-val">${gpu.used_gb.toFixed(1)} / ${gpu.total_gb.toFixed(0)} GB</span></div>
    <div class="kv-row"><span class="kv-key">Utilisation</span><span class="kv-val">${pct.toFixed(0)}%</span></div>
  </div>
  <div class="bar-track mt-8"><div class="bar-fill ${cls}" style="width:${pct.toFixed(0)}%"></div></div>`;
}


// ═════════════════════════════════════════════════════════════════════════════
// Overview
// ═════════════════════════════════════════════════════════════════════════════
async function loadOverview() {
  try {
    const d = await api('/api/overview');
    const m = d.metrics || {};
    if (m.final_equity != null) countUp('ov-equity', m.final_equity, v => '$' + Math.round(v).toLocaleString());
    else setVal('ov-equity', '—');
    const ret = m.total_return;
    if (ret != null) countUp('ov-return', ret * 100, v => (v >= 0 ? '+' : '') + v.toFixed(2) + '%', 800);
    else setVal('ov-return', '—');
    const e_ret = el('ov-return'); if (e_ret) { e_ret.className = e_ret.className.replace(/\b(pos|neg)\b/g,''); e_ret.classList.add(ret > 0 ? 'pos' : ret < 0 ? 'neg' : ''); }
    const sh = m.sharpe;
    if (sh != null) countUp('ov-sharpe', sh, v => v.toFixed(2), 800);
    else setVal('ov-sharpe', '—');
    const e_sh = el('ov-sharpe'); if (e_sh) { e_sh.className = e_sh.className.replace(/\b(pos|neg)\b/g,''); e_sh.classList.add(sh > 1 ? 'pos' : sh < 0 ? 'neg' : ''); }
    const dd = m.max_drawdown;
    if (dd != null) countUp('ov-drawdown', Math.abs(dd) * 100, v => '-' + v.toFixed(2) + '%', 800);
    else setVal('ov-drawdown', '—');
    if (m.win_rate != null) countUp('ov-winrate', m.win_rate * 100, v => v.toFixed(1) + '%', 700);
    else setVal('ov-winrate', '—');
    if (m.n_trades != null) countUp('ov-trades', m.n_trades, v => Math.round(v).toString(), 600);
    else setVal('ov-trades', '—');
    if (d.equity?.length) makeLineChart('ov-chart', Array(d.equity.length).fill(''), d.equity, {autoColor:true});
    setRegime(d.regime || 'unknown');
    renderModel('ov-model', d.model);
    renderGPU('ov-gpu', d.gpu);
    const upd = el('ov-updated');
    if (upd) upd.textContent = '// updated ' + new Date(d.updated_at).toLocaleTimeString();
  } catch (e) { console.error('overview', e); }

  // Symbols panel
  try {
    const sym = await api('/api/data/symbols');
    const cnt = el('ov-sym-count');
    if (cnt) cnt.textContent = sym.count ? '(' + sym.count + ')' : '';
    const box = el('ov-symbols');
    if (box) {
      if (!sym.symbols?.length) {
        box.innerHTML = '<p class="mono text-xs text-muted">No data downloaded yet.</p>';
      } else {
        box.innerHTML = '<div class="sym-tag-grid">' +
          sym.symbols.map(s => `<span class="sym-tag">${s.symbol}</span>`).join('') +
          '</div>';
      }
    }
  } catch {}

  // Latest signals panel
  try {
    const d = await api('/api/signals');
    const sigDate = el('ov-sig-date');
    if (sigDate) sigDate.textContent = d.date || '';
    const box = el('ov-signals');
    if (!box) return;
    const sigs = d.signals || [];
    if (!sigs.length) { box.innerHTML = '<p class="mono text-xs text-muted">No predictions yet.</p>'; return; }
    const buys  = sigs.filter(s => s.pred_class >= 3).slice(0, 5);
    const sells = sigs.filter(s => s.pred_class <= 1).slice(0, 5);
    const renderRow = s => {
      const conf = s.confidence;
      const cls  = s.pred_class >= 3 ? 'buy' : 'sell';
      return `<div class="sig-mini-row">
        <span class="sig-mini-sym">${s.symbol}</span>
        <span class="sig-pill ${CLASS_STYLES[s.pred_class]}">${CLASS_LABELS[s.pred_class]}</span>
        <div class="conf-track" style="flex:1;max-width:80px"><div class="conf-fill ${conf>=.8?'high':conf>=.5?'mid':'low'}" style="width:${(conf*100).toFixed(0)}%"></div></div>
        <span class="conf-val">${(conf*100).toFixed(0)}%</span>
      </div>`;
    };
    box.innerHTML =
      (buys.length  ? '<div class="sig-mini-group">' + buys.map(renderRow).join('')  + '</div>' : '') +
      (buys.length && sells.length ? '<div class="sig-mini-divider"></div>' : '') +
      (sells.length ? '<div class="sig-mini-group">' + sells.map(renderRow).join('') + '</div>' : '');
    if (!buys.length && !sells.length)
      box.innerHTML = '<p class="mono text-xs text-muted">All signals are HOLD.</p>';
  } catch {}
}


// ═════════════════════════════════════════════════════════════════════════════
// Process management
// ═════════════════════════════════════════════════════════════════════════════
let _sseSource = null;

function _syncRunStatus(statusId, pidId, status, processName) {
  const stEl = el(statusId), pidEl = el(pidId);
  const isThis = status.running && status.name === processName;
  if (stEl) {
    stEl.className = 'status-tag' + (isThis ? ' running' : status.rc === 0 ? ' done' : status.rc != null ? ' error' : '');
    stEl.textContent = isThis ? 'Running' : status.rc === 0 ? 'Done' : status.rc != null ? 'Error' : 'Idle';
  }
  if (pidEl) pidEl.textContent = isThis ? 'PID ' + status.pid : '';
  document.querySelectorAll('.page-run-btn').forEach(b => b.disabled = !!status.running);
  document.querySelectorAll('.page-stop-btn').forEach(b => b.disabled = !status.running);
}

async function runProcess(endpoint, statusId, logId, onDone) {
  document.querySelectorAll('.page-run-btn').forEach(b => b.disabled = true);
  document.querySelectorAll('.page-stop-btn').forEach(b => b.disabled = false);
  try {
    await api('/api/run/' + endpoint, { method: 'POST' });
  } catch (e) {
    alert('Error: ' + e.message);
    document.querySelectorAll('.page-run-btn').forEach(b => b.disabled = false);
    document.querySelectorAll('.page-stop-btn').forEach(b => b.disabled = true);
    return;
  }
  const stEl = el(statusId);
  if (stEl) { stEl.className = 'status-tag running'; stEl.textContent = 'Running'; }
  const logEl = el(logId);
  if (logEl) { logEl.style.display = ''; logEl.innerHTML = ''; }
  attachSSE(logId, rc => {
    document.querySelectorAll('.page-run-btn').forEach(b => b.disabled = false);
    document.querySelectorAll('.page-stop-btn').forEach(b => b.disabled = true);
    if (stEl) { stEl.className = 'status-tag ' + (rc === 0 ? 'done' : 'error'); stEl.textContent = rc === 0 ? 'Done' : 'Error'; }
    refreshStatus();
    if (onDone) onDone(rc);
  });
  refreshStatus();
}

async function stopProcess() {
  await api('/api/stop', { method: 'POST' }).catch(() => {});
  setTimeout(() => {
    refreshStatus();
    if (currentPage === 'download') loadDownload();
    if (currentPage === 'train')    loadTrain();
    if (currentPage === 'backtest') loadBacktest();
  }, 400);
}

function attachSSE(logId, onDone) {
  if (_sseSource) _sseSource.close();
  const logEl = el(logId);
  _sseSource = new EventSource('/api/logs/stream');
  _sseSource.onmessage = e => {
    const data = JSON.parse(e.data);
    if (logEl) appendLog(logEl, data);
    if (logId === 'train-log') parseTrainLine(data.msg || '');
    if (data.rc !== undefined) { _sseSource.close(); _sseSource = null; if (onDone) onDone(data.rc); }
  };
  _sseSource.onerror = () => { _sseSource.close(); _sseSource = null; };
}

function parseTrainLine(line) {
  const m = line.match(/epoch[=\s]+(\d+)[/\\](\d+)/i);
  if (m) {
    const cur = parseInt(m[1]), tot = parseInt(m[2]);
    const pb = el('train-pbar');
    if (pb) pb.style.width = Math.round(cur / tot * 100) + '%';
    const lbl = el('train-prog-label');
    if (lbl) lbl.textContent = `epoch ${cur} / ${tot}`;
  }
  const f = line.match(/fold[=\s]+(\d+)[/\\](\d+)/i);
  if (f) {
    const cur = parseInt(f[1]), tot = parseInt(f[2]);
    const fb = el('train-fold-bar');
    if (fb) fb.style.width = Math.round(cur / tot * 100) + '%';
    const lbl = el('train-fold-label');
    if (lbl) lbl.textContent = `fold ${cur} / ${tot}`;
  }
  const a = line.match(/val_acc[=\s]+([\d.]+)/i);
  if (a) setVal('train-vacc', fmtN(parseFloat(a[1])), 'pos');
  const s = line.match(/val_sharpe[=\s]+([\d.]+)/i);
  if (s) setVal('train-vsharpe', fmtN(parseFloat(s[1])), 'pos');
}

function appendLog(el, data) {
  const msg = data.msg || '', ts = data.t || '';
  const ll  = msg.toLowerCase();
  let cls   = 'log-plain';
  if (ll.includes('error') || ll.includes('traceback') || (data.rc != null && data.rc !== 0)) cls = 'log-err';
  else if (ll.includes('warning')) cls = 'log-warn';
  else if (msg.startsWith('✓') || ll.includes('complete') || ll.includes('done') || ll.includes('saved')) cls = 'log-ok';
  else if (ll.includes('epoch') || ll.includes('fold') || ll.includes('val_') || ll.includes('train')) cls = 'log-info';
  const line = document.createElement('div');
  line.innerHTML = `<span class="log-ts">${ts}</span><span class="${cls}">${escHtml(msg)}</span>`;
  el.appendChild(line);
  el.scrollTop = el.scrollHeight;
}


// ═════════════════════════════════════════════════════════════════════════════
// Download page
// ═════════════════════════════════════════════════════════════════════════════
async function loadDownload() {
  try {
    const [summary, sym, status] = await Promise.all([
      api('/api/data/summary'), api('/api/data/symbols'), api('/api/status'),
    ]);
    setVal('dl-nsymbols', sym.count ?? '—');
    setVal('dl-rows',     (summary.total_rows || 0).toLocaleString());
    setVal('dl-disk',     summary.total_size || '—');
    setVal('dl-updated',  summary.last_updated || '—');

    const files = summary.files || [];
    const barFiles  = files.filter(f => (f.name || '').includes('bars') || (f.path || '').includes('bars'));
    const newsFiles = files.filter(f => (f.name || '').endsWith('.json') || (f.name || '').includes('news'));
    const fundFiles = files.filter(f => (f.name || '').includes('fundamental'));
    const gdeltFiles= files.filter(f => (f.name || '').includes('gdelt'));
    const barCount  = barFiles.length || sym.count || 0;
    const newsCount = newsFiles.length;

    setVal('dl-bars', barCount || '—');
    setVal('dl-news', newsCount || '—');
    _setSource('src-bars',  barCount,  `${barCount} symbols`);
    _setSource('src-news',  newsCount, newsCount ? `${newsCount} files` : 'not downloaded');
    _setSource('src-fund',  fundFiles.length, fundFiles.length ? `${fundFiles.length} files` : 'optional');
    _setSource('src-gdelt', gdeltFiles.length, gdeltFiles.length ? 'cached' : 'optional');

    _renderSymTable('dl-sym-body', sym.symbols || []);
    _syncRunStatus('dl-status', 'dl-pid', status, 'Data Download');

    if (status.running && status.name === 'Data Download' && !_sseSource) {
      attachSSE('dl-log', rc => {
        _syncRunStatus('dl-status', 'dl-pid', { running: false, rc }, 'Data Download');
        loadDownload();
      });
    }
  } catch(e) { console.error('download', e); }
}

function _setSource(id, count, detail) {
  const tag = el(id), det = el(id + '-detail');
  if (tag) {
    tag.className   = 'status-tag ' + (count > 0 ? 'done' : '');
    tag.textContent = count > 0 ? 'OK' : 'Empty';
  }
  if (det) det.textContent = detail || '';
}

function _renderSymTable(tbodyId, symbols) {
  const t = el(tbodyId); if (!t) return;
  if (!symbols.length) { t.innerHTML = '<tr><td colspan="8" class="empty-state">No symbol data found</td></tr>'; return; }
  t.innerHTML = symbols.map(s => {
    const days = typeof s.days === 'number' ? s.days : 0;
    const fr   = days > 500 ? '' : days > 100 ? 'old' : 'none';
    const dots = days > 0
      ? Array(Math.min(8, Math.round(days / 100))).fill(0).map(() => `<span class="cov-cell ${fr}"></span>`).join('')
        + Array(Math.max(0, 8 - Math.round(days / 100))).fill(0).map(() => `<span class="cov-cell none"></span>`).join('')
      : '<span class="cov-cell none"></span>'.repeat(8);
    return `<tr>
      <td>${s.symbol}</td>
      <td>${typeof s.rows === 'number' ? s.rows.toLocaleString() : '?'}</td>
      <td class="t-muted">${s.date_from || '?'}</td>
      <td class="t-muted">${s.date_to || '?'}</td>
      <td class="t-mono">${s.days}</td>
      <td class="t-muted">${s.size}</td>
      <td class="t-mono t-muted">${s.updated}</td>
      <td>${dots}</td>
    </tr>`;
  }).join('');
}

el('btn-run-download')?.addEventListener('click', () =>
  runProcess('download', 'dl-status', 'dl-log', () => loadDownload()));
el('btn-stop-download')?.addEventListener('click', stopProcess);
el('btn-dl-scan')?.addEventListener('click', loadDownload);


// ═════════════════════════════════════════════════════════════════════════════
// Training page
// ═════════════════════════════════════════════════════════════════════════════
async function loadTrain() {
  try {
    const [info, status] = await Promise.all([api('/api/model'), api('/api/status')]);
    if (info?.epoch) {
      setVal('train-vacc',    fmtN(info.val_acc),    info.val_acc > 0.6 ? 'pos' : '');
      setVal('train-vsharpe', info.val_sharpe != null ? fmtN(info.val_sharpe) : '—', info.val_sharpe > 1 ? 'pos' : '');
      setVal('train-fold',    info.fold ?? '—');
      setVal('train-epoch',   info.epoch ?? '—');
      setVal('train-temp',    info.temperature != null ? fmtN(info.temperature, 3) : '—');
      setVal('train-age',     info.age_str || '—');
      renderModel('train-checkpoint', info);
    }
    _syncRunStatus('train-status', 'train-pid', status, 'Training');
    if (status.running && status.name === 'Training' && !_sseSource) {
      attachSSE('train-log', rc => {
        _syncRunStatus('train-status', 'train-pid', { running: false, rc }, 'Training');
        loadTrain();
      });
    }
  } catch(e) { console.error('train', e); }
}

el('btn-run-train')?.addEventListener('click', () =>
  runProcess('train', 'train-status', 'train-log', () => loadTrain()));
el('btn-stop-train')?.addEventListener('click', stopProcess);


// ═════════════════════════════════════════════════════════════════════════════
// Data page
// ═════════════════════════════════════════════════════════════════════════════
async function loadData() {
  try {
    const [sym, files] = await Promise.all([
      api('/api/data/symbols'),
      api('/api/data/summary'),
    ]);

    // Summary cards
    setVal('data-nsymbols', sym.count);
    setVal('data-nrows',    (files.total_rows||0).toLocaleString());
    setVal('data-disk',     files.total_size);
    setVal('data-lastsync', files.last_updated);

    // Symbol table
    const stbody = el('data-sym-body');
    if (stbody) {
      if (!sym.symbols.length) {
        stbody.innerHTML = '<tr><td colspan="9" class="empty-state">No per-symbol data found in data/raw/bars/</td></tr>';
      } else {
        const now = new Date();
        stbody.innerHTML = sym.symbols.map(s => {
          const days    = typeof s.days === 'number' ? s.days : 0;
          const freshness = days > 500 ? '' : days > 100 ? 'old' : 'none';
          const covDots = days > 0
            ? Array(Math.min(8, Math.round(days/100))).fill(0).map(() =>
                `<span class="cov-cell ${freshness}"></span>`).join('') + Array(Math.max(0,8-Math.round(days/100))).fill(0).map(()=>
                `<span class="cov-cell none"></span>`).join('')
            : '<span class="cov-cell none"></span>'.repeat(8);
          return `<tr>
            <td>${s.symbol}</td>
            <td class="t-mono t-muted">${s.file}</td>
            <td>${typeof s.rows==='number' ? s.rows.toLocaleString() : '?'}</td>
            <td class="t-muted">${s.date_from}</td>
            <td class="t-muted">${s.date_to}</td>
            <td class="t-mono">${s.days}</td>
            <td class="t-muted">${s.size}</td>
            <td class="t-mono t-muted">${s.updated}</td>
            <td>${covDots}</td>
          </tr>`;
        }).join('');
      }
    }

    // All files table
    const ftbody = el('data-files-body');
    if (ftbody) {
      if (!files.files.length) {
        ftbody.innerHTML = '<tr><td colspan="6" class="empty-state">No data files found</td></tr>';
      } else {
        ftbody.innerHTML = files.files.map(f => `<tr>
          <td>${f.name}</td>
          <td>${typeof f.rows==='number' ? f.rows.toLocaleString() : '?'}</td>
          <td class="t-muted">${f.date_from || '?'}</td>
          <td class="t-muted">${f.date_to   || '?'}</td>
          <td class="t-muted">${f.size_fmt}</td>
          <td class="t-mono t-muted">${f.updated}</td>
        </tr>`).join('');
      }
    }
  } catch (e) { console.error('data', e); }
}

el('btn-data-refresh')?.addEventListener('click', loadData);


// ═════════════════════════════════════════════════════════════════════════════
// Backtest
// ═════════════════════════════════════════════════════════════════════════════
async function loadBacktest() {
  try {
    const [eq, trd, perf, status] = await Promise.all([
      api('/api/equity'), api('/api/trades'), api('/api/performance'), api('/api/status'),
    ]);
    _syncRunStatus('bt-run-status', null, status, 'Backtest');
    if (status.running && status.name === 'Backtest' && !_sseSource) {
      const btLog = el('bt-log'); if (btLog) btLog.style.display = '';
      attachSSE('bt-log', rc => {
        _syncRunStatus('bt-run-status', null, { running: false, rc }, 'Backtest');
        const btLog = el('bt-log'); if (btLog) btLog.style.display = 'none';
        loadBacktest();
      });
    }
    const m = perf.metrics || {};
    if (m.total_return != null) countUp('bt-ret', m.total_return * 100, v => (v >= 0 ? '+' : '') + v.toFixed(2) + '%');
    else setVal('bt-ret', '—');
    if (m.sharpe != null) countUp('bt-sharpe', m.sharpe, v => v.toFixed(2), 800);
    else setVal('bt-sharpe', '—');
    if (m.sortino != null) countUp('bt-sortino', m.sortino, v => v.toFixed(2), 800);
    else setVal('bt-sortino', '—');
    if (m.max_drawdown != null) countUp('bt-dd', Math.abs(m.max_drawdown) * 100, v => '-' + v.toFixed(2) + '%');
    else setVal('bt-dd', '—');
    if (m.win_rate != null) countUp('bt-wr', m.win_rate * 100, v => v.toFixed(1) + '%', 700);
    else setVal('bt-wr', '—');
    if (m.n_trades != null) countUp('bt-ntrades', m.n_trades, v => Math.round(v).toString(), 600);
    else setVal('bt-ntrades', '—');
    if (eq.values?.length) makeLineChart('bt-equity-chart', eq.dates, eq.values, {autoColor:true});
    if (perf.pnl_values?.length) makeBarChart('bt-pnl-chart', perf.pnl_dates, perf.pnl_values);
    renderTradesTable('bt-trades-body', trd.trades || []);
  } catch (e) { console.error('backtest', e); }
}

el('btn-run-backtest')?.addEventListener('click', () => {
  const btLog = el('bt-log'); if (btLog) btLog.style.display = '';
  runProcess('backtest', 'bt-run-status', 'bt-log', rc => {
    const btLog = el('bt-log'); if (btLog && rc === 0) btLog.style.display = 'none';
    loadBacktest();
  });
});
el('btn-stop-backtest')?.addEventListener('click', stopProcess);

function renderTradesTable(tbodyId, trades) {
  const t = el(tbodyId); if (!t) return;
  if (!trades.length) { t.innerHTML = '<tr><td colspan="7" class="empty-state">No trades yet</td></tr>'; return; }
  t.innerHTML = trades.map(r => `<tr>
    <td>${r.symbol}</td>
    <td class="t-mono t-muted">${r.entry_date}</td>
    <td class="t-mono t-muted">${r.exit_date}</td>
    <td class="${r.pnl_pct>=0?'t-pos':'t-neg'}">${fmtPct(r.pnl_pct)}</td>
    <td class="${r.pnl_dollar>=0?'t-pos':'t-neg'}">${fmt$2(r.pnl_dollar)}</td>
    <td class="t-muted">${r.exit_reason}</td>
    <td class="t-muted">${r.regime}</td>
  </tr>`).join('');
}


// ═════════════════════════════════════════════════════════════════════════════
// Live Trading
// ═════════════════════════════════════════════════════════════════════════════
let _liveLogActive = false;

async function loadLive() {
  try {
    const [pos, st, trd] = await Promise.all([api('/api/positions'), api('/api/status'), api('/api/trades').catch(()=>({trades:[]}))]);
    const a = pos.account || {};
    setVal('live-equity', fmt$(a.equity));
    setVal('live-cash',   fmt$(a.cash));
    setVal('live-bp',     fmt$(a.buying_power));
    const invested = (pos.positions||[]).reduce((s,p)=>s+p.market_value,0);
    const exp = a.equity ? invested/a.equity : 0;
    setVal('live-exp', fmtPct1(exp), exp > 0.9 ? 'neg' : '');
    renderPosTable('live-pos-body', pos.positions||[]);
    renderTradesTable('live-trades-body', (trd.trades||[]).slice(0,20));
    updateBotBadge(st);
    if (st.running && st.name === 'Live Bot' && !_liveLogActive) {
      _liveLogActive = true;
      attachSSE('live-log', () => { _liveLogActive = false; });
    }
  } catch (e) { console.error('live', e); }
}

function renderPosTable(tbodyId, positions) {
  const t = el(tbodyId); if (!t) return;
  if (!positions.length) { t.innerHTML = '<tr><td colspan="7" class="empty-state">No open positions</td></tr>'; return; }
  t.innerHTML = positions.map(p => `<tr>
    <td>${p.symbol}</td>
    <td class="t-mono">${p.qty.toFixed(2)}</td>
    <td class="t-mono t-muted">$${p.avg_entry.toFixed(2)}</td>
    <td class="t-mono t-muted">$${p.current.toFixed(2)}</td>
    <td>$${p.market_value.toLocaleString('en-US',{maximumFractionDigits:0})}</td>
    <td class="${p.unrealized_pl>=0?'t-pos':'t-neg'}">${fmt$2(p.unrealized_pl)}</td>
    <td class="${p.pnl_pct>=0?'t-pos':'t-neg'}">${fmtPct(p.pnl_pct)}</td>
  </tr>`).join('');
}

function updateBotBadge(s) {
  const badge = el('bot-status-badge'), pid = el('bot-pid');
  if (badge) { badge.className = 'status-tag ' + (s.running?'running': s.rc===0?'done': s.rc!=null?'error':''); badge.textContent = s.running?'Running': s.rc===0?'Done': s.rc!=null?'Error':'Idle'; }
  if (pid) pid.textContent = s.running ? 'PID '+s.pid : '';
  const start = el('btn-bot-start'), stop = el('btn-bot-stop');
  if (start) start.disabled = s.running;
  if (stop)  stop.disabled  = !s.running;
}

el('btn-bot-start')?.addEventListener('click', async () => {
  el('btn-bot-start').disabled = true;
  try {
    await api('/api/run/bot', {method:'POST'});
    const log = el('live-log'); if (log) log.innerHTML = '';
    _liveLogActive = true;
    attachSSE('live-log', () => { _liveLogActive = false; loadLive(); });
    updateBotBadge({running:true});
    refreshStatus();
  } catch(e) { alert(e.message); el('btn-bot-start').disabled = false; }
});
el('btn-bot-stop')?.addEventListener('click', async () => {
  await api('/api/stop', {method:'POST'});
  _liveLogActive = false;
  setTimeout(loadLive, 500);
  refreshStatus();
});
el('btn-pos-refresh')?.addEventListener('click', loadLive);


// ═════════════════════════════════════════════════════════════════════════════
// Signals
// ═════════════════════════════════════════════════════════════════════════════
let _sigFilter = 'all';

async function loadSignals(filter) {
  if (filter) _sigFilter = filter;
  try {
    const d = await api('/api/signals');
    const s = d.summary || {};
    setVal('sig-date',   d.date || '—');
    setVal('sig-nbuys',  s.buys  ?? 0);
    setVal('sig-nsells', s.sells ?? 0);
    setVal('sig-nholds', s.holds ?? 0);
    setVal('sig-conf',   s.avg_conf != null ? fmtPct1(s.avg_conf) : '—');
    let sigs = d.signals || [];
    if (_sigFilter === 'buys')  sigs = sigs.filter(s => s.pred_class >= 3);
    if (_sigFilter === 'sells') sigs = sigs.filter(s => s.pred_class <= 1);
    const tbody = el('sig-tbody'); if (!tbody) return;
    if (!sigs.length) { tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No signals</td></tr>'; return; }
    tbody.innerHTML = sigs.map(s => {
      const conf = s.confidence;
      const cls  = conf >= 0.8 ? 'high' : conf >= 0.5 ? 'mid' : 'low';
      return `<tr>
        <td>${s.symbol}</td>
        <td><span class="sig-pill ${CLASS_STYLES[s.pred_class]}">${CLASS_LABELS[s.pred_class]}</span></td>
        <td><div class="conf-wrap"><div class="conf-track"><div class="conf-fill ${cls}" style="width:${(conf*100).toFixed(0)}%"></div></div><span class="conf-val">${(conf*100).toFixed(0)}%</span></div></td>
        <td class="${s.uncertainty>0.7?'t-neg':s.uncertainty>0.4?'':'t-pos'} mono">${s.uncertainty.toFixed(2)}</td>
        <td>${s.probs.length ? s.probs.map((p,i)=>`<span style="opacity:${0.3+p*0.7};font-size:11px;color:${i===s.pred_class?'var(--accent)':'var(--border-3)'}">█</span>`).join('') : ''}</td>
      </tr>`;
    }).join('');
  } catch (e) { console.error('signals', e); }
}

document.querySelectorAll('.chip[data-sig]').forEach(chip => {
  chip.addEventListener('click', () => {
    document.querySelectorAll('.chip[data-sig]').forEach(c => c.classList.remove('active'));
    chip.classList.add('active');
    loadSignals(chip.dataset.sig);
  });
});


// ═════════════════════════════════════════════════════════════════════════════
// System
// ═════════════════════════════════════════════════════════════════════════════
let _sysLogTab    = 'app';
let _sysLogLevel  = 'all';
let _sysLogData   = { app: [], access: [] };

async function loadSystem() {
  try {
    const [health, model, gpu] = await Promise.all([
      api('/api/system/health'),
      api('/api/model'),
      api('/api/gpu'),
    ]);

    // Health grid
    if (health.cpu_pct != null) {
      setVal('sys-cpu', health.cpu_pct.toFixed(0) + '%');
      setBarFill('sys-cpu-bar', health.cpu_pct);
    }
    if (health.mem_pct != null) {
      setVal('sys-mem', health.mem_pct.toFixed(0) + '%');
      const d = el('sys-mem-detail'); if (d) d.textContent = health.mem_used + ' / ' + health.mem_total;
      setBarFill('sys-mem-bar', health.mem_pct);
    }
    if (health.disk_pct != null) {
      setVal('sys-disk', health.disk_pct.toFixed(0) + '%');
      const d = el('sys-disk-detail'); if (d) d.textContent = health.disk_used + ' / ' + health.disk_total;
      setBarFill('sys-disk-bar', health.disk_pct);
    }
    if (health.gpu_pct != null) {
      setVal('sys-gpu', health.gpu_pct.toFixed(0) + '%');
      const n = el('sys-gpu-name'); if (n) n.textContent = health.gpu_used + ' / ' + health.gpu_total;
      setBarFill('sys-gpu-bar', health.gpu_pct);
    } else {
      setVal('sys-gpu', 'N/A');
    }
    setVal('sys-uptime',  health.uptime_str || '—');
    setVal('sys-db-size', health.db_size || '—');

    // Model + GPU detail cards
    renderModel('sys-model-info', model);
    renderGPU('sys-gpu-detail', gpu);

    // Update system banner
    const banner = el('sys-banner');
    if (banner) {
      const issues = [];
      if (health.cpu_pct  > 90) issues.push('CPU High');
      if (health.mem_pct  > 90) issues.push('Memory High');
      if (health.disk_pct > 90) issues.push('Disk Full');
      banner.className  = 'sys-banner' + (issues.length ? '' : ' ok');
      banner.textContent = issues.length ? 'ALERT: ' + issues.join(' · ') : 'System Nominal';
    }

    // Load logs
    await loadSysLogs();
  } catch (e) { console.error('system', e); }
}

async function loadSysLogs() {
  if (_sysLogTab === 'app') {
    try {
      const d = await api('/api/system/logs?days=7&limit=500');
      _sysLogData.app = d.entries || [];
    } catch { _sysLogData.app = []; }
  } else {
    try {
      const d = await api('/api/system/access-logs');
      _sysLogData.access = d.entries || [];
    } catch { _sysLogData.access = []; }
  }
  renderSysLogs();
}

function renderSysLogs() {
  const log = el('sys-log'); if (!log) return;
  const entries = _sysLogTab === 'app' ? _sysLogData.app : _sysLogData.access;

  if (_sysLogTab === 'access') {
    if (!entries.length) { log.innerHTML = '<span class="log-plain">No access log entries yet.</span>'; return; }
    log.innerHTML = entries.map(e => {
      const sc = e.status >= 500 ? 'log-err' : e.status >= 400 ? 'log-warn' : 'log-ok';
      return `<div><span class="log-ts">${e.t}</span><span class="${sc}">${e.method.padEnd(6)} ${e.status}</span> <span class="log-plain">${escHtml(e.path)}</span> <span class="log-ts">${e.ms}ms ${e.ip}</span></div>`;
    }).join('');
    return;
  }

  // App logs
  const filtered = _sysLogLevel === 'all' ? entries
    : entries.filter(e => e.level === _sysLogLevel);

  if (!filtered.length) { log.innerHTML = '<span class="log-plain">No log entries found.</span>'; return; }

  log.innerHTML = filtered.map(e => {
    const cls = e.level === 'error' ? 'log-err' : e.level === 'warning' ? 'log-warn' : 'log-plain';
    const lvl = e.level === 'error' ? '<span class="level-tag level-error">ERR</span>'
              : e.level === 'warning' ? '<span class="level-tag level-warning">WARN</span>'
              : '';
    return `<div><span class="log-ts">${e.date}</span>${lvl}<span class="${cls}">${escHtml(e.msg)}</span></div>`;
  }).join('');
}

// Log tab + level chips
document.querySelectorAll('[data-log]').forEach(btn => {
  btn.addEventListener('click', () => {
    _sysLogTab = btn.dataset.log;
    document.querySelectorAll('[data-log]').forEach(b => b.classList.toggle('active', b.dataset.log === _sysLogTab));
    el('sys-log-title').textContent = _sysLogTab === 'app' ? 'Application Logs — Last 7 Days' : 'HTTP Access Log';
    loadSysLogs();
  });
});
document.querySelectorAll('[data-loglevel]').forEach(btn => {
  btn.addEventListener('click', () => {
    _sysLogLevel = btn.dataset.loglevel;
    document.querySelectorAll('[data-loglevel]').forEach(b => b.classList.toggle('active', b.dataset.loglevel === _sysLogLevel));
    renderSysLogs();
  });
});
el('btn-sys-refresh')?.addEventListener('click', loadSystem);

// ─── Boot ──────────────────────────────────────────────────────────────────────
navigate('overview');
refreshStatus();
