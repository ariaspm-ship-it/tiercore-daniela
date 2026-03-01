// DANIELA v0.5 — Proactive AI Feed
// No charts, no tables. Just Daniela talking.

const API = "http://localhost:8000/api/v1";
const POLL_MS = 30_000;

let knownAlertIds = new Set();
let firstLoad = true;

// ── Boot ─────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  tickClock();
  setInterval(tickClock, 1000);
  fetchHealth();
  pollProactive();
  setInterval(pollProactive, POLL_MS);
  document.getElementById("input-form").addEventListener("submit", onSubmit);
  initVoice();
});

// ── Clock ────────────────────────────────────────────────────────────
function tickClock() {
  document.getElementById("clock").textContent =
    new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

// ── Health pills ─────────────────────────────────────────────────────
async function fetchHealth() {
  try {
    const d = await (await fetch(`${API}/health`)).json();
    const c = d.checks || {};
    setPill("pill-sim", c.simulator_running);
    setPill("pill-db",  c.db_connected);
    setPill("pill-key", c.api_key_configured);
  } catch {
    setPill("pill-sim", false);
    setPill("pill-db", false);
    setPill("pill-key", false);
  }
}
function setPill(id, ok) {
  const el = document.getElementById(id);
  el.classList.toggle("ok", !!ok);
  el.classList.toggle("fail", !ok);
}

// ── Poll proactive alerts ────────────────────────────────────────────
async function pollProactive() {
  try {
    const d = await (await fetch(`${API}/proactive`)).json();
    const alerts = d.alerts || [];

    for (const alert of alerts) {
      if (knownAlertIds.has(alert.id)) continue;
      knownAlertIds.add(alert.id);
      hideEmptyState();
      appendAlert(alert);

      // Speak critical/high alerts aloud
      if (alert.severity === "CRITICAL" || alert.severity === "HIGH") {
        playAlertSound();
        speakText(alert.message);
      }
    }

    // On first load with no alerts, try to show the morning briefing
    if (firstLoad && alerts.length === 0) {
      firstLoad = false;
      await loadBriefing();
    }
    firstLoad = false;
  } catch {
    // Silently retry on next poll
  }
}

// ── Load morning briefing on empty feed ──────────────────────────────
async function loadBriefing() {
  try {
    const d = await (await fetch(`${API}/briefing/latest`)).json();
    if (d.briefing) {
      hideEmptyState();
      appendFeedMessage({
        severity: "INFO",
        equipment: "Morning Briefing",
        message: d.briefing,
        timestamp: d.timestamp,
        actions: [],
      });
    }
  } catch {}
}

// ── Append alert to feed ─────────────────────────────────────────────
function appendAlert(alert) {
  const actions = extractActions(alert.message);

  appendFeedMessage({
    severity: alert.severity,
    equipment: alert.equipment,
    message: alert.message,
    timestamp: alert.timestamp,
    alertId: alert.id,
    actions: actions,
  });
}

function extractActions(message) {
  // Parse "Should I..." or "Shall I..." patterns into action buttons
  const actions = [];
  const patterns = [
    /Should I (.+?\?)/gi,
    /Shall I (.+?\?)/gi,
  ];
  for (const pat of patterns) {
    let match;
    while ((match = pat.exec(message)) !== null) {
      const label = match[1].replace(/\?$/, "").trim();
      if (label.length > 5 && label.length < 80) {
        actions.push(label.charAt(0).toUpperCase() + label.slice(1));
      }
    }
  }
  return actions;
}

function appendFeedMessage({ severity, equipment, message, timestamp, alertId, actions }) {
  const feed = document.getElementById("feed");
  const div = document.createElement("div");
  div.className = `feed-msg severity-${severity}`;

  const time = timestamp
    ? new Date(timestamp).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })
    : new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });

  let html = `
    <div class="msg-meta">
      <span class="msg-severity ${severity}">${severity}</span>
      <span class="msg-equipment">${escapeHtml(equipment)}</span>
      <span>${time}</span>
    </div>
    <div class="msg-body">${escapeHtml(message)}</div>
  `;

  if (actions && actions.length > 0) {
    html += `<div class="msg-actions">`;
    for (const action of actions) {
      const btnId = `act-${(alertId || "msg")}-${Math.random().toString(36).slice(2, 6)}`;
      html += `<button class="action-btn" id="${btnId}" onclick="confirmAction('${btnId}', '${alertId || ""}')">${escapeHtml(action)}</button>`;
    }
    html += `</div>`;
  }

  div.innerHTML = html;
  feed.appendChild(div);
  feed.scrollTop = feed.scrollHeight;
}

