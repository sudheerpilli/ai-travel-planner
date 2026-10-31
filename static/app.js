const form = document.getElementById("planner-form");
const statusBox = document.getElementById("status");
const results = document.getElementById("results");
const submitBtn = document.getElementById("submit-btn");
const today = new Date();
const dateInput = document.getElementById("start_date");
dateInput.min = today.toISOString().slice(0, 10);
document.getElementById("end_date").min = dateInput.min;
dateInput.addEventListener("change", () => {
  document.getElementById("end_date").min = dateInput.value || dateInput.min;
});

const symbols = {INR:"₹", USD:"$", EUR:"€", GBP:"£"};
function money(amount, currency) {
  const symbol = symbols[currency] || currency + " ";
  return symbol + Number(amount).toLocaleString(undefined, {maximumFractionDigits:0});
}
function escapeHTML(value) {
  return String(value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}
function render(data) {
  const c = data.currency;
  const costs = data.costs;
  let html = `<div class="card"><p class="eyebrow">YOUR TRIP PLAN</p><h2>${escapeHTML(data.destination)}</h2>
  <p>${escapeHTML(data.start_date)} → ${escapeHTML(data.end_date)} · ${data.travelers} traveler(s)</p>
  <div class="summary-grid">
    <div class="metric"><span>Estimated total</span><strong>${money(costs.estimated_total,c)}</strong></div>
    <div class="metric"><span>Per person</span><strong>${money(costs.per_person,c)}</strong></div>
    <div class="metric"><span>Your budget</span><strong>${money(data.budget,c)}</strong></div>
    <div class="metric"><span>Budget remaining</span><strong>${money(data.budget-costs.estimated_total,c)}</strong></div>
  </div>
  <h3>Estimated budget breakdown</h3>
  <div class="summary-grid">
    ${[["Transport",costs.transport],["Accommodation",costs.accommodation],["Food",costs.food],["Attractions",costs.attractions]].map(([k,v])=>`<div class="metric"><span>${k}</span><strong>${money(v,c)}</strong></div>`).join("")}
  </div></div>`;
  data.days.forEach(day => {
    html += `<article class="day"><h3>Day ${day.day} · ${escapeHTML(day.date)}</h3>`;
    ["morning","afternoon","evening"].forEach(key => {
      const s = day[key];
      const q = encodeURIComponent(s.name + " " + data.destination);
      html += `<div class="slot"><time>${escapeHTML(s.time)}</time><div><h4>${escapeHTML(s.name)}</h4><p>${escapeHTML(s.description)}</p><a class="map-link" href="https://www.google.com/maps/search/?api=1&query=${q}" target="_blank" rel="noopener noreferrer">Find on Google Maps ↗</a></div><div class="cost">${money(s.cost,c)}</div></div>`;
    });
    html += `</article>`;
  });
  html += `<div class="card"><h3>Before you go</h3><ul class="notes">${data.notes.map(n=>`<li>${escapeHTML(n)}</li>`).join("")}</ul>
  <button id="print-btn" type="button">Print / Save itinerary as PDF</button></div>`;
  results.innerHTML = html;
  results.hidden = false;
  document.getElementById("print-btn").addEventListener("click", () => window.print());
}
form.addEventListener("submit", async event => {
  event.preventDefault();
  statusBox.textContent = "";
  results.hidden = true;
  submitBtn.disabled = true;
  submitBtn.textContent = "Creating your plan…";
  const payload = {
    destination: document.getElementById("destination").value,
    start_date: document.getElementById("start_date").value,
    end_date: document.getElementById("end_date").value,
    budget: document.getElementById("budget").value,
    currency: document.getElementById("currency").value,
    travelers: document.getElementById("travelers").value,
    interests: [...document.querySelectorAll('input[name="interest"]:checked')].map(x => x.value)
  };
  try {
    const response = await fetch("/api/plan", {
      method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Could not create your itinerary.");
    render(data);
    results.scrollIntoView({behavior:"smooth", block:"start"});
  } catch (err) {
    statusBox.textContent = err.message || "Unable to connect. Please make sure the Flask server is running.";
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerHTML = 'Create my itinerary <span>→</span>';
  }
});
