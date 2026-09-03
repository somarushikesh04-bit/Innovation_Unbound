/* ═══════════════════════════════════════════════════════════════════
   MSME360 — Vanilla JS Application Core (ES6+ Modular)
   Handles: Auth, Navigation, Ledger, Invoices, Analytics, Cap Table,
            Location, AI Advisor, Charts (Chart.js), Modals, Toasts
   ═══════════════════════════════════════════════════════════════════ */

'use strict';

// ─── State ────────────────────────────────────────────────────────────────────
const STATE = {
  token: localStorage.getItem('msme360_token') || null,
  user: null,
  tenant: null,
  currentPage: 'dashboard',
  ledgerPage: 1,
  invoicePage: 1,
  charts: {},
  runwayData: null,
  breakevenData: null,
};

// ─── API Helper ───────────────────────────────────────────────────────────────
async function api(method, path, body = null, isForm = false) {
  const opts = {
    method,
    headers: {},
    credentials: 'include',
  };
  if (STATE.token) opts.headers['Authorization'] = 'Bearer ' + STATE.token;
  if (body && !isForm) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  } else if (body && isForm) {
    opts.body = body; // FormData
  }
  try {
    const res = await fetch(path, opts);
    const data = await res.json().catch(() => ({}));
    return { ok: res.ok, status: res.status, data };
  } catch (e) {
    return { ok: false, status: 0, data: { error: 'Network error' } };
  }
}

// ─── Formatting helpers ───────────────────────────────────────────────────────
function fmt(n, decimals = 0) {
  if (n == null || isNaN(n)) return '—';
  return '₹' + Number(n).toLocaleString('en-IN', { maximumFractionDigits: decimals });
}
function fmtNum(n, decimals = 0) {
  if (n == null || isNaN(n)) return '—';
  return Number(n).toLocaleString('en-IN', { maximumFractionDigits: decimals });
}
function fmtDate(s) {
  if (!s) return '—';
  try { return new Date(s).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }); }
  catch { return s; }
}
function safe(s) {
  const d = document.createElement('div');
  d.textContent = s || '—';
  return d.innerHTML;
}
function debounce(fn, ms) {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

// ─── Toast ────────────────────────────────────────────────────────────────────
function toast(msg, type = 'info') {
  const c = document.getElementById('toast-container');
  const el = document.createElement('div');
  el.className = 'toast ' + type;
  const icon = { success: 'check_circle', error: 'error', warning: 'warning', info: 'info' }[type] || 'info';
  const icon_el = document.createElement('span');
  icon_el.className = 'material-symbols-outlined sm';
  icon_el.textContent = icon;
  const text = document.createElement('span');
  text.textContent = msg;
  el.appendChild(icon_el);
  el.appendChild(text);
  c.appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; el.style.transform = 'translateX(40px)'; el.style.transition = 'all 0.3s'; setTimeout(() => el.remove(), 300); }, 3500);
}

// ─── Auth ─────────────────────────────────────────────────────────────────────
function switchAuthTab(tab) {
  document.getElementById('login-form').classList.toggle('hidden', tab !== 'login');
  document.getElementById('register-form').classList.toggle('hidden', tab !== 'register');
  document.getElementById('tab-login').classList.toggle('active', tab === 'login');
  document.getElementById('tab-register').classList.toggle('active', tab === 'register');
}

function fillDemo(email) {
  document.getElementById('login-email').value = email;
  document.getElementById('login-password').value = 'Demo@1234';
}

async function doLogin() {
  const email = document.getElementById('login-email').value.trim();
  const password = document.getElementById('login-password').value;
  const btn = document.getElementById('login-btn');
  if (!email || !password) { showAuthError('login', 'Please enter email and password'); return; }

  btn.disabled = true;
  btn.innerHTML = '<div class="spinner"></div> Signing in...';

  const r = await api('POST', '/api/auth/login', { email, password });
  btn.disabled = false;
  btn.innerHTML = '<span class="material-symbols-outlined sm">login</span> Sign In';

  if (r.ok) {
    STATE.token = r.data.access_token;
    localStorage.setItem('msme360_token', STATE.token);
    STATE.user = r.data.user;
    STATE.tenant = r.data.tenant;
    enterApp();
  } else {
    showAuthError('login', r.data.error || 'Login failed');
  }
}

async function doRegister() {
  const email = document.getElementById('reg-email').value.trim();
  const password = document.getElementById('reg-password').value;
  const full_name = document.getElementById('reg-fullname').value.trim();
  const business_name = document.getElementById('reg-business').value.trim();
  if (!email || !password || !full_name || !business_name) { showAuthError('register', 'All fields required'); return; }

  const r = await api('POST', '/api/auth/register', { email, password, full_name, business_name });
  if (r.ok) {
    STATE.token = r.data.access_token;
    localStorage.setItem('msme360_token', STATE.token);
    STATE.user = r.data.user;
    STATE.tenant = r.data.tenant;
    enterApp();
  } else {
    showAuthError('register', r.data.error || 'Registration failed');
  }
}

function showAuthError(form, msg) {
  const el = document.getElementById(form === 'login' ? 'login-error' : 'reg-error');
  el.textContent = msg;
  el.classList.remove('hidden');
  setTimeout(() => el.classList.add('hidden'), 5000);
}

async function doLogout() {
  await api('POST', '/api/auth/logout');
  STATE.token = null;
  STATE.user = null;
  localStorage.removeItem('msme360_token');
  document.getElementById('app').classList.remove('visible');
  document.getElementById('auth-screen').classList.remove('hidden');
  toast('Signed out successfully', 'info');
}

function enterApp() {
  document.getElementById('auth-screen').classList.add('hidden');
  document.getElementById('app').classList.add('visible');
  updateUserUI();
  showPage('dashboard');
  loadDashboard();
  loadQuickInsights();
  // Set today's date default for entry modal
  document.getElementById('entry-date').value = new Date().toISOString().split('T')[0];
}

function updateUserUI() {
  if (!STATE.user) return;
  const initials = (STATE.user.full_name || 'U').split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
  setText('sidebar-user-name', STATE.user.full_name);
  setText('sidebar-user-role', STATE.user.role);
  setText('header-user-name', STATE.user.full_name);
  setText('header-user-role', STATE.user.role);
  setText('user-avatar-initials', initials);
  setText('header-user-avatar', initials);
  if (STATE.tenant) {
    setText('tenant-name-sidebar', STATE.tenant.name || 'Enterprise Portal');
  }
  // Highlight active owner in switcher
  setTimeout(highlightCurrentOwner, 50);
}

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val || '';
}

// ─── Navigation ───────────────────────────────────────────────────────────────
function showPage(page) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const pageEl = document.getElementById('page-' + page);
  if (pageEl) pageEl.classList.add('active');
  const navEl = document.getElementById('nav-' + page);
  if (navEl) navEl.classList.add('active');
  STATE.currentPage = page;

  const loaders = {
    dashboard: loadDashboard,
    ledger: loadLedger,
    invoices: loadInvoices,
    directory: () => loadDirectory(''),
    inventory: loadInventory,
    forecasts: loadForecasts,
    location: loadLocationHistory,
    financing: loadFinancing,
    captable: loadCapTable,
    team: () => {},
    smartshield: loadSmartShield,
  };
  if (loaders[page]) loaders[page]();
}

// ─── Dashboard ────────────────────────────────────────────────────────────────
async function loadDashboard() {
  const r = await api('GET', '/api/analytics/dashboard');
  if (!r.ok) return;
  const { health, runway, break_even: be, invoice_alerts, invoice_pending } = r.data;

  // Header metrics
  setText('header-health', (health?.score ?? '—') + '/100');
  setText('header-runway', (runway?.runway_days ?? '—') + ' days');
  setText('header-alerts', String(invoice_alerts ?? '—'));

  // KPI Cards
  setText('kpi-cash-flow', fmt(runway?.current_cash));
  setText('kpi-burn-rate', fmt(runway?.monthly_burn));
  setText('kpi-runway', (runway?.runway_days ?? '—') + (runway?.runway_days === 999 ? '+' : '') + ' days');
  setText('kpi-alerts', String(invoice_alerts ?? 0));
  setText('kpi-alerts-label', (invoice_pending ?? 0) + ' pending review');

  const trend = (runway?.net_monthly ?? 0) >= 0;
  const trendEl = document.getElementById('kpi-cash-trend');
  if (trendEl) {
    trendEl.className = 'kpi-change ' + (trend ? 'up' : 'down');
    const icon = document.createElement('span');
    icon.className = 'material-symbols-outlined sm';
    icon.textContent = trend ? 'arrow_upward' : 'arrow_downward';
    trendEl.innerHTML = '';
    trendEl.appendChild(icon);
    const txt = document.createTextNode('₹' + Math.abs(runway?.net_monthly ?? 0).toLocaleString('en-IN', { maximumFractionDigits: 0 }) + '/mo net');
    trendEl.appendChild(txt);
  }

  // Invoice alert badge
  const badge = document.getElementById('invoice-alert-badge');
  if (badge) {
    badge.textContent = String(invoice_alerts ?? 0);
    badge.classList.toggle('hidden', !invoice_alerts);
  }

  // Health Score Ring
  const score = health?.score ?? 0;
  setText('health-score-num', Math.round(score));
  setText('health-grade', 'Grade ' + (health?.grade ?? '—'));
  const ring = document.getElementById('health-ring');
  if (ring) {
    const offset = 314 - (314 * score / 100);
    setTimeout(() => { ring.style.strokeDashoffset = offset; }, 100);
    const color = score >= 70 ? 'var(--color-secondary)' : score >= 50 ? 'var(--color-accent)' : 'var(--color-error)';
    ring.style.stroke = color;
  }

  // Score bars
  const bars = { solvency: health?.solvency, liquidity: health?.liquidity, profitability: health?.profitability, efficiency: health?.efficiency };
  for (const [key, val] of Object.entries(bars)) {
    const pct = Math.min(100, ((val ?? 0) / 25) * 100);
    const bar = document.getElementById('bar-' + key);
    if (bar) setTimeout(() => { bar.style.width = pct + '%'; }, 200);
    setText('val-' + key, Math.round(val ?? 0));
  }

  // Charts
  STATE.runwayData = runway;
  STATE.breakevenData = be;
  renderRunwayChart(runway, 30);
  renderBreakevenChart(be);

  // Invoice Queue
  loadInvoiceQueueWidget();
}

// ─── Charts ───────────────────────────────────────────────────────────────────
const CHART_DEFAULTS = {
  plugins: { legend: { display: false }, tooltip: { mode: 'index', intersect: false, backgroundColor: '#1e293b', titleColor: '#fff', bodyColor: '#94a3b8', padding: 10, cornerRadius: 8, displayColors: false } },
  scales: {
    x: { grid: { display: false }, ticks: { color: '#76777d', font: { size: 11 } } },
    y: { grid: { color: 'rgba(118,119,125,0.1)' }, ticks: { color: '#76777d', font: { size: 11 }, callback: v => '₹' + (v / 1000).toFixed(0) + 'K' } }
  },
  responsive: true,
  maintainAspectRatio: false,
  animation: { duration: 800, easing: 'easeInOutQuart' },
  interaction: { mode: 'nearest', axis: 'x', intersect: false },
};

