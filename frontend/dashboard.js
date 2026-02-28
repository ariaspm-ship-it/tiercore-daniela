// DANIELA — BCH Enterprise Dashboard
// Vanilla JS — Chart.js for COP, auto-refresh 30s, voice, demo mode

const API = "http://localhost:8000/api/v1";
const REFRESH_MS = 30_000;
const COP_HISTORY_MAX = 20;

let copChart = null;
const copHistory = { labels: [], datasets: {} };
let prevLeakCount = 0;
let prevDegradedIds = new Set();

// ── Boot ──────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  tickClock();
  setInterval(tickClock, 1000);
  initCopChart();
  refreshAll();
  setInterval(refreshAll, REFRESH_MS);
  document.getElementById("chat-form").addEventListener("submit", onChatSubmit);
  initVoice();
});

// ── Clock ─────────────────────────────────────────────────────────────
function tickClock() {
  document.getElementById("clock").textContent =
    new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

// ── Refresh all ───────────────────────────────────────────────────────
async function refreshAll() {
  await Promise.allSettled([fetchHealth(), fetchStatus(), fetchChillers(), fetchLeaks()]);
  document.getElementById("last-update").textContent =
    new Date().toLocaleTimeString("en-GB");
}

// ── Health ─────────────────────────────────────────────────────────────
async function fetchHealth() {
  try {
    const d = await (await fetch(`${API}/health`)).json();
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
  el.classList.toggle("ok", !!ok);
  el.classList.toggle("fail", !ok);
}

// ── Status / KPIs + Heatmap ───────────────────────────────────────────
async function fetchStatus() {
  try {
    const d = (await (await fetch(`${API}/status`)).json()).data;
    const resort = d.resort || {};
    document.getElementById("kpi-units").textContent = resort.total_units ?? "--";
    document.getElementById("kpi-solar").innerHTML   = `${resort.solar_production_kw ?? "--"}<small>kW</small>`;
    document.getElementById("kpi-elec").innerHTML    = `${resort.total_electricity_kwh ?? "--"}<small>kWh</small>`;
    updateHeatmap(d.buildings || {});
  } catch {}
}

function updateHeatmap(buildings) {
  const grid = document.getElementById("heatmap-grid");
  const order = ["A", "B", "C"];
  const maxKwh = Math.max(...order.map(b => (buildings[b] || {}).electricity_kwh || 0), 1);

  grid.innerHTML = order.map(b => {
    const info = buildings[b] || {};
    const kwh = info.electricity_kwh || 0;
    const ratio = kwh / maxKwh;
    const level = ratio > 0.7 ? "level-high" : ratio > 0.4 ? "level-mid" : "level-low";
    const leak = (info.leaks_active || 0) > 0 ? "has-leak" : "";
    return `<div class="hm-building ${level} ${leak}">
      <span class="hm-label">${b}</span>
      <span class="hm-detail">${info.total_units || "?"} units</span>
      <span class="hm-kwh">${kwh} kWh</span>
    </div>`;
  }).join("");
}

// ── Chillers + COP Chart ──────────────────────────────────────────────
const CHILLER_COLORS = {
  "2CH-1": { line: "#3B82F6", bg: "rgba(59,130,246,.15)" },
  "2CH-2": { line: "#22C55E", bg: "rgba(34,197,94,.15)" },
  "2CH-3": { line: "#F59E0B", bg: "rgba(245,158,11,.15)" },
};

function initCopChart() {
  const ctx = document.getElementById("cop-chart").getContext("2d");
  copChart = new Chart(ctx, {
    type: "line",
    data: { labels: [], datasets: [] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { color: "#94A3B8", font: { family: "Inter", size: 11 } } },
        tooltip: { backgroundColor: "#0D2137", titleColor: "#C49A28", bodyColor: "#E2E8F0",
                   borderColor: "rgba(255,255,255,.08)", borderWidth: 1 }
      },
      scales: {
        x: { ticks: { color: "#475569", font: { size: 10 } }, grid: { color: "rgba(255,255,255,.03)" } },
        y: {
          min: 2.5, max: 5.5,
          ticks: { color: "#475569", font: { size: 10 } },
          grid: { color: "rgba(255,255,255,.05)" },
        }
      },
      elements: { point: { radius: 3, hoverRadius: 5 }, line: { tension: .35, borderWidth: 2 } },
      animation: { duration: 600, easing: "easeOutQuart" }
    }
  });

  // Threshold line (COP 3.5)
  copChart.options.plugins.annotation = undefined; // Chart.js annotation not loaded, draw manually via plugin
  copChart.options.plugins.afterDraw = undefined;
}