// ── Confirm action button ────────────────────────────────────────────
async function confirmAction(btnId, alertId) {
  const btn = document.getElementById(btnId);
  if (!btn || btn.classList.contains("confirmed")) return;

  btn.classList.add("confirmed");
  btn.textContent = "Confirmed";

  // Acknowledge the alert
  if (alertId) {
    try {
      await fetch(`${API}/proactive/${alertId}/acknowledge`, { method: "POST" });
    } catch {}
  }

  // Add Daniela's confirmation to feed
  appendDanielaMessage("Understood. I'll proceed with that action and update you on progress.");
}

// ── User chat ────────────────────────────────────────────────────────
async function onSubmit(e) {
  e.preventDefault();
  const input = document.getElementById("user-input");
  const msg = input.value.trim();
  if (!msg) return;

  hideEmptyState();
  appendUserMessage(msg);
  input.value = "";

  const btn = document.getElementById("send-btn");
  btn.disabled = true;

  try {
    const r = await fetch(`${API}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: msg, language: "en" }),
    });
    const d = await r.json();
    appendDanielaMessage(d.response);
    speakText(d.response);
  } catch {
    appendDanielaMessage("Connection lost. Retrying on next cycle.");
  } finally {
    btn.disabled = false;
  }
}

function appendUserMessage(text) {
  const feed = document.getElementById("feed");
  const div = document.createElement("div");
  div.className = "feed-msg from-user";
  const time = new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
  div.innerHTML = `
    <div class="msg-meta"><span>You</span><span>${time}</span></div>
    <div class="msg-body">${escapeHtml(text)}</div>
  `;
  feed.appendChild(div);
  feed.scrollTop = feed.scrollHeight;
}

function appendDanielaMessage(text) {
  const feed = document.getElementById("feed");
  const div = document.createElement("div");
  div.className = "feed-msg from-daniela";
  const time = new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
  const actions = extractActions(text);

  let html = `
    <div class="msg-meta">
      <span class="msg-equipment">Daniela</span>
      <span>${time}</span>
    </div>
    <div class="msg-body">${escapeHtml(text)}</div>
  `;

  if (actions.length > 0) {
    html += `<div class="msg-actions">`;
    for (const action of actions) {
      const btnId = `act-resp-${Math.random().toString(36).slice(2, 6)}`;
      html += `<button class="action-btn" id="${btnId}" onclick="confirmAction('${btnId}', '')">${escapeHtml(action)}</button>`;
    }
    html += `</div>`;
  }

  div.innerHTML = html;
  feed.appendChild(div);
  feed.scrollTop = feed.scrollHeight;
}

// ── Helpers ──────────────────────────────────────────────────────────
function hideEmptyState() {
  const el = document.getElementById("feed-empty");
  if (el) el.remove();
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// ── Alert sound ──────────────────────────────────────────────────────
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
    gain.gain.setValueAtTime(0.12, ac.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.5);
    osc.start(ac.currentTime);
    osc.stop(ac.currentTime + 0.5);
  } catch {}
}

// ── Voice I/O ────────────────────────────────────────────────────────
let recognition = null;

function initVoice() {
  const micBtn = document.getElementById("mic-btn");
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;

  if (!SR) {
    micBtn.classList.add("unsupported");
    micBtn.title = "Voice input not supported";
    return;
  }

  recognition = new SR();
  recognition.lang = "en-US";
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;

  recognition.onresult = (e) => {
    const transcript = e.results[0][0].transcript;
    document.getElementById("user-input").value = transcript;
    document.getElementById("input-form").dispatchEvent(new Event("submit"));
  };
  recognition.onend = () => micBtn.classList.remove("listening");
  recognition.onerror = () => micBtn.classList.remove("listening");

  micBtn.addEventListener("click", () => {
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
  const utterance = new SpeechSynthesisUtterance(text.substring(0, 400));
  utterance.lang = "en-US";
  utterance.rate = 1.0;
  utterance.pitch = 1.0;
  window.speechSynthesis.speak(utterance);
}
