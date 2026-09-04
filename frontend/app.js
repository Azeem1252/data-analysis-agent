/* ═══════════════════════════════════════════════════════════════
   DataAgent — Application Logic
   ═══════════════════════════════════════════════════════════════ */

const API = "http://localhost:8000";

/* ─── State ─── */
const state = { sessionId: null, datasetInfo: null, messages: [], isQuerying: false };

/* ─── DOM ─── */
const $ = (s) => document.querySelector(s);
const hero            = $("#hero");
const chatArea        = $("#chat-area");
const messagesEl      = $("#messages");
const queryInput      = $("#query-input");
const btnSend         = $("#btn-send");
const fileInput       = $("#file-input");
const uploadArea      = $("#upload-area");
const uploadProgress  = $("#upload-progress");
const progressBar     = $(".progress__bar");
const progressLabel   = $(".progress__label");
const fileBadge       = $("#file-badge");
const fileBadgeName   = $("#file-badge-name");
const btnReset        = $("#btn-reset");
const datasetSummary  = $("#dataset-summary");
const statRows        = $("#stat-rows");
const statCols        = $("#stat-cols");
const dtypeList       = $("#dtype-list");
const systemInfo      = $("#system-info");
const previewToggle   = $("#btn-preview-toggle");
const previewWrapper  = $("#preview-wrapper");
const previewTable    = $("#preview-table");
const sidebarToggle   = $("#sidebar-toggle");
const sidebar         = $("#sidebar");

/* ═══════════════════════════════════════════════════════════════
   Toast
   ═══════════════════════════════════════════════════════════════ */
function showToast(msg, type = "error", ms = 4500) {
  let t = document.querySelector(".toast");
  if (!t) { t = document.createElement("div"); t.className = "toast"; document.body.appendChild(t); }
  t.textContent = msg;
  t.className = `toast toast--${type}`;
  requestAnimationFrame(() => t.classList.add("toast--visible"));
  clearTimeout(t._t);
  t._t = setTimeout(() => t.classList.remove("toast--visible"), ms);
}

/* ═══════════════════════════════════════════════════════════════
   Health Check
   ═══════════════════════════════════════════════════════════════ */
async function checkHealth() {
  try {
    const r = await fetch(`${API}/health`);
    const d = await r.json();
    systemInfo.innerHTML = `
      <div class="sys-info__row"><span class="sys-dot sys-dot--on"></span><span>Online</span></div>
      <div class="sys-info__row"><span>Provider: <strong>${esc(d.llm_provider)}</strong></span></div>
      <div class="sys-info__row"><span>Model: <strong>${esc(d.model_name)}</strong></span></div>
      <div class="sys-info__row"><span>Sandbox: <strong>${d.use_docker_sandbox ? "Docker" : "Local"}</strong></span></div>
    `;
  } catch {
    systemInfo.innerHTML = `<div class="sys-info__row"><span class="sys-dot sys-dot--off"></span><span>Backend offline</span></div>`;
  }
}

/* ═══════════════════════════════════════════════════════════════
   Upload
   ═══════════════════════════════════════════════════════════════ */
async function uploadFile(file) {
  if (!file) return;
  const ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase();
  if (![".csv", ".xlsx", ".xls"].includes(ext)) { showToast("Unsupported format — upload .csv, .xlsx, or .xls"); return; }
  if (file.size > 25 * 1024 * 1024) { showToast("File exceeds 25 MB limit."); return; }

  uploadArea.classList.add("hidden");
  uploadProgress.classList.remove("hidden");
  progressBar.style.width = "0%";
  progressLabel.textContent = "Uploading…";

  let pct = 0;
  const tick = setInterval(() => { pct = Math.min(pct + Math.random() * 12, 88); progressBar.style.width = pct + "%"; }, 220);

  try {
    const form = new FormData();
    form.append("file", file, file.name);
    const res = await fetch(`${API}/upload`, { method: "POST", body: form });
    clearInterval(tick);
    if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || `Upload failed (${res.status})`); }
    progressBar.style.width = "100%";
    progressLabel.textContent = "Profiling…";
    const data = await res.json();
    state.sessionId = data.session_id;
    state.datasetInfo = data;
    state.messages = [];
    setTimeout(() => activateChat(file.name, data), 350);
  } catch (e) {
    clearInterval(tick);
    uploadProgress.classList.add("hidden");
    uploadArea.classList.remove("hidden");
    showToast(e.message);
  }
}