function renderRunwayChart(runway, horizonDays = 90) {
  const ctx = document.getElementById('runway-chart');
  if (!ctx || !runway) return;

  const pts = (runway.projections || []).filter(p => p.day <= horizonDays);
  const labels = pts.map(p => p.date ? fmtDate(p.date).slice(0, 6) : 'D' + p.day);
  const balances = pts.map(p => p.balance);

  if (STATE.charts.runway) STATE.charts.runway.destroy();
  STATE.charts.runway = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        data: balances,
        borderColor: '#0d9488',
        backgroundColor: 'rgba(13,148,136,0.08)',
        fill: true,
        tension: 0.4,
        borderWidth: 2.5,
        pointRadius: 3,
        pointBackgroundColor: '#0d9488',
      }]
    },
    options: { ...CHART_DEFAULTS, plugins: { ...CHART_DEFAULTS.plugins, tooltip: { ...CHART_DEFAULTS.plugins.tooltip, callbacks: { label: ctx => '₹' + ctx.parsed.y.toLocaleString('en-IN', { maximumFractionDigits: 0 }) } } } },
  });
}

function renderBreakevenChart(be) {
  const ctx = document.getElementById('breakeven-chart');
  if (!ctx || !be) return;

  const curve = be.curve_data || [];
  const labels = curve.map(p => fmt(p.revenue).replace('₹', ''));

  if (STATE.charts.breakeven) STATE.charts.breakeven.destroy();
  STATE.charts.breakeven = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        { label: 'Revenue', data: curve.map(p => p.revenue), borderColor: '#0d9488', backgroundColor: 'transparent', tension: 0, borderWidth: 2.5, borderDash: [] },
        { label: 'Total Cost', data: curve.map(p => p.cost), borderColor: '#d97706', backgroundColor: 'transparent', tension: 0, borderWidth: 2.5, borderDash: [6, 3] },
      ]
    },
    options: { ...CHART_DEFAULTS, plugins: { ...CHART_DEFAULTS.plugins, legend: { display: true, labels: { color: '#45464d', font: { size: 12 }, boxWidth: 16 } } } },
  });
}