async function fetchChillers() {
  try {
    const d = await (await fetch(`${API}/chillers`)).json();
    const chillers = d.chillers || [];

    document.getElementById("kpi-chillers").textContent = chillers.length;

    // Table
    const tbody = document.getElementById("chillers-body");
    if (!chillers.length) {
      tbody.innerHTML = `<tr><td colspan="5" class="empty">No chiller data</td></tr>`;
      return;
    }

    const newDegraded = new Set();
    tbody.innerHTML = chillers.map(ch => {
      const sChip = ch.degraded
        ? `<span class="chip chip-danger">degraded</span>`
        : `<span class="chip chip-ok">${ch.status}</span>`;
      const dChip = ch.degraded
        ? `<span class="chip chip-danger">YES</span>`
        : `<span class="chip chip-ok">NO</span>`;
      const copStyle = ch.degraded ? ' style="color:#EF4444;font-weight:700"' : "";
      if (ch.degraded) newDegraded.add(ch.id);

      const dtt = ch.days_to_threshold != null ? ` (${ch.days_to_threshold}d)` : "";

      return `<tr>
        <td><strong>${ch.id}</strong></td>
        <td${copStyle}>${ch.cop}${dtt}</td>
        <td>${ch.power_kw} kW</td>
        <td>${sChip}</td>
        <td>${dChip}</td>
      </tr>`;
    }).join("");

    // Alert on new degradation
    for (const id of newDegraded) {
      if (!prevDegradedIds.has(id)) showToast(`Chiller ${id} is DEGRADED — COP below threshold`);
    }
    prevDegradedIds = newDegraded;

    // COP history
    const timeLabel = new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    copHistory.labels.push(timeLabel);
    if (copHistory.labels.length > COP_HISTORY_MAX) copHistory.labels.shift();

    for (const ch of chillers) {
      if (!copHistory.datasets[ch.id]) copHistory.datasets[ch.id] = [];
      copHistory.datasets[ch.id].push(ch.cop);
      if (copHistory.datasets[ch.id].length > COP_HISTORY_MAX) copHistory.datasets[ch.id].shift();
    }

    copChart.data.labels = [...copHistory.labels];
    copChart.data.datasets = Object.entries(copHistory.datasets).map(([id, data]) => ({
      label: id,
      data: [...data],
      borderColor: (CHILLER_COLORS[id] || {}).line || "#fff",
      backgroundColor: (CHILLER_COLORS[id] || {}).bg || "rgba(255,255,255,.1)",
      fill: true,
    }));
    copChart.update();

  } catch {
    document.getElementById("chillers-body").innerHTML =
      `<tr><td colspan="5" class="empty">Failed to load</td></tr>`;
  }
}

// ── Leaks ──────────────────────────────────────────────────────────────
async function fetchLeaks() {
  try {
    const d = await (await fetch(`${API}/leaks`)).json();
    const leaks = d.leaks || [];
    document.getElementById("leak-count").textContent = d.total;

    // Alert sound on new leaks
    if (d.total > prevLeakCount && prevLeakCount >= 0) {
      showToast(`New leak detected! ${d.total} active leak(s)`);
      playAlertSound();
    }
    prevLeakCount = d.total;

    const tbody = document.getElementById("leaks-body");
    if (!leaks.length) {
      tbody.innerHTML = `<tr><td colspan="5" class="empty">No active leaks</td></tr>`;
      return;
    }
    tbody.innerHTML = leaks.map(l => {
      const conf = l.confidence > 0 ? `${(l.confidence * 100).toFixed(0)}%` : "\u2014";
      const srcChip = l.source === "database"
        ? `<span class="chip chip-warn">DB</span>`
        : `<span class="chip chip-info">SIM</span>`;
      return `<tr>
        <td><strong>${l.room_id}</strong></td>
        <td>${l.building}</td>
        <td>${l.flow_lph} L/h</td>
        <td>${conf}</td>
        <td>${srcChip}</td>
      </tr>`;
    }).join("");
  } catch {
    document.getElementById("leaks-body").innerHTML =
      `<tr><td colspan="5" class="empty">Failed to load</td></tr>`;
  }
}

