/* ═══════════════════════════════════════════════════════════
   TRIPWISE 2.0 — Production Travel Experience Controller
   ═══════════════════════════════════════════════════════════ */

// ─── Global State ───
let currentTripData = null;
let currentChatHistory = [];
let leafletMapInstance = null;

// ─── DOM References ───
const form = document.getElementById('planner-form');
const statusBox = document.getElementById('status');
const resultsSection = document.getElementById('results');
const resultsInner = document.getElementById('results-inner');
const submitBtn = document.getElementById('submit-btn');
const btnText = submitBtn.querySelector('.btn-text');
const btnArrow = submitBtn.querySelector('.btn-arrow-icon');
const btnLoader = submitBtn.querySelector('.btn-loader');

// Geolocation
const startLocInput = document.getElementById('start_location');
const detectLocBtn = document.getElementById('btn-detect-location');
const geoHint = document.getElementById('geo-status-hint');

// Dates & Travelers
const todayIso = new Date().toISOString().slice(0, 10);
const startInput = document.getElementById('start_date');
const endInput = document.getElementById('end_date');
const travelersInput = document.getElementById('travelers');

// Currency & Budget
const currencySelect = document.getElementById('currency');
const currencySymbolEl = document.getElementById('currency-symbol');
const currencySymbols = { INR: '₹', USD: '$', EUR: '€', GBP: '£' };

// Navbar & Mobile
const navbar = document.getElementById('navbar');
const hamburger = document.getElementById('hamburger');
const mobileMenu = document.getElementById('mobile-menu');

// Chatbot
const chatbotDrawer = document.getElementById('chatbot-drawer');
const floatingChatTrigger = document.getElementById('floating-chat-trigger');
const closeChatBtn = document.getElementById('close-chat-btn');
const openChatNavBtn = document.getElementById('open-chat-nav-btn');
const mobileChatBtn = document.getElementById('mobile-chat-btn');
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const chatMessages = document.getElementById('chat-messages');
const chatProviderBadge = document.getElementById('chat-provider-badge');

// Modals
const savedTripsModal = document.getElementById('saved-trips-modal');
const closeSavedModal = document.getElementById('close-saved-modal');
const savedTripsList = document.getElementById('saved-trips-list');
const navSavedTripsBtn = document.getElementById('nav-saved-trips-btn');
const mobileSavedTripsBtn = document.getElementById('mobile-saved-trips-btn');
const footerSavedLink = document.getElementById('footer-saved-link');

const shareModal = document.getElementById('share-modal');
const closeShareModal = document.getElementById('close-share-modal');
const shareUrlInput = document.getElementById('share-url-input');
const btnCopyShareUrl = document.getElementById('btn-copy-share-url');
const copyStatus = document.getElementById('copy-status');


// ─── Initialization ───
document.addEventListener('DOMContentLoaded', () => {
  initDateConstraints();
  initNavbar();
  initTravelerCounter();
  initInterestChips();
  initQuickDestinationPills();
  initGeolocationDetection();
  initChatbot();
  initModals();
  initRevealObserver();

  // If page was loaded via shared trip route /trip/<id>
  if (window.INITIAL_SHARED_TRIP) {
    currentTripData = window.INITIAL_SHARED_TRIP;
    renderCompletePlan(currentTripData);
    resultsSection.scrollIntoView({ behavior: 'smooth' });
  }
});


// ─── Scroll-Reveal Observer ───
function initRevealObserver() {
  const targets = document.querySelectorAll('[data-reveal]');
  if (!targets.length) return;

  // Immediately reveal if user prefers reduced motion
  const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (prefersReduced) {
    targets.forEach(el => el.classList.add('revealed'));
    return;
  }

  // Fallback: if IntersectionObserver unavailable, reveal all immediately
  if (!('IntersectionObserver' in window)) {
    targets.forEach(el => el.classList.add('revealed'));
    return;
  }

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry, i) => {
      if (entry.isIntersecting) {
        setTimeout(() => entry.target.classList.add('revealed'), i * 80);
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });

  targets.forEach(el => observer.observe(el));

  // Safety net: reveal any still-hidden elements after 3s (e.g. if observer fires too late)
  setTimeout(() => {
    targets.forEach(el => {
      if (!el.classList.contains('revealed')) {
        el.classList.add('revealed');
      }
    });
  }, 3000);
}


// ─── Navbar & Scrolling ───
function initNavbar() {
  window.addEventListener('scroll', () => {
    navbar.classList.toggle('scrolled', window.scrollY > 20);
  }, { passive: true });

  hamburger.addEventListener('click', () => {
    hamburger.classList.toggle('open');
    mobileMenu.classList.toggle('open');
  });

  mobileMenu.querySelectorAll('a').forEach(a => a.addEventListener('click', () => {
    hamburger.classList.remove('open');
    mobileMenu.classList.remove('open');
  }));
}


// ─── Date Constraints (Departure & Return) ───
function initDateConstraints() {
  startInput.min = todayIso;
  endInput.min = todayIso;

  // Set default dates: 14 days from now for a 4-day trip
  const defaultDepart = new Date();
  defaultDepart.setDate(defaultDepart.getDate() + 14);
  const defaultReturn = new Date(defaultDepart);
  defaultReturn.setDate(defaultReturn.getDate() + 3);

  startInput.value = defaultDepart.toISOString().slice(0, 10);
  endInput.value = defaultReturn.toISOString().slice(0, 10);

  startInput.addEventListener('change', () => {
    endInput.min = startInput.value || todayIso;
    if (endInput.value && endInput.value < startInput.value) {
      endInput.value = startInput.value;
    }
  });
}