function setRunwayHorizon(days, btn) {
  document.querySelectorAll('.chart-tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  renderRunwayChart(STATE.runwayData, days);
}

// ─── Invoice Queue Widget ─────────────────────────────────────────────────────
async function loadInvoiceQueueWidget() {
  const r = await api('GET', '/api/invoices?per_page=5&status=FLAGGED');
  if (!r.ok) return;
  const { invoices } = r.data;
  const container = document.getElementById('invoice-queue-container');
  if (!container) return;

  if (!invoices || invoices.length === 0) {
    container.innerHTML = '<div class="empty-state" style="padding:24px"><span class="material-symbols-outlined">verified</span><h3>All Clear</h3><p>No flagged invoices at this time.</p></div>';
    return;
  }

  const rows = document.createElement('div');
  for (const inv of invoices) {
    const flags = inv.anomaly_flags || [];
    const row = document.createElement('div');
    row.style.cssText = 'display:flex;align-items:center;gap:12px;padding:12px 16px;border-bottom:1px solid var(--outline-variant);cursor:pointer';
    row.addEventListener('click', () => viewInvoice(inv.id));

    const badgeEl = document.createElement('span');
    badgeEl.className = 'badge flagged';
    badgeEl.textContent = '🔴 FLAGGED';

    const info = document.createElement('div');
    info.style.flex = '1';
    const vn = document.createElement('div');
    vn.style.cssText = 'font-size:13px;font-weight:600';
    vn.textContent = inv.vendor_name || 'Unknown Vendor';
    const sub = document.createElement('div');
    sub.style.cssText = 'font-size:12px;color:var(--on-surface-variant)';
    sub.textContent = (inv.invoice_number || 'No #') + ' · ' + flags.length + ' flag(s)';
    info.appendChild(vn);
    info.appendChild(sub);

    const amt = document.createElement('div');
    amt.className = 'font-mono';
    amt.style.cssText = 'font-size:13px;font-weight:700;text-align:right;flex-shrink:0';
    amt.textContent = fmt(inv.total_amount);

    row.appendChild(badgeEl);
    row.appendChild(info);
    row.appendChild(amt);
    rows.appendChild(row);
  }

  container.innerHTML = '';
  container.appendChild(rows);
}

// ─── Ledger ───────────────────────────────────────────────────────────────────
async function loadLedger() {
  const search = document.getElementById('ledger-search')?.value || '';
  const category = document.getElementById('ledger-cat-filter')?.value || '';
  const entryType = document.getElementById('ledger-type-filter')?.value || '';
  const from = document.getElementById('ledger-date-from')?.value || '';
  const to = document.getElementById('ledger-date-to')?.value || '';

  let url = `/api/ledger/entries?page=${STATE.ledgerPage}&per_page=20`;
  if (search) url += '&search=' + encodeURIComponent(search);
  if (category) url += '&category=' + category;
  if (entryType) url += '&entry_type=' + entryType;
  if (from) url += '&date_from=' + from;
  if (to) url += '&date_to=' + to;

  const r = await api('GET', url);
  if (!r.ok) { toast('Failed to load ledger', 'error'); return; }
  const { entries, total, pages } = r.data;

  const tbody = document.getElementById('ledger-tbody');
  if (!tbody) return;
  tbody.innerHTML = '';

  if (!entries || entries.length === 0) {
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = 6;
    cell.style.textAlign = 'center';
    cell.style.padding = '32px';
    cell.textContent = 'No transactions found. Add your first entry or import a CSV.';
    cell.style.color = 'var(--on-surface-variant)';
    row.appendChild(cell);
    tbody.appendChild(row);
    return;
  }

  for (const entry of entries) {
    const tr = document.createElement('tr');
    const isCredit = entry.entry_type === 'CREDIT';

    tr.innerHTML = ''; // clear
    const cells = [
      { text: fmtDate(entry.reference_date), cls: '' },
      { text: entry.description || '—', cls: '' },
      { text: (entry.category || '').replace(/_/g, ' '), cls: 'text-muted text-sm' },
      { badge: isCredit ? 'credit' : 'debit', text: isCredit ? 'Credit' : 'Debit' },
      { text: fmt(entry.amount), cls: 'mono text-right font-bold ' + (isCredit ? 'text-secondary' : 'text-accent') },
    ];

    for (const c of cells) {
      const td = document.createElement('td');
      if (c.badge) {
        const badge = document.createElement('span');
        badge.className = 'badge ' + c.badge;
        badge.textContent = c.text;
        td.appendChild(badge);
      } else {
        td.textContent = c.text;
        if (c.cls) td.className = c.cls;
      }
      tr.appendChild(td);
    }

    // Actions
    const actionTd = document.createElement('td');
    const delBtn = document.createElement('button');
    delBtn.className = 'btn btn-ghost btn-sm';
    delBtn.title = 'Delete entry';
    const delIcon = document.createElement('span');
    delIcon.className = 'material-symbols-outlined sm';
    delIcon.style.color = 'var(--color-error)';
    delIcon.textContent = 'delete';
    delBtn.appendChild(delIcon);
    delBtn.addEventListener('click', () => deleteEntry(entry.id));
    actionTd.appendChild(delBtn);
    tr.appendChild(actionTd);

    tbody.appendChild(tr);
  }

  // Pagination
  renderPagination('ledger-pagination', STATE.ledgerPage, pages, p => { STATE.ledgerPage = p; loadLedger(); });

  // Load summary
  const sr = await api('GET', '/api/ledger/summary');
  if (sr.ok) {
    const { aggregates: agg } = sr.data;
    setText('ledger-revenue', fmt(agg.revenue));
    setText('ledger-expenses', fmt(agg.cash_out));
    setText('ledger-net', fmt(agg.cash_in - agg.cash_out));
  }
}

async function createEntry() {
  const data = {
    entry_type: document.getElementById('entry-type').value,
    category: document.getElementById('entry-category').value,
    amount: document.getElementById('entry-amount').value,
    reference_date: document.getElementById('entry-date').value,
    description: document.getElementById('entry-desc').value,
    party_name: document.getElementById('entry-party').value,
  };
  if (!data.amount) { toast('Amount is required', 'warning'); return; }

  const r = await api('POST', '/api/ledger/entries', data);
  if (r.ok) {
    closeModal('entry-modal');
    toast('Entry created successfully', 'success');
    loadLedger();
    loadDashboard();
    ['entry-amount', 'entry-desc', 'entry-party'].forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
  } else {
    toast(r.data.error || 'Failed to create entry', 'error');
  }
}

async function deleteEntry(id) {
  if (!confirm('Delete this ledger entry?')) return;
  const r = await api('DELETE', '/api/ledger/entries/' + id);
  if (r.ok) { toast('Entry deleted', 'success'); loadLedger(); loadDashboard(); }
  else toast(r.data.error || 'Delete failed', 'error');
}

async function importCSV() {
  const file = document.getElementById('csv-file-input')?.files?.[0];
  if (!file) { toast('Please select a CSV file', 'warning'); return; }
  const fd = new FormData();
  fd.append('file', file);
  const r = await api('POST', '/api/ledger/bulk-import', fd, true);
  if (r.ok) {
    closeModal('import-modal');
    toast(r.data.message || 'Import complete', 'success');
    loadLedger();
    loadDashboard();
  } else {
    toast(r.data.error || 'Import failed', 'error');
  }
}

// ─── Invoices ─────────────────────────────────────────────────────────────────
async function loadInvoices() {
  const status = document.getElementById('inv-status-filter')?.value || '';
  let url = `/api/invoices?page=${STATE.invoicePage}&per_page=15`;
  if (status) url += '&status=' + status;

  const r = await api('GET', url);
  if (!r.ok) return;
  const { invoices, counts } = r.data;

  setText('inv-count-flagged', String(counts?.flagged ?? 0));
  setText('inv-count-pending', String(counts?.pending ?? 0));
  setText('inv-count-verified', String(counts?.verified ?? 0));

  const tbody = document.getElementById('invoices-tbody');
  if (!tbody) return;
  tbody.innerHTML = '';

  if (!invoices || invoices.length === 0) {
    const tr = document.createElement('tr');
    const td = document.createElement('td');
    td.colSpan = 7;
    td.style.cssText = 'text-align:center;padding:32px;color:var(--on-surface-variant)';
    td.textContent = 'No invoices found. Upload your first receipt or invoice above.';
    tr.appendChild(td);
    tbody.appendChild(tr);
    return;
  }

  for (const inv of invoices) {
    const tr = document.createElement('tr');
    const flags = inv.anomaly_flags || [];
    const statusClass = { VERIFIED: 'verified', PENDING: 'pending', FLAGGED: 'flagged' }[inv.status] || 'pending';
    const statusIcon = { VERIFIED: '✅', PENDING: '🟡', FLAGGED: '🔴' }[inv.status] || '🟡';

    const cells = [
      inv.invoice_number || 'INV-???',
      inv.vendor_name || 'Unknown',
      fmtDate(inv.invoice_date),
      fmt(inv.total_amount),
    ];

    for (const [i, text] of cells.entries()) {
      const td = document.createElement('td');
      if (i === 3) { td.className = 'mono text-right font-bold'; }
      td.textContent = text;
      tr.appendChild(td);
    }

    // Status badge
    const statusTd = document.createElement('td');
    const badge = document.createElement('span');
    badge.className = 'badge ' + statusClass;
    badge.textContent = statusIcon + ' ' + inv.status;
    statusTd.appendChild(badge);
    tr.appendChild(statusTd);

    // Anomaly flags
    const flagTd = document.createElement('td');
    if (flags.length > 0) {
      const chip = document.createElement('span');
      chip.style.cssText = 'font-size:12px;font-weight:600;color:var(--color-error)';
      chip.textContent = flags.length + ' flag' + (flags.length > 1 ? 's' : '');
      flagTd.appendChild(chip);
    } else {
      const ok = document.createElement('span');
      ok.style.cssText = 'font-size:12px;color:var(--color-secondary)';
      ok.textContent = 'None';
      flagTd.appendChild(ok);
    }
    tr.appendChild(flagTd);

    // Actions
    const actionTd = document.createElement('td');
    actionTd.style.display = 'flex';
    actionTd.style.gap = '4px';

    const viewBtn = document.createElement('button');
    viewBtn.className = 'btn btn-outline btn-sm';
    viewBtn.textContent = 'View';
    viewBtn.addEventListener('click', () => viewInvoice(inv.id));
    actionTd.appendChild(viewBtn);

    if (inv.status !== 'VERIFIED') {
      const verifyBtn = document.createElement('button');
      verifyBtn.className = 'btn btn-secondary btn-sm';
      verifyBtn.textContent = 'Verify';
      verifyBtn.addEventListener('click', () => verifyInvoice(inv.id));
      actionTd.appendChild(verifyBtn);
    }
    const delBtn = document.createElement('button');
    delBtn.className = 'btn btn-sm';
    delBtn.style.cssText = 'color:var(--color-error);border-color:var(--color-error);background:transparent;padding:4px 8px';
    delBtn.innerHTML = '<span class="material-symbols-outlined sm">delete</span>';
    delBtn.title = 'Delete invoice';
    delBtn.addEventListener('click', () => deleteInvoice(inv.id, inv.invoice_number || inv.id));
    actionTd.appendChild(delBtn);
    tr.appendChild(actionTd);
    tbody.appendChild(tr);
  }

  renderPagination('invoices-pagination', STATE.invoicePage, r.data.pages, p => { STATE.invoicePage = p; loadInvoices(); });
}

async function viewInvoice(id) {
  const r = await api('GET', '/api/invoices/' + id);
  if (!r.ok) return;
  const inv = r.data.invoice;
  const flags = inv.anomaly_flags || [];
  const lineItems = inv.line_items || [];

  const title = document.getElementById('inv-detail-title');
  const body = document.getElementById('inv-detail-body');
  const footer = document.getElementById('inv-detail-footer');
  if (!body) return;

  title.textContent = 'Invoice ' + (inv.invoice_number || 'Details');

  const statusIcon = { VERIFIED: '✅', PENDING: '🟡', FLAGGED: '🔴' }[inv.status] || '🟡';

  // Build HTML safely
  body.innerHTML = '';

  // Summary grid
  const grid = document.createElement('div');
  grid.style.cssText = 'display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px';
  const summary_items = [
    ['Vendor', inv.vendor_name],
    ['GSTIN', inv.vendor_gstin],
    ['Invoice Date', fmtDate(inv.invoice_date)],
    ['Status', statusIcon + ' ' + inv.status],
    ['Subtotal', fmt(inv.subtotal)],
    ['Tax Amount', fmt(inv.tax_amount)],
    ['Total', fmt(inv.total_amount)],
    ['Uploaded', fmtDate(inv.created_at)],
  ];
  for (const [label, val] of summary_items) {
    const cell = document.createElement('div');
    cell.style.cssText = 'padding:10px 12px;background:var(--surface-container);border-radius:8px';
    const lbl = document.createElement('div');
    lbl.style.cssText = 'font-size:11px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;color:var(--on-surface-variant)';
    lbl.textContent = label;
    const v = document.createElement('div');
    v.style.cssText = 'font-size:14px;font-weight:600;margin-top:3px';
    v.textContent = val || '—';
    cell.appendChild(lbl);
    cell.appendChild(v);
    grid.appendChild(cell);
  }
  body.appendChild(grid);

  // Anomaly Flags
  if (flags.length > 0) {
    const flagsTitle = document.createElement('div');
    flagsTitle.style.cssText = 'font-size:13px;font-weight:700;margin-bottom:8px;color:var(--color-error)';
    flagsTitle.textContent = '⚠️ Detected Anomalies (' + flags.length + ')';
    body.appendChild(flagsTitle);
    for (const flag of flags) {
      const flagEl = document.createElement('div');
      flagEl.className = 'flag-card ' + (flag.severity || 'MEDIUM');
      const icon = document.createElement('span');
      icon.className = 'material-symbols-outlined sm';
      icon.textContent = 'warning';
      const msg = document.createElement('div');
      const typeEl = document.createElement('div');
      typeEl.style.cssText = 'font-size:11px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;margin-bottom:2px';
      typeEl.textContent = (flag.type || '').replace(/_/g, ' ') + ' · ' + (flag.severity || '') + ' · ' + ((flag.confidence || 0) * 100).toFixed(0) + '% confidence';
      const msgText = document.createElement('div');
      msgText.style.fontSize = '13px';
      msgText.textContent = flag.message || '';
      msg.appendChild(typeEl);
      msg.appendChild(msgText);
      flagEl.appendChild(icon);
      flagEl.appendChild(msg);
      body.appendChild(flagEl);
    }
  } else {
    const ok = document.createElement('div');
    ok.style.cssText = 'padding:12px;background:rgba(13,148,136,0.08);border-radius:8px;font-size:13px;color:var(--color-secondary);font-weight:600';
    ok.textContent = '✅ No anomalies detected — invoice appears clean.';
    body.appendChild(ok);
  }

  // Line Items
  if (lineItems.length > 0) {
    const liTitle = document.createElement('div');
    liTitle.style.cssText = 'font-size:13px;font-weight:700;margin:16px 0 8px';
    liTitle.textContent = 'Line Items';
    body.appendChild(liTitle);
    for (const item of lineItems) {
      const liEl = document.createElement('div');
      liEl.style.cssText = 'display:flex;justify-content:space-between;padding:8px 12px;background:var(--surface-container-low);border-radius:6px;margin-bottom:4px;font-size:13px';
      const desc = document.createElement('span');
      desc.textContent = item.description || '—';
      const amt = document.createElement('span');
      amt.className = 'font-mono font-bold';
      amt.textContent = fmt(item.amount);
      liEl.appendChild(desc);
      liEl.appendChild(amt);
      body.appendChild(liEl);
    }
  }

  // Footer buttons
  footer.innerHTML = '';
  const closeBtn = document.createElement('button');
  closeBtn.className = 'btn btn-outline';
  closeBtn.textContent = 'Close';
  closeBtn.addEventListener('click', () => closeModal('invoice-detail-modal'));
  footer.appendChild(closeBtn);

  if (inv.status !== 'VERIFIED') {
    const verifyBtn = document.createElement('button');
    verifyBtn.className = 'btn btn-secondary';
    verifyBtn.innerHTML = '<span class="material-symbols-outlined sm">check_circle</span> Verify & Create Ledger Entry';
    verifyBtn.addEventListener('click', () => { closeModal('invoice-detail-modal'); verifyInvoice(id); });
    footer.appendChild(verifyBtn);
  }

  // Delete button always shown
  const delBtn = document.createElement('button');
  delBtn.className = 'btn btn-outline';
  delBtn.style.cssText = 'color:var(--color-error);border-color:var(--color-error);margin-left:auto';
  delBtn.innerHTML = '<span class="material-symbols-outlined sm">delete</span> Delete Invoice';
  delBtn.addEventListener('click', () => { closeModal('invoice-detail-modal'); deleteInvoice(id, inv.invoice_number || id); });
  footer.appendChild(delBtn);

  openModal('invoice-detail-modal');
}

async function verifyInvoice(id) {
  const r = await api('POST', '/api/invoices/' + id + '/verify');
  if (r.ok) {
    toast('Invoice verified. Ledger entry created.', 'success');
    loadInvoices();
    loadDashboard();
  } else {
    toast(r.data.error || 'Verification failed', 'error');
  }
}

async function deleteInvoice(id, label) {
  if (!confirm(`Delete invoice "${label}"? This cannot be undone.`)) return;
  const r = await api('DELETE', '/api/invoices/' + id);
  if (r.ok) {
    toast('Invoice deleted', 'success');
    loadInvoices();
    loadDashboard();
  } else {
    toast(r.data?.error || 'Delete failed', 'error');
  }
}

// OCR Upload
function handleDragOver(e) { e.preventDefault(); document.getElementById('ocr-dropzone').classList.add('dragover'); }
function handleDragLeave(e) { document.getElementById('ocr-dropzone').classList.remove('dragover'); }
function handleDrop(e) {
  e.preventDefault();
  document.getElementById('ocr-dropzone').classList.remove('dragover');
  const file = e.dataTransfer?.files?.[0];
  if (file) processUpload(file);
}
function uploadInvoice(e) {
  const file = e.target?.files?.[0];
  if (file) processUpload(file);
}

async function processUpload(file) {
  const progress = document.getElementById('upload-progress');
  const progressFill = document.getElementById('upload-progress-fill');
  const status = document.getElementById('upload-status');
  if (progress) progress.classList.remove('hidden');

  setText('upload-status', 'Uploading ' + file.name + '...');
  if (progressFill) progressFill.style.width = '30%';

  const fd = new FormData();
  fd.append('file', file);

  // Include manual override fields if provided
  const vendorName = document.getElementById('ocr-vendor-name')?.value?.trim();
  const invoiceNumber = document.getElementById('ocr-invoice-number')?.value?.trim();
  const totalAmount = document.getElementById('ocr-total-amount')?.value?.trim();
  const invoiceDate = document.getElementById('ocr-invoice-date')?.value?.trim();
  if (vendorName) fd.append('vendor_name', vendorName);
  if (invoiceNumber) fd.append('invoice_number', invoiceNumber);
  if (totalAmount) fd.append('total_amount', totalAmount);
  if (invoiceDate) fd.append('invoice_date', invoiceDate);

  setText('upload-status', 'Running OCR extraction...');
  if (progressFill) progressFill.style.width = '60%';

  const r = await api('POST', '/api/invoices/upload', fd, true);

  if (progressFill) progressFill.style.width = '100%';

  if (r.ok) {
    const { invoice, anomalies_detected, ocr_confidence } = r.data;
    const confidenceNote = ocr_confidence ? '' : ' (Manual fields used)';
    const msg = anomalies_detected > 0
      ? `⚠️ ${anomalies_detected} anomaly(ies) detected — marked as FLAGGED`
      : `✅ Invoice processed successfully${confidenceNote} — no anomalies`;
    toast(msg, anomalies_detected > 0 ? 'warning' : 'success');
    setTimeout(() => {
      if (progress) progress.classList.add('hidden');
      if (progressFill) progressFill.style.width = '0%';
    }, 1500);
    // Clear manual override fields
    ['ocr-vendor-name', 'ocr-invoice-number', 'ocr-total-amount', 'ocr-invoice-date'].forEach(id => {
      const el = document.getElementById(id); if (el) el.value = '';
    });
    loadInvoices();
    loadDashboard();
  } else {
    toast(r.data.error || 'Upload failed', 'error');
    if (progress) progress.classList.add('hidden');
  }
  // Reset file input
  const fi = document.getElementById('file-input');
  if (fi) fi.value = '';
}

// ─── Directory ────────────────────────────────────────────────────────────────
async function loadDirectory(type = '') {
  let url = '/api/ledger/directory';
  if (type) url += '?type=' + type;
  const r = await api('GET', url);
  const tbody = document.getElementById('directory-tbody');
  if (!r.ok || !tbody) return;
  tbody.innerHTML = '';

  if (!r.data.contacts?.length) {
    const tr = document.createElement('tr');
    const td = document.createElement('td');
    td.colSpan = 6; td.style.cssText = 'text-align:center;padding:24px;color:var(--on-surface-variant)';
    td.textContent = 'No contacts yet. Add your first customer or supplier.';
    tr.appendChild(td); tbody.appendChild(tr);
    return;
  }

  for (const c of r.data.contacts) {
    const tr = document.createElement('tr');
    const td0 = document.createElement('td'); td0.style.fontWeight = '600'; td0.textContent = c.name;
    const td1 = document.createElement('td');
    const badge = document.createElement('span');
    badge.className = 'badge ' + (c.entity_type === 'CUSTOMER' ? 'credit' : 'debit');
    badge.textContent = c.entity_type;
    td1.appendChild(badge);
    const td2 = document.createElement('td'); td2.className = 'font-mono text-sm'; td2.textContent = c.gstin || '—';
    const td3 = document.createElement('td'); td3.className = 'font-mono font-bold text-right'; td3.textContent = fmt(c.outstanding_balance);
    const td4 = document.createElement('td'); td4.textContent = c.payment_terms_days + ' days';
    const td5 = document.createElement('td');
    const stars = '★'.repeat(Math.round(c.settlement_speed_score / 2)) + '☆'.repeat(5 - Math.round(c.settlement_speed_score / 2));
    td5.style.color = 'var(--color-accent)'; td5.textContent = stars + ' (' + (c.settlement_speed_score || 0) + '/10)';
    // Delete button
    const tdDel = document.createElement('td');
    const delBtn = document.createElement('button');
    delBtn.className = 'btn btn-sm';
    delBtn.style.cssText = 'color:var(--color-error);background:transparent;border:none;padding:2px 6px';
    delBtn.innerHTML = '<span class="material-symbols-outlined sm">delete</span>';
    delBtn.title = 'Delete contact';
    delBtn.addEventListener('click', async () => {
      if (!confirm(`Delete contact "${c.name}"?`)) return;
      const rd = await api('DELETE', '/api/ledger/directory/' + c.id);
      if (rd.ok) { toast('Contact deleted', 'success'); loadDirectory(''); }
      else toast(rd.data?.error || 'Failed', 'error');
    });
    tdDel.appendChild(delBtn);
    for (const td of [td0, td1, td2, td3, td4, td5, tdDel]) tr.appendChild(td);
    tbody.appendChild(tr);
  }
}

function setDirTab(tab) {
  ['all', 'customer', 'supplier'].forEach(t => {
    const btn = document.getElementById('dir-tab-' + t);
    if (btn) btn.classList.toggle('active', t === tab);
  });
}

async function createContact() {
  const name = document.getElementById('contact-name').value.trim();
  const entity_type = document.getElementById('contact-type').value;
  if (!name) { toast('Contact name is required', 'warning'); return; }
  if (!entity_type) { toast('Please select Customer or Supplier', 'warning'); return; }

  const data = {
    entity_type,
    name,
    gstin: document.getElementById('contact-gstin').value.trim(),
    payment_terms_days: parseInt(document.getElementById('contact-terms').value) || 30,
    outstanding_balance: parseFloat(document.getElementById('contact-balance').value) || 0,
    phone: document.getElementById('contact-phone').value.trim(),
  };
  const r = await api('POST', '/api/ledger/directory', data);
  if (r.ok) {
    closeModal('contact-modal');
    toast('Contact saved successfully', 'success');
    // Reset form
    ['contact-name', 'contact-gstin', 'contact-phone'].forEach(id => {
      const el = document.getElementById(id); if (el) el.value = '';
    });
    document.getElementById('contact-balance').value = '0';
    document.getElementById('contact-terms').value = '30';
    loadDirectory('');
  } else {
    toast(r.data.error || 'Failed to save contact', 'error');
  }
}

// ─── Inventory ────────────────────────────────────────────────────────────────
async function loadInventory() {
  const r = await api('GET', '/api/ledger/inventory');
  const tbody = document.getElementById('inventory-tbody');
  if (!r.ok || !tbody) return;
  tbody.innerHTML = '';

  if (!r.data.items?.length) {
    const tr = document.createElement('tr');
    const td = document.createElement('td'); td.colSpan = 7; td.style.cssText = 'text-align:center;padding:24px;color:var(--on-surface-variant)'; td.textContent = 'No inventory items yet.';
    tr.appendChild(td); tbody.appendChild(tr); return;
  }

  for (const item of r.data.items) {
    const tr = document.createElement('tr');
    const stockClass = item.is_low_stock ? 'low-stock' : 'in-stock';
    const stockLabel = item.is_low_stock ? '⚠️ Low Stock' : '✅ In Stock';
    const tds = [
      { text: item.sku || '—', cls: 'font-mono text-sm text-muted' },
      { text: item.name, cls: 'font-bold' },
      { text: fmtNum(item.unit_volume), cls: 'font-mono text-right' },
      { text: fmt(item.unit_cost), cls: 'font-mono text-right' },
      { text: fmt(item.selling_price), cls: 'font-mono text-right text-secondary font-bold' },
      { text: fmt(item.cogs), cls: 'font-mono text-right' },
    ];
    for (const { text, cls } of tds) { const td = document.createElement('td'); td.className = cls || ''; td.textContent = text; tr.appendChild(td); }
    const badgeTd = document.createElement('td');
    const badge = document.createElement('span');
    badge.className = 'badge ' + stockClass;
    badge.textContent = stockLabel;
    badgeTd.appendChild(badge);
    tr.appendChild(badgeTd);
    // Delete button
    const delTd = document.createElement('td');
    const delBtn = document.createElement('button');
    delBtn.className = 'btn btn-sm';
    delBtn.style.cssText = 'color:var(--color-error);background:transparent;border:none;padding:2px 6px';
    delBtn.innerHTML = '<span class="material-symbols-outlined sm">delete</span>';
    delBtn.title = 'Delete item';
    delBtn.addEventListener('click', async () => {
      if (!confirm(`Delete "${item.name}"?`)) return;
      const rd = await api('DELETE', '/api/ledger/inventory/' + item.id);
      if (rd.ok) { toast('Item deleted', 'success'); loadInventory(); }
      else toast(rd.data?.error || 'Failed', 'error');
    });
    delTd.appendChild(delBtn);
    tr.appendChild(delTd);
    tbody.appendChild(tr);
  }
}

async function createInventoryItem() {
  const name = document.getElementById('inv-name').value.trim();
  if (!name) { toast('Item name is required', 'warning'); return; }

  const data = {
    sku: document.getElementById('inv-sku').value.trim(),
    name,
    unit_volume: parseInt(document.getElementById('inv-stock').value) || 0,
    unit_cost: parseFloat(document.getElementById('inv-cost').value) || 0,
    selling_price: parseFloat(document.getElementById('inv-price').value) || 0,
    reorder_threshold: parseInt(document.getElementById('inv-threshold').value) || 10,
    turnover_frequency_days: parseFloat(document.getElementById('inv-turnover').value) || 30,
  };
  const r = await api('POST', '/api/ledger/inventory', data);
  if (r.ok) {
    closeModal('inventory-modal');
    toast('Item saved successfully', 'success');
    // Reset form
    ['inv-sku', 'inv-name'].forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
    ['inv-stock', 'inv-cost', 'inv-price'].forEach(id => { const el = document.getElementById(id); if (el) el.value = '0'; });
    document.getElementById('inv-threshold').value = '10';
    document.getElementById('inv-turnover').value = '30';
    loadInventory();
  } else {
    toast(r.data.error || 'Failed to save item', 'error');
  }
}

// ─── Forecasts ────────────────────────────────────────────────────────────────
async function seedDemoData() {
  const btn = document.getElementById('btn-seed-demo');
  if (btn) { btn.disabled = true; btn.innerHTML = '<div class="spinner"></div> Seeding...'; }
  const r = await api('POST', '/api/analytics/seed-demo');
  if (btn) { btn.disabled = false; btn.innerHTML = '<span class="material-symbols-outlined sm">science</span> Load Demo Data'; }

  if (r.ok) {
    toast(r.data.message || 'Demo data loaded!', r.data.seeded > 0 ? 'success' : 'info');
    if (r.data.seeded > 0) {
      loadDashboard();
      loadLedger();
      loadForecasts();
    }
  } else {
    toast(r.data?.error || 'Failed to seed demo data', 'error');
  }
}

async function clearAllLedger() {
  if (!confirm('⚠️ This will permanently delete ALL ledger entries. Are you sure?')) return;
  const r = await api('DELETE', '/api/ledger/entries/clear-all');
  if (r.ok) {
    toast(`Cleared ${r.data.deleted} entries. You can reload demo data now.`, 'success');
    loadDashboard();
    loadLedger();
    loadForecasts();
  } else {
    toast(r.data?.error || 'Failed to clear data', 'error');
  }
}

async function loadForecasts() {
  const r = await api('GET', '/api/analytics/runway');
  const rb = await api('GET', '/api/analytics/break-even');
  const rh = await api('GET', '/api/analytics/health-score');

  if (r.ok) {
    const runway = r.data;
    setText('horizon-30', fmt(runway.horizon_30));
    setText('horizon-60', fmt(runway.horizon_60));
    setText('horizon-90', fmt(runway.horizon_90));
    // Render full 90-day chart on forecasts page
    const ctx = document.getElementById('forecast-runway-chart');
    if (ctx) {
      if (STATE.charts.forecastRunway) STATE.charts.forecastRunway.destroy();
      const pts = runway.projections || [];
      STATE.charts.forecastRunway = new Chart(ctx, {
        type: 'line',
        data: {
          labels: pts.map(p => fmtDate(p.date).slice(0, 6)),
          datasets: [{
            data: pts.map(p => p.balance),
            borderColor: '#0d9488', backgroundColor: 'rgba(13,148,136,0.08)', fill: true,
            tension: 0.4, borderWidth: 2.5, pointRadius: 2,
          }]
        },
        options: CHART_DEFAULTS
      });
    }
  }

  if (rb.ok) {
    const be = rb.data;
    setText('be-monthly', fmt(be.break_even_revenue_monthly));
    setText('be-cmr', (be.contribution_margin_ratio || 0) + '%');
    setText('be-fixed', fmt(be.fixed_costs_monthly));
    setText('be-margin', (be.current_margin_pct || 0) + '%');

    const ctx2 = document.getElementById('forecast-be-chart');
    if (ctx2) {
      if (STATE.charts.forecastBE) STATE.charts.forecastBE.destroy();
      const curve = be.curve_data || [];
      STATE.charts.forecastBE = new Chart(ctx2, {
        type: 'line',
        data: {
          labels: curve.map(p => fmt(p.revenue).replace('₹', '')),
          datasets: [
            { label: 'Revenue', data: curve.map(p => p.revenue), borderColor: '#0d9488', tension: 0, borderWidth: 2 },
            { label: 'Total Cost', data: curve.map(p => p.cost), borderColor: '#d97706', tension: 0, borderWidth: 2, borderDash: [6, 3] }
          ]
        },
        options: { ...CHART_DEFAULTS, plugins: { ...CHART_DEFAULTS.plugins, legend: { display: true } } }
      });
    }
  }

  if (rh.ok) {
    const h = rh.data;
    const signals = document.getElementById('warning-signals');
    if (signals) {
      signals.innerHTML = '';
      const warnings = [];
      if (h.runway_days < 90) warnings.push({ severity: 'HIGH', msg: `Cash runway is only ${h.runway_days} days — below the 90-day safety threshold. Take immediate action to reduce burn or accelerate collections.` });
      if (h.profitability < 10) warnings.push({ severity: 'MEDIUM', msg: 'Profitability score is low. Operating margins may be contracting — review COGS and OPEX trends.' });
      if (h.liquidity < 10) warnings.push({ severity: 'MEDIUM', msg: 'Liquidity is under pressure. Ensure receivables are collected promptly to maintain working capital.' });
      if (h.score >= 75) warnings.push({ severity: 'GOOD', msg: `Strong financial health (${h.score}/100, Grade ${h.grade}). Continue current trajectory and consider controlled expansion.` });

      for (const w of warnings) {
        const card = document.createElement('div');
        card.className = 'flag-card ' + (w.severity === 'GOOD' ? 'LOW' : w.severity);
        const icon = document.createElement('span');
        icon.className = 'material-symbols-outlined sm';
        icon.textContent = w.severity === 'GOOD' ? 'check_circle' : 'warning';
        const msg = document.createElement('div');
        msg.style.fontSize = '13px';
        msg.textContent = w.msg;
        card.appendChild(icon);
        card.appendChild(msg);
        signals.appendChild(card);
      }
      if (warnings.length === 0) { signals.textContent = 'Financial signals look stable. No deterioration warnings detected.'; }
    }
  }
}

// ─── Location Intelligence ────────────────────────────────────────────────────
function fillLocation(name, rent, footfall, competitors, niche, parking, notes) {
  const set = (id, val) => { const el = document.getElementById(id); if (el) el.value = val; };
  set('loc-name', name);
  set('loc-rent', rent);
  set('loc-footfall', footfall);
  set('loc-competitors', competitors);
  set('loc-niche', niche);
  set('loc-parking', parking);
  set('loc-notes', notes);
  toast('Pre-filled with real data for ' + name.split(',')[0], 'info');
}

async function evaluateLocation() {
  const data = {
    location_name: document.getElementById('loc-name').value,
    monthly_rent: document.getElementById('loc-rent').value,
    footfall_estimate: document.getElementById('loc-footfall').value,
    competitor_count: document.getElementById('loc-competitors').value || 0,
    niche_fit_score: document.getElementById('loc-niche').value || 5,
    parking_access_score: document.getElementById('loc-parking').value || 5,
    notes: document.getElementById('loc-notes').value || '',
  };
  if (!data.location_name || !data.monthly_rent) { toast('Location name and rent are required', 'warning'); return; }

  const r = await api('POST', '/api/analytics/location/evaluate', data);
  const resultEl = document.getElementById('loc-result');
  if (!r.ok) { toast(r.data.error || 'Evaluation failed', 'error'); return; }

  const { evaluation: ev, score_breakdown: sb } = r.data;
  resultEl.classList.remove('hidden');
  resultEl.innerHTML = '';

  const scoreColor = ev.feasibility_score >= 70 ? 'var(--color-secondary)' : ev.feasibility_score >= 50 ? 'var(--color-accent)' : 'var(--color-error)';

  const header = document.createElement('div');
  header.style.cssText = 'text-align:center;padding:16px;background:var(--surface-container);border-radius:12px;margin-bottom:12px';
  const scoreNum = document.createElement('div');
  scoreNum.className = 'font-mono';
  scoreNum.style.cssText = 'font-size:40px;font-weight:800;color:' + scoreColor;
  scoreNum.textContent = ev.feasibility_score.toFixed(1) + '/100';
  const scoreGrade = document.createElement('div');
  scoreGrade.style.cssText = 'font-size:14px;font-weight:600;color:var(--on-surface-variant)';
  scoreGrade.textContent = 'Feasibility Grade: ' + sb.rating;
  const revNeeded = document.createElement('div');
  revNeeded.style.cssText = 'font-size:13px;margin-top:8px;color:var(--on-surface-variant)';
  revNeeded.textContent = 'Revenue needed: ' + fmt(sb.revenue_needed_monthly) + '/month';
  header.appendChild(scoreNum); header.appendChild(scoreGrade); header.appendChild(revNeeded);
  resultEl.appendChild(header);

  toast('Location evaluated: Score ' + ev.feasibility_score.toFixed(1) + '/100', ev.feasibility_score >= 60 ? 'success' : 'warning');
  loadLocationHistory();
}

async function loadLocationHistory() {
  const r = await api('GET', '/api/analytics/location/history');
  const container = document.getElementById('location-history');
  if (!r.ok || !container) return;

  const locs = r.data.evaluations || [];
  if (!locs.length) { container.textContent = 'No locations evaluated yet. Use the form to evaluate your first site.'; return; }

  container.innerHTML = '';
  for (const loc of locs) {
    const scoreColor = loc.feasibility_score >= 70 ? 'var(--color-secondary)' : loc.feasibility_score >= 50 ? 'var(--color-accent)' : 'var(--color-error)';
    const el = document.createElement('div');
    el.style.cssText = 'display:flex;align-items:center;gap:12px;padding:12px 16px;border-bottom:1px solid var(--outline-variant)';
    const name = document.createElement('div');
    name.style.flex = '1';
    const nameEl = document.createElement('div');
    nameEl.style.cssText = 'font-size:13px;font-weight:600';
    nameEl.textContent = loc.location_name;
    const rent = document.createElement('div');
    rent.style.cssText = 'font-size:12px;color:var(--on-surface-variant)';
    rent.textContent = fmt(loc.monthly_rent) + '/month · ' + loc.footfall_estimate + ' footfall';
    name.appendChild(nameEl); name.appendChild(rent);
    const score = document.createElement('div');
    score.className = 'font-mono font-bold';
    score.style.color = scoreColor;
    score.textContent = loc.feasibility_score.toFixed(1) + '/100';
    // Delete button
    const delBtn = document.createElement('button');
    delBtn.className = 'btn btn-sm';
    delBtn.style.cssText = 'color:var(--color-error);background:transparent;border:none;padding:2px 6px;flex-shrink:0';
    delBtn.innerHTML = '<span class="material-symbols-outlined sm">delete</span>';
    delBtn.title = 'Delete evaluation';
    delBtn.addEventListener('click', async () => {
      if (!confirm(`Delete evaluation for "${loc.location_name}"?`)) return;
      const rd = await api('DELETE', '/api/analytics/location/' + loc.id);
      if (rd.ok) { toast('Evaluation deleted', 'success'); loadLocationHistory(); }
      else toast(rd.data?.error || 'Failed', 'error');
    });
    el.appendChild(name); el.appendChild(score); el.appendChild(delBtn);
    container.appendChild(el);
  }
}

// ─── Financing ────────────────────────────────────────────────────────────────
async function loadFinancing() {
  const r = await api('GET', '/api/analytics/creditworthiness');
  if (r.ok) {
    const d = r.data;
    setText('dscr-value', d.dscr?.toFixed(2) ?? '—');
    setText('dscr-rating', d.rating);
    setText('dscr-desc', d.rating_description);
    setText('dscr-wc', fmt(d.working_capital));
    setText('dscr-cr', fmtNum(d.current_ratio, 2) + 'x');
    const color = d.dscr >= 2 ? 'var(--color-secondary)' : d.dscr >= 1 ? 'var(--color-accent)' : 'var(--color-error)';
    const scoreEl = document.getElementById('dscr-value');
    if (scoreEl) scoreEl.style.color = color;
  }

  const rp = await api('GET', '/api/analytics/investor-profile');
  if (rp.ok) {
    const p = rp.data;
    const body = document.getElementById('investor-profile-body');
    if (!body) return;
    body.innerHTML = '';
    const is = p.income_statement;
    const items = [
      ['Monthly Revenue', fmt(is.revenue)],
      ['Gross Profit', fmt(is.gross_profit) + ' (' + is.gross_margin_pct + '%)'],
      ['Operating Expenses', fmt(is.opex)],
      ['Net Profit', fmt(is.net_profit) + ' (' + is.net_margin_pct + '%)'],
      ['Cash Balance', fmt(p.balance_sheet_summary?.cash)],
      ['Receivables', fmt(p.balance_sheet_summary?.receivables)],
      ['Health Score', p.health_score + '/100 (' + p.health_grade + ')'],
      ['DSCR', p.creditworthiness?.dscr?.toFixed(2) + ' (' + p.creditworthiness?.rating + ')'],
    ];
    const grid = document.createElement('div');
    grid.style.cssText = 'display:grid;grid-template-columns:1fr 1fr;gap:8px';
    for (const [label, val] of items) {
      const cell = document.createElement('div');
      cell.style.cssText = 'padding:8px 10px;background:var(--surface-container);border-radius:6px';
      const lbl = document.createElement('div');
      lbl.style.cssText = 'font-size:11px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;color:var(--on-surface-variant)';
      lbl.textContent = label;
      const v = document.createElement('div');
      v.className = 'font-mono font-bold';
      v.style.cssText = 'font-size:13px;margin-top:3px';
      v.textContent = val;
      cell.appendChild(lbl); cell.appendChild(v);
      grid.appendChild(cell);
    }
    body.appendChild(grid);
  }
}

async function exportInvestorReport() {
  // Trigger the Markdown report download.
  // We use fetch + Blob approach so the Bearer token is sent properly.
  const r = await api('GET', '/api/analytics/investor-profile/export');
  if (!r.ok) {
    toast('Export failed — ' + (r.data?.error || 'unknown error'), 'error');
    return;
  }
  // The response is a text/markdown string; re-fetch with a blob to trigger download.
  try {
    const opts = {
      method: 'GET',
      headers: { 'Authorization': 'Bearer ' + STATE.token },
      credentials: 'include',
    };
    const raw = await fetch('/api/analytics/investor-profile/export', opts);
    const blob = await raw.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    a.href = url;
    a.download = `investor_report_${ts}.md`;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 1000);
    toast('Investor report downloaded!', 'success');
  } catch (e) {
    toast('Download failed: ' + e.message, 'error');
  }
}


