/* ═══════════════════════════════════════════════════════════
   TRIPWISE v2 — Enhanced Frontend JS
   ═══════════════════════════════════════════════════════════ */

/* ─── DOM References ─── */
const form           = document.getElementById('planner-form');
const statusBox      = document.getElementById('status');
const resultsSection = document.getElementById('results');
const resultsInner   = document.getElementById('results-inner');
const submitBtn      = document.getElementById('submit-btn');
const btnText        = submitBtn.querySelector('.btn-text');
const btnArrow       = submitBtn.querySelector('.btn-arrow-icon');
const btnLoader      = submitBtn.querySelector('.btn-loader');

/* ─── Navbar scroll effect ─── */
const navbar = document.getElementById('navbar');
window.addEventListener('scroll', () => {
  navbar.classList.toggle('scrolled', window.scrollY > 20);
}, { passive: true });

/* ─── Mobile hamburger ─── */
const hamburger  = document.getElementById('hamburger');
const mobileMenu = document.getElementById('mobile-menu');
hamburger.addEventListener('click', () => {
  hamburger.classList.toggle('open');
  mobileMenu.classList.toggle('open');
});
mobileMenu.querySelectorAll('a').forEach(a => a.addEventListener('click', () => {
  hamburger.classList.remove('open');
  mobileMenu.classList.remove('open');
}));

/* ─── Date constraints ─── */
const today      = new Date().toISOString().slice(0, 10);
const startInput = document.getElementById('start_date');
const endInput   = document.getElementById('end_date');
startInput.min = today;
endInput.min   = today;
startInput.addEventListener('change', () => {
  endInput.min = startInput.value || today;
  if (endInput.value && endInput.value < startInput.value) endInput.value = startInput.value;
});

/* ─── Traveler counter ─── */
const travelersInput = document.getElementById('travelers');
document.getElementById('inc-travelers').addEventListener('click', () => {
  const v = parseInt(travelersInput.value, 10);
  if (v < 30) travelersInput.value = v + 1;
});
document.getElementById('dec-travelers').addEventListener('click', () => {
  const v = parseInt(travelersInput.value, 10);
  if (v > 1) travelersInput.value = v - 1;
});

/* ─── Currency symbol update ─── */
const currencySymbols = { INR: '₹', USD: '$', EUR: '€', GBP: '£' };
const currencySymbolEl = document.getElementById('currency-symbol');
document.getElementById('currency').addEventListener('change', function () {
  currencySymbolEl.textContent = currencySymbols[this.value] || this.value;
});

/* ─── Interest chip toggle ─── */
document.querySelectorAll('.interest-chip').forEach(chip => {
  chip.addEventListener('click', () => {
    const cb = chip.querySelector('input[type="checkbox"]');
    cb.checked = !cb.checked;
    chip.classList.toggle('checked', cb.checked);
  });
});

/* ─── Scroll-reveal observer ─── */
const revealObserver = new IntersectionObserver((entries) => {
  entries.forEach((entry, i) => {
    if (entry.isIntersecting) {
      setTimeout(() => entry.target.classList.add('revealed'), i * 120);
      revealObserver.unobserve(entry.target);
    }
  });
}, { threshold: 0.15 });
document.querySelectorAll('[data-reveal]').forEach(el => revealObserver.observe(el));

