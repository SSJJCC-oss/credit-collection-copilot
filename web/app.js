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

// Send data to the API (POST) and return the JSON answer, or throw the API's error message.
async function postJSON(path, data) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  const body = await response.json();
  if (!response.ok) {
    const detail = Array.isArray(body.detail) ? "Please fill in all required fields." : body.detail;
    throw new Error(detail || `Request to ${path} failed (${response.status})`);
  }
  return body;
}

// ---------------------------------------------------------------- Orders (feature 2)

async function loadOrders() {
  const data = await getJSON("/api/orders/pending");
  const count = decision => data.orders.filter(o => o.decision === decision).length;
  document.getElementById("orders-total").textContent = data.count;
  document.getElementById("orders-approve").textContent = count("APPROVE");
  document.getElementById("orders-review").textContent = count("REVIEW");
  document.getElementById("orders-hold").textContent = count("HOLD");

  // Each order is two rows: the order itself, and a hidden row with its reasons.
  document.getElementById("order-rows").innerHTML = data.orders.map((o, i) => `
    <tr class="clickable" data-index="${i}">
      <td>${escapeHtml(o.order_no)}</td>
      <td>${escapeHtml(o.customer_name)}</td>
      <td>${escapeHtml(o.city)}</td>
      <td>${escapeHtml(o.order_date)}</td>
      <td class="num">${money(o.total)}</td>
      <td><span class="pill ${o.decision}">${o.decision}</span></td>
    </tr>
    <tr class="reasons hidden" id="reasons-${i}">
      <td colspan="6"><ul>${o.reasons.map(r => `<li>${escapeHtml(r.detail)}</li>`).join("")}</ul></td>
    </tr>`).join("");

  document.querySelectorAll("#order-rows tr.clickable").forEach(row =>
    row.addEventListener("click", () => {
      document.getElementById(`reasons-${row.dataset.index}`).classList.toggle("hidden");
      row.classList.toggle("selected");
    }));
}

// ------------------------------------------------------------- Reminders (feature 3)

let selectedDraftId = null;

async function loadDrafts() {
  const status = document.getElementById("draft-filter").value;
  const data = await getJSON(`/api/drafts?status=${status}`);
  const rows = document.getElementById("draft-rows");
  if (data.count === 0) {
    rows.innerHTML = `<tr><td colspan="6" class="hint">No reminders here.</td></tr>`;
    return;
  }
  rows.innerHTML = data.drafts.map(d => `
    <tr class="clickable ${d.id === selectedDraftId ? "selected" : ""}" data-id="${d.id}">
      <td>${d.id}</td>
      <td>${escapeHtml(d.customer_name)}</td>
      <td>${d.language.toUpperCase()}</td>
      <td>${escapeHtml(d.channel)}</td>
      <td class="num">${money(d.amount_due)}</td>
      <td><span class="pill ${d.status}">${d.status}</span></td>
    </tr>`).join("");
  rows.querySelectorAll("tr.clickable").forEach(row =>
    row.addEventListener("click", () => showDraft(Number(row.dataset.id))));
}

async function showDraft(id) {
  selectedDraftId = id;
  const d = await getJSON(`/api/drafts/${id}`);
  const decided = d.status !== "draft"
    ? `<p class="meta">Decided by <b>${escapeHtml(d.decided_by)}</b> at ${escapeHtml(d.decided_at)}: <span class="pill ${d.status}">${d.status}</span>${d.decision_note ? ` · "${escapeHtml(d.decision_note)}"` : ""}</p>`
    : "";
  document.getElementById("draft-view").innerHTML = `
    <p class="meta">#${d.id} · ${escapeHtml(d.customer_name)} · ${escapeHtml(d.channel)} to ${escapeHtml(d.recipient || "-")} ·
       ${d.invoice_refs.length} invoice(s) · ${money(d.amount_due)}</p>
    <p><b>${escapeHtml(d.subject)}</b></p>
    <div class="letter" dir="auto">${escapeHtml(d.body)}</div>
    ${decided}`;
  document.getElementById("decision-box").classList.toggle("hidden", d.status !== "draft");
  document.getElementById("decision-message").textContent = "";
  await loadDrafts();
}

async function createDraft(event) {
  event.preventDefault();                       // stop the browser reloading the page
  const message = document.getElementById("draft-message");
  try {
    const d = await postJSON("/api/drafts", {
      customer_name: document.getElementById("draft-shop").value,
      language: document.getElementById("draft-language").value,
    });
    message.textContent = d.already_existed
      ? `A reminder for ${d.customer_name} is already waiting (#${d.id}).`
      : `Draft #${d.id} created for ${d.customer_name}. It has NOT been sent.`;
    document.getElementById("draft-filter").value = "draft";
    await showDraft(d.id);
  } catch (error) {
    message.textContent = error.message;
  }
}

async function decide(approve) {
  const name = document.getElementById("decided-by").value;
  const message = document.getElementById("decision-message");
  try {
    const d = await postJSON(`/api/drafts/${selectedDraftId}/decision`, {
      approve: approve,
      decided_by: name,
      note: document.getElementById("decision-note").value,
    });
    try { localStorage.setItem("approverName", name); } catch (e) { /* storage blocked: ignore */ }
    document.getElementById("decision-note").value = "";
    await showDraft(d.id);
    message.textContent = d.status === "logged"
      ? "Approved. DRY RUN is on, so it was logged and NOT sent."
      : `Reminder ${d.status}.`;
  } catch (error) {
    message.textContent = error.message;
  }
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
  document.getElementById("draft-form").addEventListener("submit", createDraft);
  document.getElementById("draft-filter").addEventListener("change", loadDrafts);
  document.getElementById("approve-btn").addEventListener("click", () => decide(true));
  document.getElementById("reject-btn").addEventListener("click", () => decide(false));
  try { document.getElementById("decided-by").value = localStorage.getItem("approverName") || ""; } catch (e) { /* ignore */ }
  try {
    await loadStatus();
    await Promise.all([loadBriefing(), loadQuietShops(), loadOrders(), loadDrafts()]);
  } catch (error) {
    const box = document.getElementById("error");
    box.textContent = `Could not load the dashboard: ${error.message}`;
    box.classList.remove("hidden");
  }
}

start();