function activateChat(name, data) {
  uploadProgress.classList.add("hidden");
  fileBadge.classList.remove("hidden");
  fileBadgeName.textContent = name;

  statRows.textContent = data.n_rows.toLocaleString();
  statCols.textContent = data.columns.length;
  dtypeList.innerHTML = "";
  for (const [col, dtype] of Object.entries(data.dtypes)) {
    const li = document.createElement("li");
    li.innerHTML = `<span class="schema-list__col">${esc(col)}</span><span class="schema-list__type">${esc(dtype)}</span>`;
    dtypeList.appendChild(li);
  }
  datasetSummary.classList.remove("hidden");
  buildPreview(data.columns, data.preview);

  hero.classList.add("hidden");
  chatArea.classList.remove("hidden");
  messagesEl.innerHTML = "";
  queryInput.focus();
  showToast(`Loaded ${name} — ${data.n_rows.toLocaleString()} rows`, "success");
}

/* ═══════════════════════════════════════════════════════════════
   Preview Table
   ═══════════════════════════════════════════════════════════════ */
function buildPreview(cols, rows) {
  if (!rows || !rows.length) return;
  let h = "<table><thead><tr>";
  for (const c of cols) h += `<th>${esc(c)}</th>`;
  h += "</tr></thead><tbody>";
  for (const row of rows) {
    h += "<tr>";
    for (const c of cols) { const v = row[c] ?? ""; h += `<td title="${esc(String(v))}">${esc(String(v))}</td>`; }
    h += "</tr>";
  }
  h += "</tbody></table>";
  previewTable.innerHTML = h;
}

/* ═══════════════════════════════════════════════════════════════
   Reset
   ═══════════════════════════════════════════════════════════════ */
async function resetSession() {
  if (state.sessionId) { try { await fetch(`${API}/session/${state.sessionId}`, { method: "DELETE" }); } catch {} }
  state.sessionId = null; state.datasetInfo = null; state.messages = [];
  fileBadge.classList.add("hidden"); datasetSummary.classList.add("hidden");
  uploadArea.classList.remove("hidden"); chatArea.classList.add("hidden");
  hero.classList.remove("hidden"); messagesEl.innerHTML = "";
  fileInput.value = ""; previewWrapper.classList.add("hidden");
}

/* ═══════════════════════════════════════════════════════════════
   Query
   ═══════════════════════════════════════════════════════════════ */
