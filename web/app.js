// app.js - fetches data from the copilot API and fills in the dashboard. No libraries needed.

const BUCKET_LABELS = { "not_due": "Not yet due", "1-30": "1–30 days", "31-60": "31–60 days",
                        "61-90": "61–90 days", "90+": "90+ days" };
let currency = "AED";

// Ask the API for something and return the JSON answer (or show an error).
async function getJSON(path) {
  const response = await fetch(path);
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.detail || `Request to ${path} failed (${response.status})`);
  }
  return body;
}

// 4264940.59 -> "AED 4,264,941"
function money(amount) {
  return `${currency} ${Math.round(amount).toLocaleString("en-US")}`;
}

// Make text safe to put inside HTML (so a shop name can never break the page).
function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
}

async function loadStatus() {
  const health = await getJSON("/api/health");
  currency = health.currency;
  document.getElementById("as-of").textContent = `Data as of ${health.as_of}`;
  const badge = document.getElementById("dry-run");
  badge.textContent = health.dry_run ? "DRY RUN: nothing is sent" : "LIVE: approved reminders are sent";
  badge.classList.toggle("live", !health.dry_run);
}

async function loadBriefing() {
  const b = await getJSON("/api/briefing");
  document.getElementById("total-owed").textContent = money(b.total_owed);
  document.getElementById("total-overdue").textContent = money(b.total_overdue);
  document.getElementById("over-limit").textContent = b.over_limit_count;
  document.getElementById("cheques").textContent =
    `${b.pending_cheques.cheques} · ${money(b.pending_cheques.amount)}`;

  // Ageing bars: each bar's width is its share of the biggest bucket.
  const biggest = Math.max(...Object.values(b.ageing).map(x => x.amount));
  document.getElementById("ageing").innerHTML = Object.entries(b.ageing).map(([bucket, x]) => `
    <div class="bar-row">
      <span>${BUCKET_LABELS[bucket]}</span>
      <div class="bar-track"><div class="bar b-${bucket.replace("+", "")}" style="width:${(x.amount / biggest) * 100}%"></div></div>
      <span class="num">${money(x.amount)} · ${x.invoices} bills</span>
    </div>`).join("");

  document.getElementById("chase-rows").innerHTML = b.top_to_chase.slice(0, 5).map(s => `
    <tr>
      <td>${escapeHtml(s.customer_name)}</td>
      <td>${escapeHtml(s.city)}</td>
      <td class="num">${money(s.overdue)}</td>
      <td class="num">${s.worst_days_overdue} days late</td>
    </tr>`).join("");
}

async function loadQuietShops() {
  const q = await getJSON("/api/quiet-shops?limit=5");
  document.getElementById("quiet-rows").innerHTML = q.shops.map(s => `
    <tr>
      <td>${escapeHtml(s.customer_name)}</td>
      <td class="num">${s.usual_gap_days} day${s.usual_gap_days === 1 ? "" : "s"}</td>
      <td class="num">${s.days_silent} days</td>
      <td class="num">${money(s.monthly_value)}</td>
    </tr>`).join("");
}

// Sidebar: show one section at a time, based on the part of the address after '#'.
function showSection() {
  const name = (location.hash || "#briefing").slice(1);
  document.querySelectorAll(".section").forEach(s => s.classList.toggle("hidden", s.id !== name));
  document.querySelectorAll(".nav-link").forEach(a => a.classList.toggle("active", a.dataset.section === name));
}

async function start() {
  window.addEventListener("hashchange", showSection);
  showSection();
  try {
    await loadStatus();
    await Promise.all([loadBriefing(), loadQuietShops()]);
  } catch (error) {
    const box = document.getElementById("error");
    box.textContent = `Could not load the dashboard: ${error.message}`;
    box.classList.remove("hidden");
  }
}

start();