// DANIELA — BCH Executive Dashboard
// Pure vanilla JS — auto-refreshes every 30 seconds

const API = "http://localhost:8000/api/v1";
const REFRESH_MS = 30_000;

// ── Boot ──
document.addEventListener("DOMContentLoaded", () => {
  tickClock();
  setInterval(tickClock, 1_000);
  refreshAll();
  setInterval(refreshAll, REFRESH_MS);
  document.getElementById("chat-form").addEventListener("submit", onChatSubmit);
});

// ── Clock ──
function tickClock() {
  document.getElementById("clock").textContent =
    new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

// ── Refresh everything ──
async function refreshAll() {
  await Promise.allSettled([
    fetchHealth(),
    fetchStatus(),
    fetchChillers(),
    fetchLeaks(),
  ]);
  document.getElementById("last-update").textContent =
    new Date().toLocaleTimeString("en-GB");
}

// ── Health ──
async function fetchHealth() {
  try {
    const r = await fetch(`${API}/health`);
    const d = await r.json();
    const c = d.checks || {};
    setPill("pill-sim", c.simulator_running);
    setPill("pill-db",  c.db_connected);
    setPill("pill-key", c.api_key_configured);
    document.getElementById("version-tag").textContent = `v${d.version || "?"}`;
    document.getElementById("footer-version").textContent = d.version || "?";
  } catch { setPill("pill-sim", false); setPill("pill-db", false); setPill("pill-key", false); }
}

function setPill(id, ok) {
  const el = document.getElementById(id);
  el.classList.toggle("ok",   !!ok);
  el.classList.toggle("fail", !ok);
}

// ── Status (KPI cards) ──
async function fetchStatus() {
  try {
    const r = await fetch(`${API}/status`);
    const d = (await r.json()).data;
    const resort = d.resort || {};
    document.getElementById("kpi-units").textContent   = resort.total_units ?? "--";
    document.getElementById("kpi-solar").innerHTML      = `${resort.solar_production_kw ?? "--"} <small>kW</small>`;
    document.getElementById("kpi-elec").innerHTML       = `${resort.total_electricity_kwh ?? "--"} <small>kWh</small>`;
    // active chillers count set by fetchChillers
  } catch { /* keep previous values */ }
}

// ── Chillers ──
async function fetchChillers() {
  try {
    const r = await fetch(`${API}/chillers`);
    const d = await r.json();
    const chillers = d.chillers || [];

    document.getElementById("kpi-chillers").textContent = chillers.length;

    const tbody = document.getElementById("chillers-body");
    if (!chillers.length) {
      tbody.innerHTML = `<tr><td colspan="5" class="empty">No chiller data</td></tr>`;
      return;
    }
    tbody.innerHTML = chillers.map(ch => {
      const statusChip = ch.degraded
        ? `<span class="chip chip-danger">degraded</span>`
        : `<span class="chip chip-ok">${ch.status}</span>`;
      const degChip = ch.degraded
        ? `<span class="chip chip-danger">YES</span>`
        : `<span class="chip chip-ok">NO</span>`;
      const copClass = ch.degraded ? ' style="color:#EF4444;font-weight:700"' : "";
      return `<tr>
        <td><strong>${ch.id}</strong></td>
        <td${copClass}>${ch.cop}</td>
        <td>${ch.power_kw}</td>
        <td>${statusChip}</td>
        <td>${degChip}</td>
      </tr>`;
    }).join("");
  } catch {
    document.getElementById("chillers-body").innerHTML =
      `<tr><td colspan="5" class="empty">Failed to load</td></tr>`;
  }
}

// ── Leaks ──
async function fetchLeaks() {
  try {
    const r = await fetch(`${API}/leaks`);
    const d = await r.json();
    const leaks = d.leaks || [];

    document.getElementById("leak-count").textContent = d.total;

    const tbody = document.getElementById("leaks-body");
    if (!leaks.length) {
      tbody.innerHTML = `<tr><td colspan="5" class="empty">No active leaks</td></tr>`;
      return;
    }
    tbody.innerHTML = leaks.map(l => {
      const conf = l.confidence > 0
        ? `${(l.confidence * 100).toFixed(0)}%`
        : "—";
      const srcChip = l.source === "database"
        ? `<span class="chip chip-warn">DB</span>`
        : `<span class="chip chip-ok">SIM</span>`;
      return `<tr>
        <td><strong>${l.room_id}</strong></td>
        <td>${l.building}</td>
        <td>${l.flow_lph}</td>
        <td>${conf}</td>
        <td>${srcChip}</td>
      </tr>`;
    }).join("");
  } catch {
    document.getElementById("leaks-body").innerHTML =
      `<tr><td colspan="5" class="empty">Failed to load</td></tr>`;
  }
}

// ── Chat ──
async function onChatSubmit(e) {
  e.preventDefault();
  const input = document.getElementById("chat-input");
  const msg = input.value.trim();
  if (!msg) return;

  appendBubble(msg, "user");
  input.value = "";

  const btn = document.getElementById("chat-send");
  btn.disabled = true;
  btn.textContent = "…";

  try {
    const r = await fetch(`${API}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: msg, language: "en" }),
    });
    const d = await r.json();
    appendBubble(d.response, "daniela");
  } catch {
    appendBubble("Sorry, I could not reach the server. Please try again.", "daniela");
  } finally {
    btn.disabled = false;
    btn.textContent = "Send";
  }
}

function appendBubble(text, who) {
  const log = document.getElementById("chat-log");
  const div = document.createElement("div");
  div.className = `chat-bubble ${who}`;
  div.textContent = text;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}