// ─── Traveler Counter ───
function initTravelerCounter() {
  document.getElementById('inc-travelers').addEventListener('click', () => {
    const v = parseInt(travelersInput.value, 10) || 1;
    if (v < 30) travelersInput.value = v + 1;
  });
  document.getElementById('dec-travelers').addEventListener('click', () => {
    const v = parseInt(travelersInput.value, 10) || 1;
    if (v > 1) travelersInput.value = v - 1;
  });

  currencySelect.addEventListener('change', function () {
    currencySymbolEl.textContent = currencySymbols[this.value] || this.value;
  });
}


// ─── Interest Chips Multi-Select ───
function initInterestChips() {
  document.querySelectorAll('.interest-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const cb = chip.querySelector('input[type="checkbox"]');
      cb.checked = !cb.checked;
      chip.classList.toggle('checked', cb.checked);
    });
  });
}


// ─── Quick Destination Pills ───
function initQuickDestinationPills() {
  document.querySelectorAll('.quick-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      document.getElementById('destination').value = pill.dataset.dest;
      pill.style.transform = 'scale(0.95)';
      setTimeout(() => pill.style.transform = '', 150);
    });
  });
}


// ─── Phase 7: Geolocation Detection ───
function initGeolocationDetection() {
  detectLocBtn.addEventListener('click', () => {
    if (!navigator.geolocation) {
      geoHint.textContent = 'Geolocation is not supported by your browser.';
      geoHint.style.color = '#ef4444';
      return;
    }

    geoHint.textContent = 'Detecting current GPS location...';
    geoHint.style.color = '#2563eb';
    detectLocBtn.disabled = true;

    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const lat = pos.coords.latitude;
        const lon = pos.coords.longitude;
        try {
          const resp = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}`);
          if (resp.ok) {
            const data = await resp.json();
            const city = data.address.city || data.address.town || data.address.state_district || data.address.state || 'Current Location';
            startLocInput.value = city;
            geoHint.textContent = `📍 Detected: ${city}`;
            geoHint.style.color = '#10b981';
          } else {
            startLocInput.value = `${lat.toFixed(2)}, ${lon.toFixed(2)}`;
            geoHint.textContent = '📍 Coordinates detected.';
          }
        } catch {
          startLocInput.value = 'Visakhapatnam';
          geoHint.textContent = 'Defaulted to Visakhapatnam.';
        } finally {
          detectLocBtn.disabled = false;
        }
      },
      (err) => {
        detectLocBtn.disabled = false;
        geoHint.textContent = 'Location permission denied. Enter location manually.';
        geoHint.style.color = '#64748b';
      },
      { timeout: 8000 }
    );
  });
}


// ─── Form Submission ───
form.addEventListener('submit', async (e) => {
  e.preventDefault();
  clearStatus();
  resultsSection.hidden = true;
  setLoading(true);

  const payload = {
    start_location: startLocInput.value.trim() || 'Visakhapatnam',
    destination: document.getElementById('destination').value.trim(),
    start_date: startInput.value,
    end_date: endInput.value,
    budget: document.getElementById('budget').value,
    budget_type: document.getElementById('budget_type').value,
    currency: currencySelect.value,
    travelers: travelersInput.value,
    travel_preference: document.getElementById('travel_preference').value,
    accommodation_preference: document.getElementById('accommodation_preference').value,
    food_preference: document.getElementById('food_preference').value,
    interests: [...document.querySelectorAll('input[name="interest"]:checked')].map(x => x.value)
  };

  try {
    const res = await fetch('/api/plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Could not generate travel itinerary.');

    currentTripData = data;
    renderCompletePlan(data);
    resultsSection.hidden = false;
    setTimeout(() => {
      resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 150);

  } catch (err) {
    showStatus('⚠️ ' + (err.message || 'Unable to connect to server. Please check your network.'), 'error');
  } finally {
    setLoading(false);
  }
});


// ─── Status & Loading Helpers ───
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
  btnText.hidden = on;
  btnArrow.hidden = on;
  btnLoader.hidden = !on;
}
function money(amount, currency) {
  if (amount === undefined || amount === null) return '—';
  const sym = currencySymbols[currency] || currency + ' ';
  return sym + Number(amount).toLocaleString(undefined, { maximumFractionDigits: 0 });
}
function esc(val) {
  return String(val ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}


// ═══════════════════════════════════════════════════════════
// RENDER COMPLETE MASTER PLAN
// ═══════════════════════════════════════════════════════════
function renderCompletePlan(data) {
  const c = data.currency;
  const ba = data.budget_analysis;
  const tc = data.transportation_comparison;
  const itin = data.itinerary;
  const weather = data.weather;
  const intercity = data.intercity_travel;

  resultsInner.innerHTML = `
    <!-- Top Action Bar -->
    <div class="results-top-bar">
      <div class="trip-destination-tag">
        <span class="trip-dest-icon">🛫</span>
        <span class="trip-dest-title">${esc(data.start_location)} → ${esc(data.destination)}</span>
      </div>
      <div class="results-action-buttons">
        <button class="btn-action-pill btn-save-action" id="btn-save-trip">
          💾 Save Trip
        </button>
        <button class="btn-action-pill" id="btn-share-trip">
          🔗 Share Link
        </button>
        <button class="btn-action-pill" id="btn-copy-summary">
          📋 Copy Summary
        </button>
        <button class="btn-action-pill" id="btn-print-pdf">
          📄 Export PDF
        </button>
      </div>
    </div>

    <!-- Navigation Sub-Tabs -->
    <div class="plan-tabs-bar">
      <button class="plan-tab-btn active" data-tab="tab-overview">📊 Overview & Budget</button>
      <button class="plan-tab-btn" data-tab="tab-itinerary">🗓️ Day-by-Day Itinerary</button>
      <button class="plan-tab-btn" data-tab="tab-transport">🚆 Transport Comparison</button>
      <button class="plan-tab-btn" data-tab="tab-map">🗺️ Interactive Map</button>
      <button class="plan-tab-btn" data-tab="tab-weather">🌤️ Weather & Packing</button>
    </div>

    <!-- TAB 1: Overview & Budget Analysis -->
    <div class="plan-tab-content active" id="tab-overview">
      ${renderTripHeroCard(data, intercity, c)}
      ${renderBudgetAssessmentBanner(ba, c)}
      ${renderBudgetBreakdownGrid(ba, c)}
    </div>

    <!-- TAB 2: Day-by-Day Itinerary -->
    <div class="plan-tab-content" id="tab-itinerary">
      <div class="itinerary-header-meta">
        <h3>🗓️ Detailed Daily Schedule (${itin.length} Days)</h3>
        <p>Attractions grouped geographically to optimize driving routes, meal breaks, and visit times.</p>
      </div>
      <div class="days-list-wrapper">
        ${renderDaysItinerary(itin, data.destination, c)}
      </div>
    </div>

    <!-- TAB 3: 5-Way Transport Comparison -->
    <div class="plan-tab-content" id="tab-transport">
      ${renderTransportComparison(tc, intercity, c)}
    </div>

    <!-- TAB 4: Interactive Route Map -->
    <div class="plan-tab-content" id="tab-map">
      <div class="map-card-wrapper">
        <div class="map-header">
          <div>
            <h3>🗺️ Interactive Destination & Route Map</h3>
            <p>Pins show recommended attractions with driving routes between stops.</p>
          </div>
          <a class="btn-maps-link" href="${esc(intercity.directions_url)}" target="_blank" rel="noopener noreferrer">
            📍 Open in Google Maps ↗
          </a>
        </div>
        <div id="interactive-trip-map" class="trip-leaflet-map"></div>
      </div>
    </div>

    <!-- TAB 5: Weather & Packing Advice -->
    <div class="plan-tab-content" id="tab-weather">
      ${renderWeatherSection(weather, data.destination)}
    </div>
  `;

  // Bind Actions & Event Handlers
  bindTabSwitching();
  bindDayCardToggles();
  bindActionButtons(data);
  initLeafletMap(data);
}


// ─── Tab Switching ───
function bindTabSwitching() {
  document.querySelectorAll('.plan-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.plan-tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.plan-tab-content').forEach(c => c.classList.remove('active'));

      btn.classList.add('active');
      const targetId = btn.dataset.tab;
      const targetEl = document.getElementById(targetId);
      if (targetEl) targetEl.classList.add('active');

      // Refresh map sizing if switching to map tab
      if (targetId === 'tab-map' && leafletMapInstance) {
        setTimeout(() => leafletMapInstance.invalidateSize(), 200);
      }
    });
  });
}


// ─── Hero Summary Card ───
function renderTripHeroCard(data, intercity, c) {
  const ba = data.budget_analysis;
  const isSurplus = ba.budget_difference >= 0;

  return `
    <div class="result-hero-card">
      <div class="result-eyebrow">
        <span>VERIFIED TRAVEL PLAN</span>
        <span class="source-badge">${esc(data.attraction_source)}</span>
      </div>
      <div class="result-destination">${esc(data.destination)}</div>
      <div class="result-dates">
        📅 ${esc(data.start_date)} → ${esc(data.end_date)} &nbsp;·&nbsp;
        👥 ${data.travelers} traveller${data.travelers > 1 ? 's' : ''} &nbsp;·&nbsp;
        📆 ${data.num_days} day(s), ${data.num_nights} night(s) &nbsp;·&nbsp;
        🚗 ~${intercity.distance_km} km from ${esc(data.start_location)} (${intercity.estimated_duration})
      </div>

      <div class="metrics-grid">
        <div class="metric-card">
          <div class="metric-label">TOTAL ESTIMATED COST</div>
          <div class="metric-value">${money(ba.total_estimated_trip_cost, c)}</div>
          <div class="metric-sub">${money(ba.total_estimated_per_person, c)} / person</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">AVAILABLE BUDGET</div>
          <div class="metric-value">${money(ba.available_budget_total, c)}</div>
          <div class="metric-sub">${money(ba.available_budget_per_person, c)} / person (${data.budget_type === 'per_person' ? 'Per Person Input' : 'Group Input'})</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">${isSurplus ? 'BUDGET REMAINING' : 'BUDGET SHORTFALL'}</div>
          <div class="metric-value ${isSurplus ? 'green' : 'red'}">
            ${money(Math.abs(ba.budget_difference), c)}
          </div>
          <div class="metric-sub">${isSurplus ? 'Surplus' : 'Deficit'} (${ba.percentage_consumed}% consumed)</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">TRAVEL PREFERENCES</div>
          <div class="metric-value" style="font-size:1.05rem;">${esc(data.accommodation_preference.replace('_', ' ').toUpperCase())}</div>
          <div class="metric-sub">${esc(data.food_preference.replace('_', ' ').toUpperCase())} · ${esc(data.travel_preference.toUpperCase())}</div>
        </div>
      </div>
    </div>
  `;
}


// ─── Budget Assessment Banner (Phase 2 & Feature Two) ───
function renderBudgetAssessmentBanner(ba, c) {
  const colorMap = { green: '#10b981', yellow: '#f59e0b', red: '#ef4444' };
  const bgMap = { green: '#f0fdf4', yellow: '#fffbeb', red: '#fef2f2' };
  const borderMap = { green: '#bbf7d0', yellow: '#fde68a', red: '#fecaca' };

  const color = colorMap[ba.status_color] || '#64748b';
  const bg = bgMap[ba.status_color] || '#f8fafc';
  const border = borderMap[ba.status_color] || '#e2e8f0';

  const suggestionsHTML = (ba.suggestions && ba.suggestions.length) ? `
    <div class="assessment-suggestions">
      <div class="suggestions-title">💡 Actionable Budget Advice & Savings:</div>
      <ul class="suggestions-list">
        ${ba.suggestions.map(s => `<li>${esc(s)}</li>`).join('')}
      </ul>
    </div>
  ` : '';

  return `
    <div class="assessment-banner" style="background:${bg}; border-color:${border};">
      <div class="assessment-header">
        <div class="assessment-title-wrap">
          <span class="status-indicator-icon">${ba.status_icon}</span>
          <span class="assessment-label" style="color:${color}">${esc(ba.status_label)}</span>
        </div>
        <div class="assessment-diff" style="color:${color}">
          ${ba.budget_difference >= 0 ? '+' : '-'}${money(Math.abs(ba.budget_difference), c)} (${ba.percentage_consumed}% consumed)
        </div>
      </div>

      <div class="assessment-message-text">${esc(ba.status_message)}</div>

      <div class="assessment-meters">
        <div class="assessment-meter-track">
          <div class="assessment-meter-fill" style="background:${color}; width:${Math.min(ba.percentage_consumed, 100)}%;"></div>
        </div>
        <span class="assessment-pct">${ba.percentage_consumed}%</span>
      </div>

      ${suggestionsHTML}

      <div class="assessment-disclaimer">
        ℹ️ Estimates calculated independently using standard rates without artificial capping. Actual expenses depend on seasonal demand and booking timing.
      </div>
    </div>
  `;
}


// ─── Budget Breakdown Grid (All Categories Reconciled) ───
function renderBudgetBreakdownGrid(ba, c) {
  const cats = ba.categories;

  const rows = [
    { key: 'transportation', label: 'Transit & Local Transport', icon: '🚆', item: cats.transportation },
    { key: 'accommodation', label: 'Accommodation', icon: '🏨', item: cats.accommodation },
    { key: 'food', label: 'Food & Dining', icon: '🍽️', item: cats.food },
    { key: 'sightseeing', label: 'Attractions & Sightseeing', icon: '🎫', item: cats.sightseeing },
    { key: 'miscellaneous', label: 'Emergency Contingency', icon: '🛡️', item: cats.miscellaneous }
  ];

  return `
    <div class="budget-card">
      <div class="budget-title">
        <span>💰 Transparent Trip Expense Breakdown</span>
        <span class="budget-badge-pill">Reconciled Sum</span>
      </div>

      <div class="budget-table-responsive">
        <table class="budget-table">
          <thead>
            <tr>
              <th>Expense Category</th>
              <th>Calculation Basis</th>
              <th>Group Total</th>
              <th>Per Person</th>
            </tr>
          </thead>
          <tbody>
            ${rows.map(r => `
              <tr>
                <td class="col-cat">
                  <span class="cat-icon">${r.icon}</span>
                  <strong>${esc(r.label)}</strong>
                </td>
                <td class="col-basis">${esc(r.item.basis)}</td>
                <td class="col-total"><strong>${money(r.item.total, c)}</strong></td>
                <td class="col-pp">${money(r.item.per_person, c)}</td>
              </tr>
            `).join('')}
          </tbody>
          <tfoot>
            <tr class="total-row">
              <td colspan="2"><strong>Total Estimated Expenses</strong></td>
              <td><strong>${money(ba.total_estimated_trip_cost, c)}</strong></td>
              <td><strong>${money(ba.total_estimated_per_person, c)}</strong></td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  `;
}


// ─── Day-by-Day Itinerary with Routes (Phase 4 & 5) ───
function renderDaysItinerary(itin, destination, c) {
  return itin.map((day, idx) => {
    const isRest = Boolean(day.is_rest_day);
    const restBadge = isRest ? '<span style="background: #e0f2fe; color: #0369a1; padding: 2px 8px; border-radius: 999px; font-size: 0.72rem; font-weight: 700; margin-left: 8px;">🌴 Leisure & Exploration</span>' : '';
    const restBanner = (isRest && day.rest_day_note) ? `
      <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 10px 14px; margin-bottom: 14px; color: #166534; font-size: 0.85rem; line-height: 1.5;">
        ℹ️ <strong>Rest & Leisure Day:</strong> ${esc(day.rest_day_note)}
      </div>
    ` : '';

    return `
      <div class="day-card" data-day="${day.day_number}">
        <div class="day-header">
          <div class="day-number">${day.day_number}</div>
          <div class="day-meta">
            <div class="day-name">Day ${day.day_number} · ${esc(day.date_formatted)} ${restBadge}</div>
            <div class="day-date">Total Route: ~${day.day_total_route_km} km road travel</div>
          </div>
          <div class="day-toggle">▾</div>
        </div>

        <div class="day-body">
          ${restBanner}

          <!-- Morning Activity -->
          ${renderActivitySlot(day.morning, 'Morning', '🌅', 'morning-badge', c)}

          <!-- Route Morning to Afternoon -->
          ${renderRouteConnector(day.route_morning_to_afternoon)}

          <!-- Afternoon Activity -->
          ${renderActivitySlot(day.afternoon, 'Afternoon', '☀️', 'afternoon-badge', c)}

          <!-- Food Stop & Rest Period -->
          <div class="itinerary-interstitial-row">
            <div class="food-stop-pill">
              <span class="pill-icon">🍲</span>
              <div>
                <strong>Suggested Lunch Stop:</strong>
                <span>${esc(day.suggested_food_stop)}</span>
              </div>
            </div>
            <div class="rest-break-pill">
              <span class="pill-icon">☕</span>
              <div>
                <strong>Rest Break:</strong>
                <span>${esc(day.suggested_rest_period)}</span>
              </div>
            </div>
          </div>

          <!-- Route Afternoon to Evening -->
          ${renderRouteConnector(day.route_afternoon_to_evening)}

          <!-- Evening Activity -->
          ${renderActivitySlot(day.evening, 'Evening', '🌆', 'evening-badge', c)}
        </div>
      </div>
    `;
  }).join('');
}


function renderActivitySlot(slot, periodLabel, icon, badgeClass, c) {
  if (!slot) return '';  // null guard: slot may be undefined on rest days
  const feeLabel = slot.entry_fee_per_person > 0 ? `${money(slot.entry_fee_per_person, c)} / person` : 'Free Entry';

  return `
    <div class="activity-slot">
      <div class="slot-time-col">
        <span class="slot-period-badge ${badgeClass}">${icon} ${periodLabel}</span>
        <span class="slot-time">${esc(slot.time)}</span>
      </div>
      <div class="slot-info">
        <div class="slot-title-row">
          <h4 class="slot-name">${esc(slot.name)}</h4>
          <span class="slot-category-chip">${esc(slot.category)}</span>
        </div>
        <p class="slot-desc">${esc(slot.description)}</p>
        <div class="slot-meta-tags">
          <span class="meta-tag">⏰ Duration: ${esc(slot.visit_duration)}</span>
          <span class="meta-tag">🕒 Hours: ${esc(slot.opening_hours)}</span>
          <span class="meta-tag">🎟️ Ticket: ${feeLabel}</span>
        </div>
        <a class="slot-maps-link" href="${esc(slot.google_maps_url)}" target="_blank" rel="noopener noreferrer">
          📍 Open in Google Maps ↗
        </a>
      </div>
      <div class="slot-cost-box">
        <span class="cost-label">Est. Group Ticket</span>
        <strong class="cost-val">${money(slot.entry_fee_total, c)}</strong>
      </div>
    </div>
  `;
}


function renderRouteConnector(route) {
  if (!route) return '';
  return `
    <div class="route-connector-box">
      <span class="route-car-icon">🚗</span>
      <div class="route-details-wrap">
        <span class="route-distance-text">${route.distance_km} km</span>
        <span class="route-time-text">(~${route.duration_formatted} drive from ${esc(route.from_name)} to ${esc(route.to_name)})</span>
      </div>
      <a class="route-directions-link" href="${esc(route.maps_directions_url)}" target="_blank" rel="noopener noreferrer">
        Directions ↗
      </a>
    </div>
  `;
}


// ─── 5-Way Transportation Comparison (Phase 6) ───
function renderTransportComparison(tc, intercity, c) {
  return `
    <div class="transport-section-wrapper">
      <div class="transport-header-card">
        <h3>🚆 Starting Location to Destination Transport Options</h3>
        <p>
          Route: <strong>${esc(tc.start_location)}</strong> to <strong>${esc(tc.destination)}</strong>
          (~${tc.road_distance_km} km road distance · ~${tc.air_distance_km} km air distance)
        </p>
      </div>

      <div class="transport-cards-grid">
        ${tc.options.map(opt => {
          const badgesHTML = (opt.badges || []).map(b => `<span class="badge-tag">${esc(b)}</span>`).join('');
          return `
            <div class="transport-card ${!opt.available ? 'card-unavailable' : ''}">
              <div class="trans-top">
                <span class="trans-icon">${opt.icon}</span>
                <div class="trans-title-col">
                  <h4>${esc(opt.mode)}</h4>
                  <span class="trans-provider">${esc(opt.booking_provider)}</span>
                </div>
                <div class="trans-badges">${badgesHTML}</div>
              </div>

              <div class="trans-body">
                <p class="trans-details">${esc(opt.details)}</p>
                <div class="trans-metrics-grid">
                  <div class="t-metric">
                    <span class="t-lbl">EST. DURATION</span>
                    <strong>${esc(opt.duration_formatted)}</strong>
                  </div>
                  <div class="t-metric">
                    <span class="t-lbl">ONE-WAY / PERSON</span>
                    <strong>${money(opt.cost_per_person_inr, c)}</strong>
                  </div>
                  <div class="t-metric">
                    <span class="t-lbl">GROUP ROUND-TRIP</span>
                    <strong class="color-blue">${money(opt.return_total_inr, c)}</strong>
                  </div>
                </div>
                <p class="trans-notes">ℹ️ ${esc(opt.notes)}</p>
              </div>

              <div class="trans-footer">
                ${opt.booking_link ? `
                  <a class="btn-book-transport" href="${esc(opt.booking_link)}" target="_blank" rel="noopener noreferrer">
                    Search on ${esc(opt.booking_provider)} ↗
                  </a>
                ` : `
                  <span class="btn-disabled-transport">Not Recommended For Short Distances</span>
                `}
              </div>
            </div>
          `;
        }).join('')}
      </div>
    </div>
  `;
}


// ─── Weather & Packing (Phase 10) ───
function renderWeatherSection(w, destination) {
  if (!w || !w.available) {
    return `<div class="weather-card"><p>Weather data currently unavailable for ${esc(destination)}.</p></div>`;
  }

  const forecastHTML = (w.forecast || []).map(d => `
    <div class="forecast-day-card">
      <div class="f-date">${esc(d.date.slice(5))}</div>
      <div class="f-icon">${d.icon}</div>
      <div class="f-temp">${d.max_temp}° / ${d.min_temp}°C</div>
      <div class="f-cond">${esc(d.condition)}</div>
      <div class="f-rain">🌧️ ${d.rain_probability}%</div>
    </div>
  `).join('');

  return `
    <div class="weather-section-card">
      <div class="weather-current-hero">
        <div class="weather-big-temp">
          <span class="w-hero-icon">${w.icon}</span>
          <div class="w-temp-number">${w.temperature}°C</div>
        </div>
        <div class="weather-hero-meta">
          <h4>${esc(destination)} Current Climate</h4>
          <div class="weather-cond-badge">${esc(w.condition)}</div>
          <div class="w-sub-metrics">
            <span>💧 Humidity: ${w.humidity}%</span>
            <span>💨 Wind: ${w.wind_speed_kmh} km/h</span>
            <span>🌐 ${esc(w.provider)}</span>
          </div>
        </div>
      </div>

      ${forecastHTML ? `
        <div class="forecast-heading">📅 5-Day Destination Forecast:</div>
        <div class="forecast-grid">${forecastHTML}</div>
      ` : ''}

      <div class="weather-tips-box">
        <h5>🎒 Weather-Tailored Packing & Travel Advice:</h5>
        <ul>
          ${(w.travel_advice || []).map(t => `<li>${esc(t)}</li>`).join('')}
        </ul>
      </div>
    </div>
  `;
}


// ─── Leaflet Interactive Map (Phase 8) ───
function initLeafletMap(data) {
  const mapContainer = document.getElementById('interactive-trip-map');
  if (!mapContainer || typeof L === 'undefined') return;

  if (leafletMapInstance) {
    leafletMapInstance.remove();
    leafletMapInstance = null;
  }

  const attractions = data.attractions_summary || [];
  if (!attractions.length) return;

  const firstLat = attractions[0].lat;
  const firstLon = attractions[0].lon;

  leafletMapInstance = L.map('interactive-trip-map').setView([firstLat, firstLon], 12);

  // Free OpenStreetMap Tile Layer
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '© OpenStreetMap contributors'
  }).addTo(leafletMapInstance);

  const latlngs = [];

  attractions.forEach((a, idx) => {
    if (a.lat && a.lon) {
      const pt = [a.lat, a.lon];
      latlngs.push(pt);

      const marker = L.marker(pt).addTo(leafletMapInstance);
      const popupContent = `
        <div style="font-family:'Plus Jakarta Sans',sans-serif; min-width:180px;">
          <h4 style="margin:0 0 4px; color:#0f172a; font-size:0.95rem;">${esc(a.name)}</h4>
          <span style="font-size:0.75rem; color:#2563eb; font-weight:700;">${esc(a.category.toUpperCase())}</span>
          <p style="margin:6px 0; font-size:0.8rem; color:#64748b;">${esc(a.description.slice(0, 90))}...</p>
          <a href="https://www.google.com/maps/search/?api=1&query=${a.lat},${a.lon}" target="_blank"
             style="font-size:0.75rem; color:#2563eb; font-weight:800; text-decoration:none;">
            Open in Google Maps ↗
          </a>
        </div>
      `;
      marker.bindPopup(popupContent);
    }
  });

  // Polyline connecting attractions
  if (latlngs.length > 1) {
    const routeLine = L.polyline(latlngs, {
      color: '#2563eb',
      weight: 4,
      opacity: 0.75,
      dashArray: '8, 8'
    }).addTo(leafletMapInstance);
    leafletMapInstance.fitBounds(routeLine.getBounds(), { padding: [30, 30] });
  }
}


// ─── Day Card Collapse Toggle ───
function bindDayCardToggles() {
  document.querySelectorAll('.day-header').forEach(hdr => {
    hdr.addEventListener('click', () => {
      hdr.closest('.day-card').classList.toggle('collapsed');
    });
  });
}


// ─── Phase 11: Save, Share, Copy & PDF Handlers ───
function bindActionButtons(data) {
  // Save Trip
  const saveBtn = document.getElementById('btn-save-trip');
  saveBtn.addEventListener('click', async () => {
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving…';
    try {
      const resp = await fetch('/api/trips/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      const res = await resp.json();
      if (res.success) {
        saveBtn.textContent = '✅ Saved';
        saveBtn.style.background = '#10b981';
        showShareModal(res.share_url);
      } else {
        alert(res.error || 'Failed to save trip.');
        saveBtn.textContent = '💾 Save Trip';
        saveBtn.disabled = false;
      }
    } catch {
      alert('Could not connect to server to save trip.');
      saveBtn.textContent = '💾 Save Trip';
      saveBtn.disabled = false;
    }
  });

  // Share Trip
  document.getElementById('btn-share-trip').addEventListener('click', async () => {
    // If not saved yet, save it first to get an ID
    if (!data.trip_id) {
      try {
        const resp = await fetch('/api/trips/save', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data)
        });
        const res = await resp.json();
        if (res.success) {
          data.trip_id = res.trip_id;
          showShareModal(res.share_url);
        }
      } catch {
        showShareModal(window.location.href);
      }
    } else {
      showShareModal(`${window.location.origin}/trip/${data.trip_id}`);
    }
  });

  // Copy Summary to Clipboard
  document.getElementById('btn-copy-summary').addEventListener('click', () => {
    const summaryText = `✈️ TRIPWISE TRAVEL PLAN: ${data.start_location} → ${data.destination}\n` +
      `📅 Dates: ${data.start_date} to ${data.end_date} (${data.num_days} days, ${data.travelers} travellers)\n` +
      `💰 Total Estimated Cost: ${data.currency} ${data.budget_analysis.total_estimated_trip_cost.toLocaleString()}\n` +
      `📊 Budget Status: ${data.budget_analysis.status_label}\n` +
      `🛣️ Distance: ~${data.intercity_travel.distance_km} km\n` +
      `Explore further with TripWise!`;
    navigator.clipboard.writeText(summaryText).then(() => {
      const btn = document.getElementById('btn-copy-summary');
      btn.textContent = '✅ Copied!';
      setTimeout(() => btn.textContent = '📋 Copy Summary', 2000);
    });
  });

  // Export PDF via Server-Side ReportLab API
  const btnPdf = document.getElementById('btn-print-pdf');
  if (btnPdf) {
    btnPdf.addEventListener('click', async () => {
      if (!currentTripData) {
        alert('Please generate an itinerary first before exporting to PDF.');
        return;
      }
      const origText = btnPdf.textContent;
      btnPdf.textContent = '⏳ Generating PDF...';
      btnPdf.disabled = true;

      try {
        const resp = await fetch('/api/trips/export-pdf', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(currentTripData)
        });

        if (!resp.ok) {
          const errData = await resp.json().catch(() => ({}));
          throw new Error(errData.error || `Server returned ${resp.status}`);
        }

        const blob = await resp.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        const destName = (currentTripData.destination || 'Trip').replace(/\s+/g, '_');
        a.download = `TripWise_${destName}_Itinerary.pdf`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
      } catch (err) {
        console.error('PDF export failed:', err);
        // Fallback to window.print if server export fails
        document.querySelectorAll('.day-card').forEach(c => c.classList.remove('collapsed'));
        window.print();
      } finally {
        btnPdf.textContent = origText;
        btnPdf.disabled = false;
      }
    });
  }
}


// ─── Modal Logic (Saved Trips & Share) ───
function initModals() {
  // Share modal copy button
  btnCopyShareUrl.addEventListener('click', () => {
    navigator.clipboard.writeText(shareUrlInput.value).then(() => {
      copyStatus.textContent = '✅ Link copied to clipboard!';
      setTimeout(() => copyStatus.textContent = '', 2500);
    });
  });

  closeShareModal.addEventListener('click', () => shareModal.hidden = true);
  closeSavedModal.addEventListener('click', () => savedTripsModal.hidden = true);

  navSavedTripsBtn.addEventListener('click', openSavedTripsModal);
  mobileSavedTripsBtn.addEventListener('click', () => {
    mobileMenu.classList.remove('open');
    openSavedTripsModal();
  });
  footerSavedLink.addEventListener('click', openSavedTripsModal);
}

function showShareModal(url) {
  shareUrlInput.value = url;
  copyStatus.textContent = '';
  shareModal.hidden = false;
}

async function openSavedTripsModal() {
  savedTripsModal.hidden = false;
  savedTripsList.innerHTML = '<p class="empty-state-text">Loading saved trips...</p>';

  try {
    const resp = await fetch('/api/trips');
    const data = await resp.json();
    const trips = data.trips || [];

    if (!trips.length) {
      savedTripsList.innerHTML = '<p class="empty-state-text">No trips saved yet. Generate an itinerary and click "Save Trip"!</p>';
      return;
    }

    savedTripsList.innerHTML = trips.map(t => `
      <div class="saved-trip-row" id="saved-trip-${t.id}">
        <div class="saved-trip-info">
          <div class="saved-trip-title">🛫 ${esc(t.start_location || 'Origin')} → ${esc(t.destination)}</div>
          <div class="saved-trip-meta">
            ${esc(t.start_date)} to ${esc(t.end_date)} · ${t.travelers} traveller(s) · ${t.currency} ${Number(t.total_cost || 0).toLocaleString()}
          </div>
        </div>
        <div class="saved-trip-actions">
          <button class="btn-open-trip" data-id="${t.id}">View Plan</button>
          <button class="btn-del-trip" data-id="${t.id}">Delete</button>
        </div>
      </div>
    `).join('');

    // Bind view & delete
    savedTripsList.querySelectorAll('.btn-open-trip').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = btn.dataset.id;
        const res = await fetch(`/api/trips/${id}`);
        if (res.ok) {
          const trip = await res.json();
          currentTripData = trip;
          renderCompletePlan(trip);
          savedTripsModal.hidden = true;
          resultsSection.hidden = false;
          resultsSection.scrollIntoView({ behavior: 'smooth' });
        }
      });
    });

    savedTripsList.querySelectorAll('.btn-del-trip').forEach(btn => {
      btn.addEventListener('click', async () => {
        if (!confirm('Are you sure you want to delete this trip?')) return;
        const id = btn.dataset.id;
        const res = await fetch(`/api/trips/${id}`, { method: 'DELETE' });
        if (res.ok) {
          document.getElementById(`saved-trip-${id}`)?.remove();
        }
      });
    });

  } catch {
    savedTripsList.innerHTML = '<p class="empty-state-text">Failed to load saved trips.</p>';
  }
}


// ─── Phase 9: AI Travel Chatbot Drawer ───
function initChatbot() {
  const toggleChat = (show) => {
    chatbotDrawer.classList.toggle('open', show);
    floatingChatTrigger.classList.toggle('hidden', show);
  };

  floatingChatTrigger.addEventListener('click', () => toggleChat(true));
  openChatNavBtn.addEventListener('click', () => toggleChat(true));
  mobileChatBtn.addEventListener('click', () => {
    mobileMenu.classList.remove('open');
    toggleChat(true);
  });
  closeChatBtn.addEventListener('click', () => toggleChat(false));

  // Quick Prompt Pills
  document.querySelectorAll('.chat-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      chatInput.value = pill.dataset.prompt;
      submitChat();
    });
  });

  chatForm.addEventListener('submit', (e) => {
    e.preventDefault();
    submitChat();
  });
}

async function submitChat() {
  const msg = chatInput.value.trim();
  if (!msg) return;

  chatInput.value = '';
  chatInput.disabled = true;
  appendChatMessage(msg, 'user');

  // Build thinking indicator with animated dots
  const loadingBubble = appendChatLoadingBubble();

  try {
    const resp = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: msg,
        history: currentChatHistory,
        trip_context: currentTripData || {
          destination: document.getElementById('destination').value.trim() || 'Goa',
          start_location: startLocInput.value.trim() || 'Visakhapatnam',
          travelers: travelersInput.value,
          currency: currencySelect.value
        }
      })
    });

    const data = await resp.json();
    loadingBubble.remove();
    chatInput.disabled = false;
    chatInput.focus();

    if (data.reply) {
      if (data.updated_context) {
        currentTripData = data.updated_context;
        const destInput = document.getElementById('destination');
        if (destInput && data.updated_context.destination) {
          destInput.value = data.updated_context.destination;
        }
        if (travelersInput && data.updated_context.travelers) {
          travelersInput.value = data.updated_context.travelers;
        }
      }

      appendChatMessage(data.reply, 'assistant', false, {
        provider: data.provider,
        sourceIndicator: data.source_indicator,
        searchSources: data.search_sources || [],
        dataLabels: data.data_labels || []
      });
      if (data.provider) chatProviderBadge.textContent = data.provider;
      // Update badge style based on provider type
      chatProviderBadge.className = 'chat-provider-badge';
      if (data.source_indicator === 'live_ai') chatProviderBadge.classList.add('badge-ai');
      else if (data.source_indicator === 'ollama') chatProviderBadge.classList.add('badge-ollama');
      else chatProviderBadge.classList.add('badge-offline');

      currentChatHistory.push({ sender: 'user', text: msg });
      currentChatHistory.push({ sender: 'assistant', text: data.reply });
      // Keep history to last 20 messages to avoid payload bloat
      if (currentChatHistory.length > 20) currentChatHistory = currentChatHistory.slice(-20);
    } else {
      appendChatMessage('I encountered an issue generating a response. Please ask again.', 'assistant');
    }
  } catch (err) {
    loadingBubble.remove();
    chatInput.disabled = false;
    appendChatMessage('Unable to connect to the assistant right now. Please verify your connection.', 'assistant');
  }
}

function appendChatLoadingBubble() {
  const msgDiv = document.createElement('div');
  msgDiv.className = 'chat-msg msg-assistant chat-loading';
  msgDiv.innerHTML = `
    <div class="msg-bubble loading-bubble">
      <span class="loading-dot"></span>
      <span class="loading-dot"></span>
      <span class="loading-dot"></span>
    </div>`;
  chatMessages.appendChild(msgDiv);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return msgDiv;
}

function formatChatMarkdown(text) {
  // Escape HTML first (note: * has no HTML entity so it survives untouched)
  let s = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');

  // Bold **text** (must come before italic to avoid conflicting * matches)
  s = s.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

  // Italic *text* (single asterisk, not followed/preceded by another *)
  s = s.replace(/(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)/g, '<em>$1</em>');

  // Inline code `code`
  s = s.replace(/`([^`]+)`/g, '<code>$1</code>');

  // Markdown-style links [text](url)
  s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer" class="chat-link">$1 ↗</a>');

  // Bare URLs (not already in an href)
  s = s.replace(/(^|[\s(])(https?:\/\/[^\s)<]+)/g,
    '$1<a href="$2" target="_blank" rel="noopener noreferrer" class="chat-link">$2 ↗</a>');

  // Headers ### and ##
  s = s.replace(/^###\s+(.+)$/gm, '<h4 class="chat-h4">$1</h4>');
  s = s.replace(/^##\s+(.+)$/gm, '<h3 class="chat-h3">$1</h3>');

  // Bullet lines starting with • or -
  s = s.replace(/^[•\-]\s+(.+)$/gm, '<li>$1</li>');
  s = s.replace(/(<li>.*<\/li>\n?)+/g, '<ul class="chat-ul">$&</ul>');

  // Numbered list lines — wrap consecutive items in <ol>
  s = s.replace(/^(\d+)\.\s+(.+)$/gm, '<li data-ol>$2</li>');
  s = s.replace(/(<li data-ol>[\s\S]*?<\/li>\n?)+/g, (m) =>
    '<ol class="chat-ol">' + m.replace(/ data-ol/g, '') + '</ol>'
  );

  // Paragraphs: double newline -> <br><br>, single newline -> <br>
  s = s.replace(/\n\n/g, '<br><br>');
  s = s.replace(/\n/g, '<br>');

  return s;
}

function appendChatMessage(text, role, isTemp = false, meta = {}) {
  const msgDiv = document.createElement('div');
  msgDiv.className = `chat-msg msg-${role}`;
  if (isTemp) msgDiv.classList.add('chat-temp');

  const formatted = role === 'assistant' ? formatChatMarkdown(text) : esc(text);

  // Build data-labels row (live data indicators)
  let labelsHtml = '';
  if (meta.dataLabels && meta.dataLabels.length) {
    labelsHtml = `<div class="chat-data-labels">${
      meta.dataLabels.map(l => `<span class="chat-data-tag">${esc(l)}</span>`).join('')
    }</div>`;
  }

  // Build search sources row
  let sourcesHtml = '';
  if (meta.searchSources && meta.searchSources.length) {
    const links = meta.searchSources.map(s =>
      `<a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer" class="chat-source-link">${esc(s.title || s.url)}</a>`
    ).join('');
    sourcesHtml = `<div class="chat-sources"><span class="sources-label">🔍 Sources:</span>${links}</div>`;
  }

  msgDiv.innerHTML = `<div class="msg-bubble">${formatted}${labelsHtml}${sourcesHtml}</div>`;
  chatMessages.appendChild(msgDiv);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return msgDiv;
}