function simulateLoan() {
  const amount = parseFloat(document.getElementById('loan-amount').value) || 0;
  const rate = parseFloat(document.getElementById('loan-rate').value) || 12;
  const tenure = parseInt(document.getElementById('loan-tenure').value) || 36;

  const r = rate / 12 / 100;
  const emi = amount * r * Math.pow(1 + r, tenure) / (Math.pow(1 + r, tenure) - 1);
  const totalPaid = emi * tenure;
  const totalInterest = totalPaid - amount;

  const result = document.getElementById('loan-result');
  if (!result) return;
  result.classList.remove('hidden');
  result.innerHTML = '';
  const items = [
    ['Monthly EMI', fmt(emi)],
    ['Total Payment', fmt(totalPaid)],
    ['Total Interest', fmt(totalInterest)],
    ['Interest %', (totalInterest / amount * 100).toFixed(1) + '% of principal'],
  ];
  const grid = document.createElement('div');
  grid.style.cssText = 'display:grid;grid-template-columns:1fr 1fr;gap:10px';
  for (const [label, val] of items) {
    const cell = document.createElement('div');
    const lbl = document.createElement('div');
    lbl.style.cssText = 'font-size:11px;font-weight:700;color:var(--on-surface-variant);text-transform:uppercase;margin-bottom:3px';
    lbl.textContent = label;
    const v = document.createElement('div');
    v.className = 'font-mono font-bold';
    v.style.fontSize = '15px';
    v.textContent = val;
    cell.appendChild(lbl); cell.appendChild(v);
    grid.appendChild(cell);
  }
  result.appendChild(grid);
  toast('EMI calculated: ' + fmt(emi) + '/month', 'info');
}