async function sendQuery() {
  const q = queryInput.value.trim();
  if (!q || state.isQuerying) return;
  if (!state.sessionId) { showToast("Please upload a spreadsheet first."); return; }
  state.isQuerying = true; btnSend.disabled = true;
  queryInput.value = ""; autoResize();
  appendMsg("user", q);
  const thinkEl = appendThinking();

  try {
    const res = await fetch(`${API}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: state.sessionId, question: q }),
    });
    thinkEl.remove();
    if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || `Query failed (${res.status})`); }
    const data = await res.json();
    appendMsg("agent", data.answer, { figureJson: data.figure_json, codeRun: data.code_run, attempts: data.attempts });
  } catch (e) {
    thinkEl.remove();
    appendMsg("agent", `⚠️ ${e.message}`);
    showToast(e.message);
  } finally {
    state.isQuerying = false;
    btnSend.disabled = !queryInput.value.trim();
  }
}

/* ═══════════════════════════════════════════════════════════════
   Message Rendering
   ═══════════════════════════════════════════════════════════════ */
function appendMsg(role, text, meta = {}) {
  const el = document.createElement("div");
  el.className = `msg msg--${role}`;

  const label = document.createElement("span");
  label.className = "msg__label";
  label.textContent = role === "user" ? "You" : "Agent";
  el.appendChild(label);

  const body = document.createElement("div");
  body.className = "msg__body";
  body.innerHTML = renderMd(text);

  /* Chart */
  if (meta.figureJson) {
    const chartDiv = document.createElement("div");
    chartDiv.className = "msg__chart";
    const id = "c" + Date.now() + Math.random().toString(36).slice(2, 5);
    chartDiv.id = id;
    body.appendChild(chartDiv);
    try {
      const fig = typeof meta.figureJson === "string" ? JSON.parse(meta.figureJson) : meta.figureJson;
      const L = fig.layout || {};
      L.paper_bgcolor = "rgba(0,0,0,0)";
      L.plot_bgcolor  = "rgba(11,18,33,0.6)";
      L.font = { ...(L.font || {}), color: "#94A3B8", family: "Plus Jakarta Sans, sans-serif" };
      L.margin = { t: 40, r: 20, b: 44, l: 52, ...(L.margin || {}) };
      L.colorway = L.colorway || ["#10B981","#3B82F6","#F59E0B","#EF4444","#8B5CF6","#EC4899","#14B8A6"];
      L.autosize = true;
      for (const ax of ["xaxis","yaxis"]) {
        L[ax] = { ...(L[ax] || {}), gridcolor: "rgba(148,163,184,0.06)", zerolinecolor: "rgba(148,163,184,0.08)" };
      }
      fig.layout = L;
      requestAnimationFrame(() => {
        Plotly.newPlot(id, fig.data, fig.layout, {
          responsive: true, displayModeBar: true, displaylogo: false,
          modeBarButtonsToRemove: ["lasso2d","select2d"],
        }).then(() => window.dispatchEvent(new Event("resize")));
      });
    } catch (err) {
      chartDiv.innerHTML = `<p style="color:var(--error);padding:14px;font-size:.8rem;">Chart render error: ${esc(err.message)}</p>`;
    }
  }

  /* Code toggle */
  if (meta.codeRun) {
    const tog = document.createElement("div");
    tog.className = "msg__code-toggle";
    tog.textContent = "↳ View executed code";
    const blk = document.createElement("pre");
    blk.className = "msg__code-block hidden";
    blk.textContent = meta.codeRun;
    tog.addEventListener("click", () => {
      const h = blk.classList.toggle("hidden");
      tog.textContent = h ? "↳ View executed code" : "↳ Hide code";
    });
    body.appendChild(tog);
    body.appendChild(blk);
  }

  /* Badge */
  if (meta.attempts) {
    const b = document.createElement("span");
    b.className = meta.attempts === 1 ? "msg__badge msg__badge--ok" : "msg__badge msg__badge--corrected";
    b.textContent = meta.attempts === 1 ? "✓ 1 attempt" : `⟳ ${meta.attempts} attempts — self-corrected`;
    body.appendChild(b);
  }

  el.appendChild(body);
  messagesEl.appendChild(el);
  scrollBottom();
  state.messages.push({ role, text, meta });
}

function appendThinking() {
  const el = document.createElement("div");
  el.className = "msg msg--agent";
  el.innerHTML = `
    <span class="msg__label">Agent</span>
    <div class="msg__body">
      <div class="thinking">
        <span class="thinking__dot"></span>
        <span class="thinking__dot"></span>
        <span class="thinking__dot"></span>
        <span class="thinking__text">Analysing…</span>
      </div>
    </div>`;
  messagesEl.appendChild(el);
  scrollBottom();
  return el;
}

function scrollBottom() { requestAnimationFrame(() => { messagesEl.scrollTop = messagesEl.scrollHeight; }); }

/* ═══════════════════════════════════════════════════════════════
   Helpers
   ═══════════════════════════════════════════════════════════════ */
function renderMd(t) {
  if (!t) return "";
  if (typeof marked !== "undefined" && marked.parse) {
    try {
      marked.setOptions({
        breaks: true,
        gfm: true
      });
      return marked.parse(t);
    } catch (e) {
      console.warn("Markdown parse error:", e);
    }
  }
  let h = esc(t);
  h = h.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  h = h.replace(/`([^`]+)`/g, '<code>$1</code>');
  h = h.replace(/\n/g, "<br>");
  return h;
}

function esc(s) { const d = document.createElement("div"); d.textContent = s; return d.innerHTML; }

function autoResize() {
  queryInput.style.height = "auto";
  queryInput.style.height = Math.min(queryInput.scrollHeight, 140) + "px";
}

/* ═══════════════════════════════════════════════════════════════
   Events
   ═══════════════════════════════════════════════════════════════ */
fileInput.addEventListener("change", (e) => {
  if (e.target.files[0]) {
    const f = e.target.files[0];
    fileInput.value = "";
    uploadFile(f);
  }
});

uploadArea.addEventListener("dragover", (e) => { e.preventDefault(); uploadArea.classList.add("dragover"); });
uploadArea.addEventListener("dragleave", () => uploadArea.classList.remove("dragover"));
uploadArea.addEventListener("drop", (e) => {
  e.preventDefault(); uploadArea.classList.remove("dragover");
  if (e.dataTransfer.files[0]) { fileInput.files = e.dataTransfer.files; uploadFile(e.dataTransfer.files[0]); }
});
document.body.addEventListener("dragover", (e) => e.preventDefault());
document.body.addEventListener("drop", (e) => {
  e.preventDefault();
  if (e.dataTransfer.files[0] && !state.sessionId) { fileInput.files = e.dataTransfer.files; uploadFile(e.dataTransfer.files[0]); }
});

btnReset.addEventListener("click", resetSession);
btnSend.addEventListener("click", sendQuery);
queryInput.addEventListener("input", () => { autoResize(); btnSend.disabled = !queryInput.value.trim() || state.isQuerying; });
queryInput.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendQuery(); } });

previewToggle.addEventListener("click", () => {
  const h = previewWrapper.classList.toggle("hidden");
  previewToggle.querySelector("span").textContent = h ? "Preview data" : "Hide preview";
});

sidebarToggle.addEventListener("click", () => sidebar.classList.toggle("open"));
document.addEventListener("click", (e) => {
  if (sidebar.classList.contains("open") && !sidebar.contains(e.target) && !sidebarToggle.contains(e.target))
    sidebar.classList.remove("open");
});

/* ─── Init ─── */
checkHealth();
setInterval(checkHealth, 30000);