/* ─── Smooth nav links ─── */
document.querySelectorAll('a[href^="#"]').forEach(a => {
  a.addEventListener('click', e => {
    const target = document.querySelector(a.getAttribute('href'));
    if (target) {
      e.preventDefault();
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });
});


/* ═══════════════════════════════════════════════════════════
   UTILITY HELPERS
   ═══════════════════════════════════════════════════════════ */
function money(amount, currency) {
  if (amount === undefined || amount === null) return '—';
  const sym = currencySymbols[currency] || currency + ' ';
  return sym + Number(amount).toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function esc(val) {
  return String(val).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}

function showStatus(msg, type = 'error') {
  statusBox.textContent = msg;
  statusBox.className = 'status-box ' + type;
}
function clearStatus() {
  statusBox.textContent = '';
  statusBox.className = 'status-box';
}

function setLoading(on) {
  submitBtn.disabled = on;
  btnText.hidden     = on;
  btnArrow.hidden    = on;
  btnLoader.hidden   = !on;
}

function animateBars() {
  setTimeout(() => {
    document.querySelectorAll('.budget-bar-fill').forEach(bar => {
      bar.style.width = (bar.dataset.pct || 0) + '%';
    });
  }, 350);
}

function bindDayToggles() {
  document.querySelectorAll('.day-header').forEach(header => {
    header.addEventListener('click', () => {
      header.closest('.day-card').classList.toggle('collapsed');
    });
  });
}


/* ═══════════════════════════════════════════════════════════
   BUDGET ASSESSMENT BANNER
   ═══════════════════════════════════════════════════════════ */
function renderAssessment(assessment, c) {
  const colorMap = { green: '#10b981', yellow: '#f59e0b', red: '#ef4444' };
  const bgMap    = { green: '#f0fdf4', yellow: '#fffbeb', red: '#fef2f2' };
  const borderMap= { green: '#bbf7d0', yellow: '#fde68a', red: '#fecaca' };

  const color  = colorMap[assessment.status_color]  || '#6b7280';
  const bg     = bgMap[assessment.status_color]     || '#f9fafb';
  const border = borderMap[assessment.status_color] || '#e5e7eb';

  const diffLabel = assessment.difference_display >= 0
    ? `${money(assessment.difference_display, c)} remaining`
    : `${money(Math.abs(assessment.difference_display), c)} shortfall`;

  let suggestionsHTML = '';
  if (assessment.suggestions && assessment.suggestions.length) {
    suggestionsHTML = `
      <div class="assessment-suggestions">
        <div class="suggestions-title">💡 Suggestions to reduce cost:</div>
        <ul class="suggestions-list">
          ${assessment.suggestions.map(s => `<li>${esc(s)}</li>`).join('')}
        </ul>
      </div>`;
  }

  return `
    <div class="assessment-banner" style="background:${bg};border-color:${border}">
      <div class="assessment-header">
        <span class="assessment-label" style="color:${color}">${esc(assessment.status_label)}</span>
        <span class="assessment-diff" style="color:${color}">${diffLabel}</span>
      </div>
      <div class="assessment-meters">
        <div class="assessment-meter-track">
          <div class="assessment-meter-fill" data-pct="${Math.min(assessment.pct_used, 100)}"
               style="background:${color}; width:0%"></div>
        </div>
        <span class="assessment-pct">${assessment.pct_used}% of budget consumed</span>
      </div>
      ${suggestionsHTML}
      <div class="assessment-disclaimer">ℹ️ ${esc(assessment.disclaimer)}</div>
    </div>`;
}


/* ═══════════════════════════════════════════════════════════
   ROUTE CONNECTOR
   ═══════════════════════════════════════════════════════════ */
function renderRouteConnector(slot) {
  const r = slot.travel_to_next;
  if (!r) return '';
  return `
    <div class="route-connector">
      <span class="route-icon">🚗</span>
      <span class="route-info">${r.distance_km} km · ~${r.duration_min} min drive</span>
    </div>`;
}


/* ═══════════════════════════════════════════════════════════
   BUDGET BREAKDOWN CARD
   ═══════════════════════════════════════════════════════════ */
function renderBudgetBreakdown(costs, c) {
  const estimated = costs.estimated_total || 1;
  const lines = [
    { label: '🏨 Accommodation',   key: 'accommodation',      color: '#8B5CF6', basis: costs.accommodation_basis },
    { label: '🍽️  Food',           key: 'food',               color: '#38BDF8', basis: costs.food_basis },
    { label: '🚇 Local Transport', key: 'local_transport',    color: '#2563EB', basis: costs.local_transport_basis },
    { label: '✈️  Intercity',       key: 'intercity_transport',color: '#0ea5e9', basis: costs.intercity_transport_basis },
    { label: '🎫 Attractions',     key: 'attractions',        color: '#10b981', basis: costs.attractions_basis },
    { label: '🛡️  Contingency',     key: 'contingency',        color: '#f59e0b', basis: costs.contingency_basis },
  ];

  const rowsHTML = lines.map(l => {
    const amount = costs[l.key] || 0;
    const pct    = Math.round((amount / estimated) * 100);
    return `
      <div class="budget-bar-row">
        <div class="budget-bar-label">${l.label}</div>
        <div class="budget-bar-col">
          <div class="budget-bar-track">
            <div class="budget-bar-fill" data-pct="${pct}"
                 style="background:linear-gradient(90deg,${l.color},${l.color}aa);width:0%"></div>
          </div>
          ${l.basis ? `<div class="budget-basis">${esc(l.basis)}</div>` : ''}
        </div>
        <div class="budget-bar-amount">${money(amount, c)}</div>
      </div>`;
  }).join('');

  return `
    <div class="budget-card">
      <div class="budget-title">💰 Estimated Budget Breakdown</div>
      <div class="budget-bars">${rowsHTML}</div>
      <div class="budget-total-row">
        <span class="budget-total-label">Estimated Total</span>
        <span class="budget-total-value">${money(costs.estimated_total, c)}</span>
      </div>
    </div>`;
}


/* ═══════════════════════════════════════════════════════════
   DAY CARDS
   ═══════════════════════════════════════════════════════════ */
function renderDays(days, destination, c) {
  const periodMeta = {
    morning:   { label: 'Morning',   badge: 'morning-badge',   icon: '🌅' },
    afternoon: { label: 'Afternoon', badge: 'afternoon-badge', icon: '☀️' },
    evening:   { label: 'Evening',   badge: 'evening-badge',   icon: '🌆' },
  };

  return days.map((day, idx) => {
    const slots = ['morning', 'afternoon', 'evening'].map((key, si) => {
      const s = day[key];
      const p = periodMeta[key];
      const q = encodeURIComponent(s.name + ' ' + destination);

      // Build Maps link — use lat/lon if available, otherwise search query
      const mapsHref = (s.lat && s.lon)
        ? `https://www.google.com/maps/search/?api=1&query=${s.lat},${s.lon}`
        : `https://www.google.com/maps/search/?api=1&query=${q}`;

      // Route connector after morning and afternoon
      const routeHTML = (si < 2) ? renderRouteConnector(s) : '';

      return `
        <div class="activity-slot">
          <div class="slot-time-col">
            <span class="slot-period-badge ${p.badge}">${p.icon} ${p.label}</span>
            <span class="slot-time">${esc(s.time)}</span>
          </div>
          <div class="slot-info">
            <div class="slot-name">${esc(s.name)}</div>
            <div class="slot-desc">${esc(s.description)}</div>
            <a class="slot-maps-link" href="${mapsHref}" target="_blank" rel="noopener noreferrer">
              📍 View on Google Maps ↗
            </a>
          </div>
          <div class="slot-cost">${money(s.cost, c)}</div>
        </div>
        ${routeHTML}`;
    }).join('');

    return `
      <div class="day-card" style="animation-delay:${idx * 80}ms">
        <div class="day-header">
          <div class="day-number">${day.day}</div>
          <div class="day-meta">
            <div class="day-name">Day ${day.day}</div>
            <div class="day-date">${esc(day.date)}</div>
          </div>
          <div class="day-toggle">▾</div>
        </div>
        <div class="day-body">${slots}</div>
      </div>`;
  }).join('');
}


/* ═══════════════════════════════════════════════════════════
   MAIN RENDER FUNCTION
   ═══════════════════════════════════════════════════════════ */
function render(data) {
  const c        = data.currency;
  const costs    = data.costs;
  const assess   = data.assessment;

  /* ── Source badge ── */
  const sourceBadge = data.live_data_used
    ? `<span class="source-badge source-live">✅ Curated Data</span>`
    : `<span class="source-badge source-wiki">🌐 Wikipedia + Generic</span>`;

  /* ── Currency note ── */
  const currencyBanner = (c !== 'INR' && data.currency_note)
    ? `<div class="currency-note">💱 Exchange rate: ${esc(data.currency_note)}. Figures shown in ${c}.</div>`
    : '';

  /* ── Min budget warning ── */
  const minBudgetWarning = !data.budget_adequate
    ? `<div class="min-budget-warning">
         ⚠️ Your budget of ${money(data.budget, c)} may be below the minimum recommended
         ${money(data.min_budget_recommended, c)} for this trip. The plan below is still generated
         but actual costs are likely to exceed your budget significantly.
       </div>`
    : '';

  /* ── Hero metrics ── */
  const remaining        = data.budget - costs.estimated_total;
  const remainingClass   = remaining >= 0 ? 'green' : 'red';

  /* ── Build full HTML ── */
  resultsInner.innerHTML = `
    ${currencyBanner}
    ${minBudgetWarning}

    <!-- Trip hero -->
    <div class="result-hero-card">
      <div class="result-eyebrow">YOUR PERSONALISED ITINERARY ${sourceBadge}</div>
      <div class="result-destination">${esc(data.destination)}</div>
      <div class="result-dates">
        📅 ${esc(data.start_date)} → ${esc(data.end_date)} &nbsp;·&nbsp;
        👥 ${data.travelers} traveller${data.travelers > 1 ? 's' : ''} &nbsp;·&nbsp;
        📆 ${data.num_days} day${data.num_days > 1 ? 's' : ''}, ${data.num_nights} night${data.num_nights > 1 ? 's' : ''}
      </div>
      <div class="metrics-grid">
        <div class="metric-card">
          <div class="metric-label">ESTIMATED TOTAL</div>
          <div class="metric-value">${money(costs.estimated_total, c)}</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">PER PERSON</div>
          <div class="metric-value">${money(costs.per_person, c)}</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">YOUR BUDGET</div>
          <div class="metric-value">${money(data.budget, c)}</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">REMAINING</div>
          <div class="metric-value ${remainingClass}">${money(remaining, c)}</div>
        </div>
      </div>
    </div>

    <!-- Budget assessment -->
    ${renderAssessment(assess, c)}

    <!-- Budget breakdown with basis notes -->
    ${renderBudgetBreakdown(costs, c)}

    <!-- Day-by-day itinerary -->
    <div class="days-header">🗓️ Day-by-Day Itinerary</div>
    <div class="days-list">${renderDays(data.days, data.destination, c)}</div>

    <!-- Notes -->
    <div class="notes-card">
      <div class="notes-title">📌 Before You Go</div>
      <div class="notes-list">
        ${data.notes.map(n => `<div class="note-item"><span class="note-icon">ℹ</span><span>${esc(n)}</span></div>`).join('')}
      </div>
      <button class="print-btn" id="print-btn" type="button">🖨️ Print / Save as PDF</button>
    </div>
  `;

  /* Animate elements */
  animateBars();
  setTimeout(() => {
    document.querySelectorAll('.assessment-meter-fill').forEach(el => {
      el.style.width = (el.dataset.pct || 0) + '%';
    });
  }, 400);

  bindDayToggles();
  document.getElementById('print-btn').addEventListener('click', () => window.print());

  /* Scroll to results */
  resultsSection.hidden = false;
  setTimeout(() => resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);
}


/* ═══════════════════════════════════════════════════════════
   FORM SUBMIT
   ═══════════════════════════════════════════════════════════ */
form.addEventListener('submit', async (e) => {
  e.preventDefault();
  clearStatus();
  resultsSection.hidden = true;
  setLoading(true);

  const payload = {
    destination: document.getElementById('destination').value.trim(),
    start_date:  startInput.value,
    end_date:    endInput.value,
    budget:      document.getElementById('budget').value,
    currency:    document.getElementById('currency').value,
    travelers:   travelersInput.value,
    interests:   [...document.querySelectorAll('input[name="interest"]:checked')].map(x => x.value),
  };

  try {
    const res  = await fetch('/api/plan', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Could not create your itinerary.');
    render(data);
  } catch (err) {
    showStatus('⚠️  ' + (err.message || 'Unable to connect. Please make sure the server is running.'), 'error');
  } finally {
    setLoading(false);
  }
});