// ─── Cap Table ────────────────────────────────────────────────────────────────
async function loadCapTable() {
  const r = await api('GET', '/api/analytics/cap-table');
  if (!r.ok) return;
  const { entries, total_equity_allocated, total_invested, unallocated } = r.data;

  const tbody = document.getElementById('captable-tbody');
  if (tbody) {
    tbody.innerHTML = '';
    for (const e of entries) {
      const tr = document.createElement('tr');
      const typeColors = { FOUNDER: '#0f172a', INVESTOR: '#0d9488', POOL: '#d97706' };
      const tds = [
        { text: e.stakeholder_name, cls: 'font-bold' },
        { badge: e.stakeholder_type, color: typeColors[e.stakeholder_type] },
        { text: e.round_name || '—', cls: 'text-muted text-sm' },
        { text: e.equity_percentage?.toFixed(1) + '%', cls: 'font-mono font-bold text-right' },
        { text: fmtNum(e.shares_count), cls: 'font-mono text-right' },
        { text: fmt(e.invested_amount), cls: 'font-mono text-right' },
      ];
      for (const t of tds) {
        const td = document.createElement('td');
        if (t.badge) {
          const badge = document.createElement('span');
          badge.className = 'badge';
          badge.style.background = (typeColors[t.badge] || '#0f172a') + '15';
          badge.style.color = typeColors[t.badge] || '#0f172a';
          badge.textContent = t.badge;
          td.appendChild(badge);
        } else {
          td.className = t.cls || '';
          td.textContent = t.text;
        }
        tr.appendChild(td);
      }
      // Delete button
      const delTd = document.createElement('td');
      const delBtn = document.createElement('button');
      delBtn.className = 'btn btn-sm';
      delBtn.style.cssText = 'color:var(--color-error);background:transparent;border:none;padding:2px 6px';
      delBtn.innerHTML = '<span class="material-symbols-outlined sm">delete</span>';
      delBtn.title = 'Remove from cap table';
      delBtn.addEventListener('click', async () => {
        if (!confirm(`Remove "${e.stakeholder_name}" from cap table?`)) return;
        const rd = await api('DELETE', '/api/analytics/cap-table/' + e.id);
        if (rd.ok) { toast('Entry removed', 'success'); loadCapTable(); }
        else toast(rd.data?.error || 'Failed', 'error');
      });
      delTd.appendChild(delBtn);
      tr.appendChild(delTd);
      tbody.appendChild(tr);
    }
  }


  // Donut chart
  const ctx = document.getElementById('cap-chart');
  if (ctx && entries.length > 0) {
    if (STATE.charts.cap) STATE.charts.cap.destroy();
    const COLORS = ['#0f172a', '#0d9488', '#d97706', '#7c3aed', '#dc2626', '#0891b2'];
    STATE.charts.cap = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: entries.map(e => e.stakeholder_name),
        datasets: [{ data: entries.map(e => e.equity_percentage), backgroundColor: COLORS.slice(0, entries.length), borderWidth: 2, borderColor: '#ffffff' }]
      },
      options: {
        responsive: false,
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => ctx.label + ': ' + ctx.raw + '%' } } },
        cutout: '65%'
      }
    });

    // Legend
    const legend = document.getElementById('cap-legend');
    if (legend) {
      legend.innerHTML = '';
      entries.forEach((e, i) => {
        const item = document.createElement('div');
        item.className = 'cap-legend-item';
        const dot = document.createElement('div');
        dot.className = 'cap-dot';
        dot.style.background = COLORS[i] || '#ccc';
        const info = document.createElement('div');
        info.style.flex = '1';
        const name = document.createElement('div');
        name.style.cssText = 'font-size:13px;font-weight:600';
        name.textContent = e.stakeholder_name;
        const pct = document.createElement('div');
        pct.style.cssText = 'font-size:12px;color:var(--on-surface-variant)';
        pct.textContent = e.equity_percentage?.toFixed(1) + '% · ' + e.stakeholder_type;
        info.appendChild(name); info.appendChild(pct);
        item.appendChild(dot); item.appendChild(info);
        legend.appendChild(item);
      });
    }
  }
}