// ── Alert toast & sound ───────────────────────────────────────────────
function showToast(msg) {
  const t = document.getElementById("alert-toast");
  t.textContent = msg;
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 5000);
}

function playAlertSound() {
  try {
    const ac = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ac.createOscillator();
    const gain = ac.createGain();
    osc.connect(gain);
    gain.connect(ac.destination);
    osc.type = "sine";
    osc.frequency.setValueAtTime(880, ac.currentTime);
    osc.frequency.setValueAtTime(660, ac.currentTime + 0.15);
    gain.gain.setValueAtTime(0.15, ac.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.5);
    osc.start(ac.currentTime);
    osc.stop(ac.currentTime + 0.5);
  } catch {}
}

// ── Chat ──────────────────────────────────────────────────────────────
async function onChatSubmit(e) {
  e.preventDefault();
  const input = document.getElementById("chat-input");
  const msg = input.value.trim();
  if (!msg) return;

  appendBubble(msg, "user");
  input.value = "";
  const btn = document.getElementById("chat-send");
  btn.disabled = true;
  btn.textContent = "\u2026";

  try {
    const r = await fetch(`${API}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: msg, language: "en" }),
    });
    const d = await r.json();
    appendBubble(d.response, "daniela");
    speakText(d.response);
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

// ── Voice I/O (Web Speech API) ────────────────────────────────────────
let recognition = null;
let speechSupported = false;

function initVoice() {
  const micBtn = document.getElementById("mic-btn");
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

  if (!SpeechRecognition) {
    micBtn.classList.add("unsupported");
    micBtn.title = "Voice input not supported in this browser";
    return;
  }

  speechSupported = true;
  recognition = new SpeechRecognition();
  recognition.lang = "en-US";
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;

  recognition.onresult = (e) => {
    const transcript = e.results[0][0].transcript;
    document.getElementById("chat-input").value = transcript;
    document.getElementById("chat-form").dispatchEvent(new Event("submit"));
  };
  recognition.onend = () => micBtn.classList.remove("listening");
  recognition.onerror = () => micBtn.classList.remove("listening");

  micBtn.addEventListener("click", () => {
    if (!speechSupported) return;
    if (micBtn.classList.contains("listening")) {
      recognition.stop();
    } else {
      micBtn.classList.add("listening");
      recognition.start();
    }
  });
}

function speakText(text) {
  if (!window.speechSynthesis) return;
  // Limit to first 300 chars for natural speech
  const utterance = new SpeechSynthesisUtterance(text.substring(0, 300));
  utterance.lang = "en-US";
  utterance.rate = 1.0;
  utterance.pitch = 1.0;
  window.speechSynthesis.speak(utterance);
}

// ── Demo Mode ─────────────────────────────────────────────────────────
async function demoAction(action) {
  const status = document.getElementById("demo-status");
  status.textContent = `Running ${action}...`;
  try {
    const r = await fetch(`${API}/demo/${action}`, { method: "POST" });
    const d = await r.json();
    status.textContent = d.message || "Done";
    await refreshAll();
  } catch (e) {
    status.textContent = `Error: ${e.message}`;
  }
}

async function runFullDemo() {
  const btn = document.getElementById("btn-demo-full");
  const status = document.getElementById("demo-status");
  btn.disabled = true;
  btn.classList.add("running");

  const steps = [
    { action: "reset",           label: "Resetting to baseline..." },
    { action: "inject-leak",     label: "Injecting water leak in Building B..." },
    { action: "degrade-chiller", label: "Degrading chiller 2CH-2..." },
  ];

  for (const step of steps) {
    status.textContent = step.label;
    try {
      await fetch(`${API}/demo/${step.action}`, { method: "POST" });
    } catch {}
    await refreshAll();
    await sleep(5000);
  }

  status.textContent = "Demo complete — observe dashboard changes above";
  btn.disabled = false;
  btn.classList.remove("running");
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