async function addStakeholder() {
  const data = {
    stakeholder_name: document.getElementById('sh-name').value,
    stakeholder_type: document.getElementById('sh-type').value,
    equity_percentage: document.getElementById('sh-equity').value,
    shares_count: document.getElementById('sh-shares').value,
    invested_amount: document.getElementById('sh-invested').value,
    round_name: document.getElementById('sh-round').value,
  };
  const r = await api('POST', '/api/analytics/cap-table', data);
  if (r.ok) { closeModal('stakeholder-modal'); toast('Stakeholder added', 'success'); loadCapTable(); }
  else toast(r.data.error || 'Failed', 'error');
}

async function simulateDilution() {
  const data = {
    new_investment: document.getElementById('dil-investment').value,
    pre_money_valuation: document.getElementById('dil-valuation').value,
  };
  const r = await api('POST', '/api/analytics/dilution-simulator', data);
  const result = document.getElementById('dil-result');
  if (!r.ok || !result) { toast(r.data?.error || 'Failed', 'error'); return; }
  result.classList.remove('hidden');
  result.innerHTML = '';

  const d = r.data;
  const summary = document.createElement('div');
  summary.style.cssText = 'font-size:13px;font-weight:600;margin-bottom:10px;padding:10px;background:var(--surface-container);border-radius:8px';
  summary.textContent = `Post-money valuation: ${fmt(d.post_money_valuation)} · New investor gets ${d.new_investor_equity_pct?.toFixed(1)}%`;
  result.appendChild(summary);

  const table = document.createElement('table');
  table.className = 'data-table';
  table.style.fontSize = '12px';
  const thead = document.createElement('thead');
  thead.innerHTML = '<tr><th>Stakeholder</th><th class="text-right">Before</th><th class="text-right">After</th><th class="text-right">Dilution</th></tr>';
  table.appendChild(thead);
  const tbody = document.createElement('tbody');
  for (const row of d.cap_table_after) {
    const tr = document.createElement('tr');
    const cells = [row.stakeholder, row.before + '%', row.after + '%', '-' + row.dilution + '%'];
    cells.forEach((c, i) => {
      const td = document.createElement('td');
      td.className = i > 0 ? 'font-mono text-right' : '';
      if (i === 3) td.style.color = 'var(--color-error)';
      td.textContent = c;
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  result.appendChild(table);
}

// ─── AI Advisor ───────────────────────────────────────────────────────────────
function openAdvisor() {
  document.getElementById('advisor-drawer').classList.add('open');
  document.getElementById('drawer-overlay').classList.add('open');
  document.getElementById('chat-input')?.focus();
}

function closeAdvisor() {
  document.getElementById('advisor-drawer').classList.remove('open');
  document.getElementById('drawer-overlay').classList.remove('open');
}

async function loadQuickInsights() {
  const r = await api('GET', '/api/advisor/quick-insights');
  if (!r.ok) return;
  const container = document.getElementById('quick-prompts');
  if (!container) return;
  container.innerHTML = '';
  for (const insight of r.data.insights || []) {
    const btn = document.createElement('button');
    btn.className = 'quick-prompt-btn';
    btn.textContent = insight;
    btn.addEventListener('click', () => askQuestion(insight));
    container.appendChild(btn);
  }
}

function askQuestion(question) {
  const input = document.getElementById('chat-input');
  if (input) { input.value = question; sendMessage(); }
}

async function sendMessage() {
  const input = document.getElementById('chat-input');
  const question = input?.value?.trim();
  if (!question) return;

  addChatBubble(question, 'user');
  if (input) input.value = '';

  // Typing indicator
  const typingEl = document.createElement('div');
  typingEl.className = 'chat-bubble typing ai';
  typingEl.innerHTML = '<div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>';
  const chatMessages = document.getElementById('chat-messages');
  if (chatMessages) { chatMessages.appendChild(typingEl); chatMessages.scrollTop = chatMessages.scrollHeight; }

  const r = await api('POST', '/api/advisor/chat', { question });
  typingEl.remove();

  if (r.ok) {
    addChatBubble(r.data.answer, 'ai', r.data.source);
  } else {
    addChatBubble('I\'m having trouble processing that right now. Please try again.', 'ai');
  }
}

function addChatBubble(text, type, source = null) {
  const chatMessages = document.getElementById('chat-messages');
  if (!chatMessages) return;

  const bubble = document.createElement('div');
  bubble.className = 'chat-bubble ' + type;
  bubble.textContent = text;

  if (source && type === 'ai') {
    const sourceEl = document.createElement('div');
    sourceEl.style.cssText = 'font-size:11px;color:rgba(255,255,255,0.5);margin-top:6px';
    if (type === 'user') sourceEl.style.color = 'rgba(255,255,255,0.5)';
    else sourceEl.style.color = 'var(--on-surface-variant)';
    sourceEl.textContent = '📊 Grounded in your live financial data · via ' + (source === 'gemini' ? 'Gemini AI' : 'Rules Engine');
    bubble.appendChild(sourceEl);
  }

  chatMessages.appendChild(bubble);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

// ─── Modals ───────────────────────────────────────────────────────────────────
function openModal(id) {
  const modal = document.getElementById(id);
  if (modal) modal.classList.add('open');
}
function closeModal(id) {
  const modal = document.getElementById(id);
  if (modal) modal.classList.remove('open');
}
// Close modals on overlay click
document.addEventListener('click', e => {
  if (e.target.classList.contains('modal-overlay')) closeModal(e.target.id);
});

// ─── Invite ───────────────────────────────────────────────────────────────────
async function inviteUser() {
  const data = {
    full_name: document.getElementById('invite-name').value,
    email: document.getElementById('invite-email').value,
    role: document.getElementById('invite-role').value,
  };
  const r = await api('POST', '/api/auth/invite', data);
  if (r.ok) { closeModal('invite-modal'); toast(r.data.message || 'Invitation sent', 'success'); }
  else toast(r.data.error || 'Failed', 'error');
}

// ─── Pagination ───────────────────────────────────────────────────────────────
function renderPagination(containerId, currentPage, totalPages, onPage) {
  const container = document.getElementById(containerId);
  if (!container || totalPages <= 1) { if (container) container.innerHTML = ''; return; }

  container.innerHTML = '';
  const pages = [];
  if (currentPage > 1) pages.push({ label: '‹', page: currentPage - 1 });
  for (let i = Math.max(1, currentPage - 2); i <= Math.min(totalPages, currentPage + 2); i++) pages.push({ label: String(i), page: i });
  if (currentPage < totalPages) pages.push({ label: '›', page: currentPage + 1 });

  for (const { label, page } of pages) {
    const btn = document.createElement('button');
    btn.className = 'page-btn' + (page === currentPage && !isNaN(Number(label)) ? ' active' : '');
    btn.textContent = label;
    btn.addEventListener('click', () => onPage(page));
    container.appendChild(btn);
  }
}

// ─── Auto-Login Check ─────────────────────────────────────────────────────────
async function init() {
  if (STATE.token) {
    const r = await api('GET', '/api/auth/me');
    if (r.ok) {
      STATE.user = r.data.user;
      STATE.tenant = r.data.tenant;
      enterApp();
      return;
    } else {
      STATE.token = null;
      localStorage.removeItem('msme360_token');
    }
  }
}

// ─── Keyboard shortcuts ───────────────────────────────────────────────────────
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    closeAdvisor();
    document.querySelectorAll('.modal-overlay.open').forEach(m => m.classList.remove('open'));
  }
});

// Boot
init();


// ═══════════════════════════════════════════════════════════════════════════
//  SMARTSHIELD — AI Banking Fraud Protection
//  Real-time risk analysis, scam detection, trusted contact alerts
// ═══════════════════════════════════════════════════════════════════════════

const SHIELD = {
  currentTxnId: null,
  vulnerableMode: false,
  trustContact: null,
};

// ─── Page Load ───────────────────────────────────────────────────────────────
async function loadSmartShield() {
  await Promise.all([
    loadShieldStats(),
    loadShieldHistory(),
    loadTrustedContact(),
  ]);
}

async function loadShieldStats() {
  const r = await api('GET', '/api/shield/stats');
  if (!r.ok) return;
  const d = r.data;
  setText('shield-stat-analyzed', d.total_analyzed ?? 0);
  setText('shield-stat-blocked', d.high_risk_blocked ?? 0);
  setText('shield-stat-medium', d.medium_risk_flagged ?? 0);
  setText('shield-stat-protected', fmt(d.amount_protected ?? 0));
  // update shield badge in sidebar
  const badge = document.getElementById('shield-alert-badge');
  if (badge && d.high_risk_blocked > 0) {
    badge.textContent = d.high_risk_blocked;
    badge.classList.remove('hidden');
  }
}

// ─── History Table ─────────────────────────────────────────────────────────
async function loadShieldHistory(riskFilter) {
  const url = riskFilter ? `/api/shield/history?risk_level=${riskFilter}` : '/api/shield/history';
  const r = await api('GET', url);
  const tbody = document.getElementById('shield-history-body');
  if (!tbody) return;
  if (!r.ok) { tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:20px;color:var(--on-surface-variant)">Failed to load history</td></tr>'; return; }

  const txns = r.data.transactions || [];
  if (!txns.length) {
    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:24px;color:var(--on-surface-variant)">No transactions analyzed yet. Use the analyzer above to check a payment.</td></tr>';
    return;
  }

  tbody.innerHTML = txns.map(t => {
    const riskColor = { HIGH: '#ba1a1a', MEDIUM: '#d97706', LOW: '#0d9488' }[t.risk_level] || '#45464d';
    const topFlag = (t.risk_flags || [])[0] || '';
    const topFlagLabel = topFlag.replace(/_/g, ' ');
    return `<tr>
      <td><strong>${safe(t.recipient_name)}</strong><br><span style="font-size:11px;color:var(--on-surface-variant)">${safe(t.recipient_id || '')}</span></td>
      <td><strong>${fmt(t.amount)}</strong></td>
      <td><span style="font-size:12px">${safe(t.payment_method)}</span></td>
      <td>
        <div style="display:flex;align-items:center;gap:8px">
          <div style="width:40px;height:6px;border-radius:3px;background:var(--surface-container-highest);overflow:hidden">
            <div style="width:${t.risk_score}%;height:100%;background:${riskColor};border-radius:3px;transition:width 0.5s"></div>
          </div>
          <span style="font-size:13px;font-weight:700;color:${riskColor}">${t.risk_score}</span>
        </div>
      </td>
      <td><span class="risk-badge ${t.risk_level}">${t.risk_level}</span></td>
      <td><span class="status-badge ${t.status}">${t.status}</span></td>
      <td style="font-size:11px;color:var(--on-surface-variant)">${fmtDate(t.created_at)}<br>${String(t.transaction_hour || 0).padStart(2,'0')}:00</td>
      <td style="font-size:11px;color:var(--on-surface-variant);max-width:160px;white-space:normal">${topFlagLabel ? `<span style="color:${riskColor}">${safe(topFlagLabel)}</span>` : '—'}</td>
    </tr>`;
  }).join('');
}

// ─── Transaction Analyzer ──────────────────────────────────────────────────
async function analyzeShieldTransaction() {
  const amount = parseFloat(document.getElementById('shield-amount').value);
  const recipient = document.getElementById('shield-recipient').value.trim();
  const upi = document.getElementById('shield-upi').value.trim();
  const method = document.getElementById('shield-method').value;
  const desc = document.getElementById('shield-desc').value.trim();
  const hourVal = document.getElementById('shield-hour').value;
  const hour = hourVal !== '' ? parseInt(hourVal) : null;

  if (!amount || !recipient) { toast('Please enter amount and recipient name', 'warning'); return; }

  const btn = document.getElementById('shield-analyze-btn');
  btn.disabled = true;
  btn.innerHTML = '<div class="spinner"></div> Analyzing...';

  const payload = {
    amount, recipient_name: recipient, recipient_id: upi,
    payment_method: method, description: desc,
    vulnerable_user_mode: SHIELD.vulnerableMode,
  };
  if (hour !== null) payload.transaction_hour = hour;

  const r = await api('POST', '/api/shield/analyze', payload);
  btn.disabled = false;
  btn.innerHTML = '<span class="material-symbols-outlined sm">security_scan</span> Analyze Risk';

  if (!r.ok) { toast(r.data.error || 'Analysis failed', 'error'); return; }

  const result = r.data;
  SHIELD.currentTxnId = result.transaction_id;
  showShieldResult(result, recipient, amount);
  loadShieldHistory();
  loadShieldStats();

  // High-risk: show full-screen alert modal
  if (result.risk_level === 'HIGH') {
    showHighRiskModal(result, recipient, amount);
  }
}

function showShieldResult(result, recipient, amount) {
  const panel = document.getElementById('shield-result-panel');
  if (!panel) return;
  panel.classList.remove('hidden');

  const score = result.risk_score || 0;
  const level = result.risk_level || 'LOW';
  const colors = { HIGH: '#ba1a1a', MEDIUM: '#d97706', LOW: '#0d9488' };
  const color = colors[level] || '#0d9488';
  const icons = { HIGH: 'gpp_bad', MEDIUM: 'gpp_maybe', LOW: 'gpp_good' };

  // Update header
  const iconEl = document.getElementById('shield-result-icon');
  const titleEl = document.getElementById('shield-result-title');
  if (iconEl) { iconEl.textContent = icons[level]; iconEl.style.color = color; }
  if (titleEl) titleEl.textContent = `${level} RISK — ${recipient} — ${fmt(amount)}`;

  // Animate meter
  animateShieldMeter(score, level, color);

  // Explanations
  const explContainer = document.getElementById('shield-explanations');
  if (explContainer) {
    const expls = result.explanations || [];
    if (expls.length === 0 && level === 'LOW') {
      explContainer.innerHTML = `<div class="shield-flag-item low"><span class="shield-flag-icon">✅</span><span>Transaction looks safe — no suspicious signals detected</span></div>`;
    } else {
      explContainer.innerHTML = expls.map(e =>
        `<div class="shield-flag-item ${level.toLowerCase()}">
          <span class="shield-flag-icon">${level === 'HIGH' ? '🔴' : level === 'MEDIUM' ? '🟡' : '🟢'}</span>
          <span>${safe(e)}</span>
        </div>`
      ).join('');
    }
  }

  // Scam keywords
  const kwContainer = document.getElementById('shield-scam-kws');
  const kwList = document.getElementById('shield-scam-kws-list');
  const kws = result.scam_keywords_found || [];
  if (kwContainer && kwList) {
    if (kws.length > 0) {
      kwContainer.classList.remove('hidden');
      kwList.textContent = 'Keywords: ' + kws.map(k => `"${k}"`).join(', ');
    } else {
      kwContainer.classList.add('hidden');
    }
  }

  // Action message
  const actMsg = result.action_message || '';
  const vulnMsg = SHIELD.vulnerableMode && level !== 'LOW'
    ? `<div style="margin-bottom:12px;padding:14px;border-radius:8px;background:rgba(186,26,26,0.08);border:2px solid rgba(186,26,26,0.4);font-size:17px;font-weight:700;color:#7a0000;text-align:center">${safe(actMsg)}</div>`
    : '';

  // Action buttons
  const actBtns = document.getElementById('shield-action-buttons');
  if (actBtns) {
    if (level === 'HIGH') {
      actBtns.innerHTML = `${vulnMsg}
        <button class="btn" style="flex:1;background:#ba1a1a;color:white" onclick="cancelShieldTxn()">
          <span class="material-symbols-outlined sm">cancel</span> Cancel — It's a Scam
        </button>
        <button class="btn btn-outline" style="flex:1" onclick="confirmShieldTxn()">
          <span class="material-symbols-outlined sm">check_circle</span> I've Verified — Proceed
        </button>`;
    } else if (level === 'MEDIUM') {
      actBtns.innerHTML = `${vulnMsg}
        <button class="btn btn-secondary" style="flex:1" onclick="confirmShieldTxn()">
          <span class="material-symbols-outlined sm">verified_user</span> Confirm with OTP & Proceed
        </button>
        <button class="btn btn-outline" style="flex:1" onclick="cancelShieldTxn()">
          <span class="material-symbols-outlined sm">cancel</span> Cancel Transaction
        </button>`;
    } else {
      actBtns.innerHTML = `<div style="color:#0d9488;font-size:14px;font-weight:600;padding:10px 0">
        ✅ Transaction cleared. Proceeding normally.
      </div>`;
    }
  }

  // Trusted contact notice
  const tcNotice = document.getElementById('shield-contact-alert');
  const tcName = document.getElementById('shield-contact-name');
  if (tcNotice && result.trusted_contact_alerted && result.trusted_contact_name) {
    tcNotice.classList.remove('hidden');
    if (tcName) tcName.textContent = ' ' + result.trusted_contact_name;
  } else if (tcNotice) {
    tcNotice.classList.add('hidden');
  }

  // Scroll to result
  panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function animateShieldMeter(score, level, color) {
  const arc = document.getElementById('meter-arc');
  const scoreText = document.getElementById('meter-score-text');
  const levelText = document.getElementById('meter-level-text');

  if (!arc) return;

  // SVG arc path total length ≈ 251.3 (half circle)
  const totalLen = 251.3;
  const offset = totalLen - (totalLen * score / 100);

  // Color gradient based on score
  const arcColor = score >= 70 ? '#ba1a1a' : score >= 40 ? '#d97706' : '#0d9488';
  arc.style.stroke = arcColor;

  setTimeout(() => {
    arc.style.strokeDashoffset = offset;
    if (scoreText) {
      scoreText.textContent = score;
      scoreText.style.fill = arcColor;
    }
    if (levelText) {
      levelText.textContent = level + ' RISK';
      levelText.style.fill = arcColor;
    }
  }, 100);
}

// ─── HIGH-RISK Modal ────────────────────────────────────────────────────────
function showHighRiskModal(result, recipient, amount) {
  const modal = document.getElementById('shield-highrisk-modal');
  if (!modal) return;

  const headline = document.getElementById('shield-modal-headline');
  const scoreEl = document.getElementById('shield-modal-score');
  const msgEl = document.getElementById('shield-modal-message');
  const explContainer = document.getElementById('shield-modal-explanations');
  const contactNotice = document.getElementById('shield-modal-contact-notice');
  const cancelBtn = document.getElementById('shield-modal-cancel-btn');
  const confirmBtn = document.getElementById('shield-modal-confirm-btn');

  const isVulnerable = SHIELD.vulnerableMode;

  if (headline) headline.textContent = isVulnerable
    ? '⛔ STOP! This Payment Looks Dangerous!'
    : '⛔ HIGH-RISK TRANSACTION DETECTED';

  if (scoreEl) scoreEl.textContent = `Risk Score: ${result.risk_score}/100`;

  if (msgEl) msgEl.textContent = isVulnerable
    ? `⚠️ THIS PAYMENT TO "${recipient.toUpperCase()}" FOR ${fmt(amount)} IS VERY SUSPICIOUS. Please call your family member or bank BEFORE sending any money.`
    : result.action_message || 'This payment has been held for your protection. Please verify carefully.';

  if (explContainer) {
    const expls = result.explanations || [];
    explContainer.innerHTML = expls.slice(0, 3).map(e =>
      `<div class="shield-flag-item high" style="${isVulnerable ? 'font-size:15px;padding:12px' : ''}">
        <span class="shield-flag-icon">🚨</span><span>${safe(e)}</span>
      </div>`
    ).join('');
  }

  if (contactNotice) {
    contactNotice.classList.toggle('hidden', !result.trusted_contact_alerted);
  }

  if (cancelBtn) cancelBtn.onclick = () => { cancelShieldTxn(); closeModal('shield-highrisk-modal'); };
  if (confirmBtn) confirmBtn.onclick = () => { confirmShieldTxn(); closeModal('shield-highrisk-modal'); };

  modal.classList.add('open');
}

// ─── Transaction Resolution ─────────────────────────────────────────────────
async function confirmShieldTxn() {
  if (!SHIELD.currentTxnId) return;
  const r = await api('POST', `/api/shield/confirm/${SHIELD.currentTxnId}`);
  if (r.ok) {
    toast('Transaction confirmed. System has learned from your feedback.', 'success');
    document.getElementById('shield-action-buttons').innerHTML = `<div style="color:#0d9488;font-size:14px;font-weight:600">✅ Transaction confirmed and processed.</div>`;
    loadShieldHistory();
    loadShieldStats();
  } else {
    toast('Failed to confirm transaction', 'error');
  }
}

async function cancelShieldTxn() {
  if (!SHIELD.currentTxnId) return;
  const r = await api('POST', `/api/shield/cancel/${SHIELD.currentTxnId}`);
  if (r.ok) {
    toast('Transaction cancelled. Thank you for staying safe!', 'success');
    document.getElementById('shield-action-buttons').innerHTML = `<div style="color:#ba1a1a;font-size:14px;font-weight:600">🛡️ Transaction cancelled and reported as suspicious.</div>`;
    loadShieldHistory();
    loadShieldStats();
  } else {
    toast('Failed to cancel transaction', 'error');
  }
}

// ─── Demo Quick-fill ────────────────────────────────────────────────────────
function fillShieldDemo(scenario) {
  const demos = {
    kyc: {
      recipient: 'Fake SBI KYC Team',
      upi: 'sbicare9821@paytm',
      amount: 95000,
      method: 'UPI',
      desc: 'SBI KYC Update process urgent please verify immediately',
      hour: 23,
    },
    prize: {
      recipient: 'Lucky Draw Prize Processing',
      upi: 'prize.winner2024@ybl',
      amount: 50000,
      method: 'UPI',
      desc: 'Congratulations! Claim your prize. Pay processing fee.',
      hour: 2,
    },
    electricity: {
      recipient: 'Electricity Board Emergency',
      upi: 'electricityboard.maha@ybl',
      amount: 25000,
      method: 'UPI',
      desc: 'Pay immediately electricity disconnection last warning',
      hour: 1,
    },
    vendor: {
      recipient: 'Rahul Sharma (New Vendor)',
      upi: 'rahulsharma.vendor@oksbi',
      amount: 12000,
      method: 'UPI',
      desc: 'Raw material advance payment',
      hour: 14,
    },
    legit: {
      recipient: 'Maharashtra Electricity Board',
      upi: 'mahaelectricity@bescom',
      amount: 3200,
      method: 'UPI',
      desc: 'Monthly electricity bill October 2024',
      hour: 11,
    },
  };

  const d = demos[scenario];
  if (!d) return;
  document.getElementById('shield-recipient').value = d.recipient;
  document.getElementById('shield-upi').value = d.upi;
  document.getElementById('shield-amount').value = d.amount;
  document.getElementById('shield-method').value = d.method;
  document.getElementById('shield-desc').value = d.desc;
  document.getElementById('shield-hour').value = d.hour;
  toast(`Demo scenario loaded: ${scenario.toUpperCase()}`, 'info');
}

// ─── Vulnerable User Mode ───────────────────────────────────────────────────
function toggleVulnerableMode() {
  const toggle = document.getElementById('vulnerable-mode-toggle');
  SHIELD.vulnerableMode = toggle ? toggle.checked : false;
  document.body.classList.toggle('vulnerable-mode', SHIELD.vulnerableMode);
  if (SHIELD.vulnerableMode) {
    toast('⚠️ Vulnerable User Mode ON — larger warnings enabled', 'warning');
  } else {
    toast('Vulnerable User Mode disabled', 'info');
  }
}

// ─── Trusted Contact ────────────────────────────────────────────────────────
async function loadTrustedContact() {
  const r = await api('GET', '/api/shield/trusted-contact');
  if (!r.ok || !r.data.contact) return;
  const c = r.data.contact;
  SHIELD.trustContact = c;
  const nameEl = document.getElementById('tc-name');
  const phoneEl = document.getElementById('tc-phone');
  const emailEl = document.getElementById('tc-email');
  const consentEl = document.getElementById('tc-consent');
  if (nameEl) nameEl.value = c.contact_name || '';
  if (phoneEl) phoneEl.value = c.contact_phone || '';
  if (emailEl) emailEl.value = c.contact_email || '';
  if (consentEl) consentEl.checked = c.consent_given !== false;
}

async function saveTrustedContact() {
  const name = document.getElementById('tc-name')?.value.trim();
  const phone = document.getElementById('tc-phone')?.value.trim();
  const email = document.getElementById('tc-email')?.value.trim();
  const consent = document.getElementById('tc-consent')?.checked;

  if (!name) { toast('Please enter the guardian name', 'warning'); return; }

  const r = await api('POST', '/api/shield/trusted-contact', {
    contact_name: name,
    contact_phone: phone || '',
    contact_email: email || '',
    consent_given: consent,
  });

  const status = document.getElementById('tc-status');
  if (r.ok) {
    toast('✅ Trusted guardian saved successfully', 'success');
    if (status) { status.textContent = '✅ Guardian saved — will be alerted for high-risk transactions'; status.classList.remove('hidden'); }
    SHIELD.trustContact = r.data.contact;
  } else {
    toast(r.data.error || 'Failed to save contact', 'error');
  }
}

// ─── Fraud Awareness Chatbot ────────────────────────────────────────────────
async function shieldChatSend() {
  const input = document.getElementById('shield-chat-input');
  const query = input ? input.value.trim() : '';
  if (!query) return;

  appendShieldChat(query, 'user');
  if (input) input.value = '';

  // Typing indicator
  const typingId = 'shield-typing-' + Date.now();
  appendShieldChat('...', 'system', typingId);

  const r = await api('POST', '/api/shield/chatbot', { query });
  const typingEl = document.getElementById(typingId);
  if (typingEl) typingEl.remove();

  if (r.ok) {
    const cls = r.data.is_scam_detected ? 'scam-warning' : 'system';
    appendShieldChat(r.data.response, cls);
  } else {
    appendShieldChat('Sorry, I couldn\'t process your question. Please try again.', 'system');
  }
}

function shieldChatQuick(question) {
  const input = document.getElementById('shield-chat-input');
  if (input) input.value = question;
  shieldChatSend();
}

function appendShieldChat(text, cls, id) {
  const container = document.getElementById('shield-chat-messages');
  if (!container) return;
  const bubble = document.createElement('div');
  bubble.className = 'chat-bubble ' + cls;
  if (id) bubble.id = id;
  bubble.textContent = text;
  container.appendChild(bubble);
  container.scrollTop = container.scrollHeight;
}

// ═══════════════════════════════════════════════════════════════════════════
//  OWNER / ROLE SWITCHER — Switch between tenants/users without logout
// ═══════════════════════════════════════════════════════════════════════════

async function switchOwner(email, password, roleLabel) {
  // Show spinner briefly
  const btns = document.querySelectorAll('.owner-btn');
  btns.forEach(b => b.disabled = true);

  const r = await api('POST', '/api/auth/login', { email, password });

  btns.forEach(b => b.disabled = false);

  if (!r.ok) {
    toast('Switch failed: ' + (r.data.error || 'Login error'), 'error');
    return;
  }

  // Update state
  STATE.token = r.data.access_token;
  localStorage.setItem('msme360_token', STATE.token);
  STATE.user = r.data.user;
  STATE.tenant = r.data.tenant;

  // Update UI
  updateUserUI();

  // Highlight the active owner button
  document.querySelectorAll('.owner-btn').forEach(b => {
    b.classList.toggle('active',
      b.getAttribute('onclick') && b.getAttribute('onclick').includes(email));
  });

  // Reload current page data
  showPage(STATE.currentPage);

  const name = r.data.user?.full_name || email;
  const tenant = r.data.tenant?.name || '';
  toast(`Switched to ${name} (${roleLabel}) — ${tenant}`, 'success');
}

// Highlight the current user in the switcher on load
function highlightCurrentOwner() {
  const email = STATE.user?.email || '';
  document.querySelectorAll('.owner-btn').forEach(b => {
    const onclick = b.getAttribute('onclick') || '';
    b.classList.toggle('active', onclick.includes(email));
  });
}

// ═══════════════════════════════════════════════════════════════════════════
//  THEME CONTROLLER — Light & Dark Mode
// ═══════════════════════════════════════════════════════════════════════════

function initTheme() {
  const saved = localStorage.getItem('msme360_theme') || 'light';
  applyTheme(saved);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'light';
  const next = current === 'dark' ? 'light' : 'dark';
  applyTheme(next);
  toast(`Switched to ${next === 'dark' ? 'Dark' : 'Light'} Mode`, 'info');
}

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('msme360_theme', theme);

  const iconName = theme === 'dark' ? 'light_mode' : 'dark_mode';
  const iconTitle = theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode';

  const headerIcon = document.getElementById('theme-toggle-icon');
  if (headerIcon) headerIcon.textContent = iconName;

  const authIcon = document.getElementById('auth-theme-icon');
  if (authIcon) authIcon.textContent = iconName;

  const headerBtn = document.getElementById('theme-toggle-btn');
  if (headerBtn) headerBtn.title = iconTitle;
}

// Auto-run on script parse
initTheme();
