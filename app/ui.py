"""
app/ui.py — Single-file dashboard for InboxPilot, served at "/".

A three-pane mail-client layout: inbox (real files from /samples, plus a
"write your own" draft), the open message, and the agent's review with the
proposed change, its steps, and the drafted reply.
"""

HTML_CONTENT = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>InboxPilot</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --paper: #f6f4ef;
    --panel: #fffdf9;
    --line: #e4dfd5;
    --line-strong: #d3ccbe;
    --ink: #1d1c1a;
    --ink-2: #4a4741;
    --ink-3: #8a857b;
    --accent: #1f5c46;
    --accent-ink: #f3f8f5;
    --accent-soft: #e6efe9;
    --warn: #8a4b0f;
    --warn-soft: #fbf0e1;
    --danger: #9b2c22;
    --danger-soft: #f8e9e6;
    --info: #2f4a7a;
    --info-soft: #e8edf6;
    --mono: "IBM Plex Mono", ui-monospace, Menlo, monospace;
    --sans: "IBM Plex Sans", -apple-system, "Segoe UI", sans-serif;
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; }
  body {
    margin: 0;
    background: var(--paper);
    color: var(--ink);
    font: 14px/1.5 var(--sans);
    -webkit-font-smoothing: antialiased;
  }
  button, input, textarea { font: inherit; color: inherit; }
  kbd {
    font: 11px var(--mono);
    padding: 1px 5px;
    border: 1px solid var(--line-strong);
    border-bottom-width: 2px;
    border-radius: 4px;
    color: var(--ink-3);
    background: var(--panel);
  }

  /* ── Top bar ─────────────────────────────────────────── */
  .topbar {
    height: 52px;
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 0 20px;
    border-bottom: 1px solid var(--line);
    background: var(--panel);
  }
  .brand { font-weight: 600; letter-spacing: -0.01em; }
  .brand small { font-weight: 400; color: var(--ink-3); margin-left: 8px; }
  .topbar .spacer { flex: 1; }
  .key-field {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: var(--ink-3);
  }
  .key-field input {
    width: 220px;
    padding: 6px 9px;
    border: 1px solid var(--line-strong);
    border-radius: 6px;
    background: #fff;
    font: 12px var(--mono);
  }
  .key-field input:focus { outline: 2px solid var(--accent-soft); border-color: var(--accent); }
  .key-state { width: 7px; height: 7px; border-radius: 50%; background: var(--line-strong); }
  .key-state.ok { background: var(--accent); }
  .demo-note { display: none; font-size: 12px; color: var(--ink-3); }
  .demo-note b { color: var(--accent); font-weight: 600; }
  body.demo-public .demo-note { display: block; }
  body.demo-public .key-field { display: none; }

  .error-banner {
    display: none;
    padding: 9px 20px;
    border-bottom: 1px solid #ecc9c3;
    background: var(--danger-soft);
    color: var(--danger);
    font-size: 13px;
  }
  .error-banner.visible { display: block; }

  /* ── Layout ──────────────────────────────────────────── */
  .app {
    display: grid;
    grid-template-columns: 300px minmax(0, 1fr) 400px;
    height: calc(100vh - 52px);
  }
  .app.has-error { height: calc(100vh - 52px - 38px); }
  .pane { overflow-y: auto; min-width: 0; }
  .pane + .pane { border-left: 1px solid var(--line); }
  .pane-head {
    position: sticky;
    top: 0;
    z-index: 1;
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    padding: 14px 18px 10px;
    background: var(--paper);
    border-bottom: 1px solid var(--line);
    font-size: 12px;
    color: var(--ink-3);
  }
  .pane-head h2 { margin: 0; font-size: 13px; font-weight: 600; color: var(--ink); }

  /* ── Inbox list ──────────────────────────────────────── */
  .msg {
    display: block;
    width: 100%;
    text-align: left;
    padding: 12px 18px;
    border: 0;
    border-bottom: 1px solid var(--line);
    background: transparent;
    cursor: pointer;
  }
  .msg:hover { background: #fbf9f4; }
  .msg.active { background: var(--panel); box-shadow: inset 3px 0 0 var(--ink); }
  .msg-top { display: flex; justify-content: space-between; gap: 8px; font-size: 13px; }
  .msg-from { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .msg-date { color: var(--ink-3); font-size: 12px; white-space: nowrap; }
  .msg-subject { margin-top: 2px; font-size: 13px; color: var(--ink-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .msg-snippet { margin-top: 2px; font-size: 12px; color: var(--ink-3); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .msg-tag {
    display: inline-block;
    margin-top: 6px;
    font: 11px var(--mono);
    color: var(--ink-3);
  }
  .msg-tag.done { color: var(--accent); }
  .msg-tag.waiting { color: var(--warn); }

  /* ── Reading pane ────────────────────────────────────── */
  .reader { background: var(--panel); }
  .reader-inner { max-width: 680px; padding: 28px 36px 40px; }
  .reader h1 { margin: 0 0 14px; font-size: 20px; font-weight: 600; letter-spacing: -0.01em; line-height: 1.3; }
  .headers { display: grid; grid-template-columns: 56px 1fr; gap: 2px 10px; font-size: 13px; color: var(--ink-2); padding-bottom: 16px; border-bottom: 1px solid var(--line); }
  .headers dt { color: var(--ink-3); }
  .headers dd { margin: 0; overflow-wrap: anywhere; }
  .body-text {
    width: 100%;
    margin: 18px 0 0;
    padding: 0;
    border: 0;
    background: transparent;
    font: 14.5px/1.65 var(--sans);
    white-space: pre-wrap;
    color: var(--ink);
    resize: vertical;
    min-height: 260px;
  }
  textarea.body-text[readonly] { resize: none; cursor: default; }
  .body-text:focus { outline: none; }
  textarea.body-text.editable { padding: 12px; border: 1px dashed var(--line-strong); border-radius: 6px; background: #fff; }
  .reader-actions { display: flex; align-items: center; gap: 12px; margin-top: 22px; padding-top: 16px; border-top: 1px solid var(--line); }
  .hint { font-size: 12px; color: var(--ink-3); }

  .btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 8px 14px;
    border: 1px solid var(--line-strong);
    border-radius: 6px;
    background: #fff;
    cursor: pointer;
    font-weight: 500;
    white-space: nowrap;
  }
  .btn:hover:not(:disabled) { border-color: var(--ink-3); }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-primary { background: var(--ink); border-color: var(--ink); color: #fff; }
  .btn-primary:hover:not(:disabled) { background: #000; }
  .btn-approve { background: var(--accent); border-color: var(--accent); color: var(--accent-ink); }
  .btn-approve:hover:not(:disabled) { background: #174a38; }
  .btn-reject { color: var(--danger); }
  .btn kbd { border-color: currentColor; color: inherit; background: transparent; opacity: 0.7; }

  /* ── Review pane ─────────────────────────────────────── */
  .review-inner { padding: 18px; display: flex; flex-direction: column; gap: 18px; }
  .empty { padding: 40px 18px; color: var(--ink-3); font-size: 13px; line-height: 1.6; }
  .empty strong { color: var(--ink-2); font-weight: 500; }

  .status {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 3px 9px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 500;
  }
  .status::before { content: ""; width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
  .status.awaiting { background: var(--warn-soft); color: var(--warn); }
  .status.completed { background: var(--accent-soft); color: var(--accent); }
  .status.rejected, .status.failed { background: var(--danger-soft); color: var(--danger); }
  .status.review { background: var(--info-soft); color: var(--info); }

  .block h3 { margin: 0 0 8px; font-size: 11px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: var(--ink-3); }
  .change {
    padding: 14px;
    border: 1px solid var(--line-strong);
    border-radius: 8px;
    background: #fff;
  }
  .change-summary { font-size: 15px; font-weight: 500; line-height: 1.4; }
  .change-meta { margin-top: 4px; font-size: 12px; color: var(--ink-3); }
  .change details { margin-top: 10px; font-size: 12px; color: var(--ink-3); }
  .change summary { cursor: pointer; }
  .change pre {
    margin: 8px 0 0;
    padding: 10px;
    border-radius: 6px;
    background: var(--paper);
    font: 12px/1.5 var(--mono);
    color: var(--ink-2);
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
  .decision { display: flex; gap: 8px; margin-top: 12px; }
  .decision .btn { flex: 1; justify-content: center; }
  .outcome { margin-top: 12px; font-size: 13px; color: var(--ink-2); }

  .fields { display: grid; grid-template-columns: 120px 1fr; gap: 4px 12px; margin: 0; font-size: 13px; }
  .fields dt { color: var(--ink-3); }
  .fields dd { margin: 0; font-family: var(--mono); font-size: 12.5px; overflow-wrap: anywhere; }

  .steps { list-style: none; margin: 0; padding: 0; font-size: 13px; }
  .steps li { display: flex; gap: 10px; padding: 3px 0; color: var(--ink-2); }
  .steps li::before { content: "✓"; color: var(--accent); font-weight: 600; width: 12px; }
  .steps code { font: 11.5px var(--mono); color: var(--ink-3); margin-left: auto; }

  .draft-box {
    padding: 14px;
    border: 1px solid var(--line);
    border-radius: 8px;
    background: #fff;
  }
  .draft-head { font-size: 12px; color: var(--ink-3); margin-bottom: 10px; }
  .draft-head div { overflow-wrap: anywhere; }
  .draft-body { white-space: pre-wrap; font-size: 13.5px; line-height: 1.6; }
  .draft-actions { display: flex; justify-content: flex-end; margin-top: 10px; }
  .btn-small { padding: 4px 10px; font-size: 12px; }

  .spinner { width: 12px; height: 12px; border: 2px solid currentColor; border-right-color: transparent; border-radius: 50%; animation: spin 0.7s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }

  @media (max-width: 1100px) {
    .app { grid-template-columns: 260px minmax(0, 1fr); }
    .review { grid-column: 1 / -1; border-left: 0 !important; border-top: 1px solid var(--line); }
    .app, .app.has-error { height: auto; }
  }
  @media (max-width: 720px) {
    .app { grid-template-columns: 1fr; }
    .pane + .pane { border-left: 0; border-top: 1px solid var(--line); }
    .inbox { max-height: 40vh; }
    .reader-inner { padding: 20px 16px 28px; }
    .key-field span { display: none; }
    .key-field input { width: 150px; }
    .brand small { display: none; }
  }
</style>
</head>
<body>

<header class="topbar">
  <div class="brand">InboxPilot<small>ops inbox · every write needs a human yes</small></div>
  <div class="spacer"></div>
  <div class="demo-note"><b>Public demo</b> · approvals change a sandbox copy of the sample data, never a real database</div>
  <label class="key-field" title="Agent endpoints require the X-Demo-Token header">
    <span class="key-state" id="keyState"></span>
    <span>Access key</span>
    <input type="password" id="demoToken" placeholder="paste DEMO_TOKEN" autocomplete="off" spellcheck="false">
  </label>
</header>

<div id="errorBanner" class="error-banner" role="alert"></div>

<main class="app" id="app">
  <section class="pane inbox" aria-label="Inbox">
    <div class="pane-head"><h2>Inbox</h2><span id="inboxCount"></span></div>
    <div id="inboxList"></div>
  </section>

  <section class="pane reader" aria-label="Message">
    <div class="reader-inner">
      <h1 id="msgSubject">Loading…</h1>
      <dl class="headers">
        <dt>From</dt><dd id="msgFrom"></dd>
        <dt>To</dt><dd id="msgTo"></dd>
        <dt>Date</dt><dd id="msgDate"></dd>
      </dl>
      <textarea id="msgBody" class="body-text" readonly></textarea>
      <div class="reader-actions">
        <button class="btn btn-primary" id="processBtn" onclick="executeProcess()">Run agent <kbd>⌘↵</kbd></button>
        <span class="hint" id="runHint">Reads the email, checks it against company records, and proposes a change for you to approve.</span>
      </div>
    </div>
  </section>

  <section class="pane review" aria-label="Agent review">
    <div class="pane-head"><h2>Agent review</h2><span id="statusPill" class="status" style="display:none"><span id="statusPillText"></span></span></div>
    <div id="reviewEmpty" class="empty">
      Nothing reviewed yet.<br><br>
      Pick a message and press <strong>Run agent</strong>. Nothing is written until you approve it here.
    </div>
    <div id="reviewBody" class="review-inner" style="display:none">
      <div class="block" id="changeBlock">
        <h3>Proposed change</h3>
        <div class="change">
          <div class="change-summary" id="changeSummary"></div>
          <div class="change-meta" id="changeMeta"></div>
          <details id="changeRaw">
            <summary>Database operation</summary>
            <pre id="changeOp"></pre>
          </details>
          <div class="decision" id="decisionRow">
            <button id="approveBtn" class="btn btn-approve" onclick="handleDecision('approve')" disabled>Approve <kbd>A</kbd></button>
            <button id="rejectBtn" class="btn btn-reject" onclick="handleDecision('reject')" disabled>Reject <kbd>R</kbd></button>
          </div>
          <div class="outcome" id="outcome"></div>
        </div>
      </div>

      <div class="block" id="fieldsBlock">
        <h3>What it read</h3>
        <dl class="fields" id="fieldList"></dl>
      </div>

      <div class="block" id="draftBlock">
        <h3>Reply draft</h3>
        <div class="draft-box">
          <div class="draft-head"><div id="draftTo"></div><div id="draftSubject"></div></div>
          <div class="draft-body" id="draftBody"></div>
          <div class="draft-actions"><button class="btn btn-small" onclick="copyDraft(this)">Copy reply</button></div>
        </div>
      </div>

      <div class="block">
        <h3>Steps</h3>
        <ol class="steps" id="stepList"></ol>
      </div>
    </div>
  </section>
</main>

<script>
  // ── State ────────────────────────────────────────────────
  const FALLBACK_SAMPLES = [
    { filename: "leave_request_01.eml", content: "From: aarav.sharma@acme.dev\nTo: hr@acme.dev\nDate: Mon, 14 Oct 2024 09:30:00 +0000\nSubject: Casual Leave Application - Aarav Sharma (EMP001)\n\nHi HR Team,\n\nI would like to apply for 2 days of casual leave from 2024-10-24 to 2024-10-25 due to a family commitment.\nMy employee ID is EMP001.\n\nBest regards,\nAarav Sharma" },
  ];
  const COMPOSE = {
    id: "compose", from: "you@example.com", to: "ops@acme.dev", date: "now",
    subject: "Write your own", snippet: "Paste or type any email to test the agent",
    body: "Hi team,\n\nI'd like to take sick leave on 2024-11-12. My employee ID is EMP002.\n\nThanks,\nPriya",
  };
  let messages = [];
  let demoPublic = false;
  let current = null;
  let currentRunId = null;
  const runsByMessage = {};

  const STEP_LABELS = {
    read_email: "Parsed the email",
    read_pdf: "Extracted text from the PDF",
    extract_fields: "Pulled out the key fields",
    lookup_record: "Looked up the matching record",
    draft_reply: "Drafted a reply",
    apply_update: "Applied the approved change",
  };
  const FIELD_LABELS = {
    document_type: "Type", employee_name: "Employee", employee_id: "Employee ID",
    leave_type: "Leave type", leave_start: "From", leave_end: "To",
    invoice_number: "Invoice", vendor_name: "Vendor", amount: "Amount", due_date: "Due",
    ticket_id: "Ticket", priority: "Priority", issue_summary: "Issue",
  };
  const TYPE_LABELS = { leave_request: "Leave request", invoice: "Invoice", support_ticket: "Support ticket", unknown: "Unclassified" };

  const $ = (id) => document.getElementById(id);

  // ── Access key (kept for this tab only) ─────────────────
  function loadKey() {
    try { $("demoToken").value = sessionStorage.getItem("inboxpilot.key") || ""; } catch (_) {}
    updateKeyState();
  }
  function updateKeyState() {
    const has = $("demoToken").value.trim().length > 0;
    $("keyState").classList.toggle("ok", has);
    try {
      if (has) sessionStorage.setItem("inboxpilot.key", $("demoToken").value.trim());
      else sessionStorage.removeItem("inboxpilot.key");
    } catch (_) {}
  }
  $("demoToken").addEventListener("input", updateKeyState);

  // ── Errors ───────────────────────────────────────────────
  function showError(msg) {
    $("errorBanner").innerText = msg;
    $("errorBanner").classList.add("visible");
    $("app").classList.add("has-error");
  }
  function clearError() {
    $("errorBanner").classList.remove("visible");
    $("app").classList.remove("has-error");
  }

  // ── Inbox ────────────────────────────────────────────────
  function parseEmail(filename, raw) {
    const text = raw.replace(/\r\n/g, "\n");
    const split = text.indexOf("\n\n");
    const head = split >= 0 ? text.slice(0, split) : "";
    const body = split >= 0 ? text.slice(split + 2).trim() : text.trim();
    const h = {};
    head.split("\n").forEach((line) => {
      const i = line.indexOf(":");
      if (i > 0) h[line.slice(0, i).trim().toLowerCase()] = line.slice(i + 1).trim();
    });
    return {
      id: filename, from: h.from || "unknown sender", to: h.to || "", date: h.date || "",
      subject: h.subject || filename, body, snippet: body.replace(/\s+/g, " ").slice(0, 90),
    };
  }

  function shortDate(d) {
    const t = Date.parse(d);
    if (isNaN(t)) return d;
    return new Date(t).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  }

  const ROLE_MAILBOXES = ["accounts", "billing", "support", "it-support", "noreply", "no-reply", "info", "finance", "hr", "ap"];
  const titleCase = (w) => w.split(/[._-]/).filter(Boolean).map((p) => p[0].toUpperCase() + p.slice(1)).join(" ");

  function senderName(from) {
    const [local, domain = ""] = from.split("@");
    // Shared mailboxes read better as the company: "accounts@designcraft.com" -> "Designcraft accounts"
    if (ROLE_MAILBOXES.includes(local.toLowerCase()) && domain) {
      return `${titleCase(domain.split(".")[0])} ${local.toLowerCase()}`;
    }
    return titleCase(local);
  }

  function longDate(d) {
    const t = Date.parse(d);
    if (isNaN(t)) return d;
    return new Date(t).toLocaleString(undefined, { weekday: "short", day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
  }

  function renderInbox() {
    const list = $("inboxList");
    list.innerHTML = "";
    messages.forEach((m) => {
      const run = runsByMessage[m.id];
      const tag = run ? statusTag(run.status) : (m.id === "compose" ? "draft" : "");
      const tagClass = run && run.status === "completed" ? "done" : (run && run.status === "awaiting_approval" ? "waiting" : "");
      const el = document.createElement("button");
      el.className = "msg" + (current && current.id === m.id ? " active" : "");
      el.innerHTML = `
        <div class="msg-top"><span class="msg-from"></span><span class="msg-date"></span></div>
        <div class="msg-subject"></div>
        <div class="msg-snippet"></div>
        ${tag ? `<span class="msg-tag ${tagClass}"></span>` : ""}`;
      el.querySelector(".msg-from").textContent = m.id === "compose" ? "New message" : senderName(m.from);
      el.querySelector(".msg-date").textContent = m.id === "compose" ? "" : shortDate(m.date);
      el.querySelector(".msg-subject").textContent = m.subject;
      el.querySelector(".msg-snippet").textContent = m.snippet;
      if (tag) el.querySelector(".msg-tag").textContent = tag;
      el.onclick = () => openMessage(m.id);
      list.appendChild(el);
    });
    const pending = Object.values(runsByMessage).filter((r) => r.status === "awaiting_approval").length;
    $("inboxCount").textContent = pending ? `${pending} awaiting you` : `${messages.length - 1} messages`;
  }

  function statusTag(s) {
    return { awaiting_approval: "● waiting for approval", completed: "✓ done", rejected: "✕ rejected",
             needs_human_review: "→ sent to a person", failed: "! failed" }[s] || s;
  }

  function openMessage(id) {
    current = messages.find((m) => m.id === id);
    if (!current) return;
    $("msgSubject").textContent = current.id === "compose" ? "Write your own email" : current.subject;
    $("msgFrom").textContent = current.from;
    $("msgTo").textContent = current.to;
    $("msgDate").textContent = longDate(current.date);
    const body = $("msgBody");
    body.value = current.body;
    body.readOnly = current.id !== "compose";
    body.classList.toggle("editable", current.id === "compose");
    renderInbox();
    const run = runsByMessage[id];
    if (run) { currentRunId = run.run_id; renderState(run); }
    else { currentRunId = null; resetReview(); }
  }

  async function loadInbox() {
    let samples = FALLBACK_SAMPLES;
    try {
      const res = await fetch("/samples");
      if (res.ok) {
        const data = await res.json();
        if (data.samples && data.samples.length) samples = data.samples;
      }
    } catch (_) { /* offline: keep the built-in sample */ }
    messages = samples.map((s) => parseEmail(s.filename, s.content));
    messages.sort((a, b) => (Date.parse(b.date) || 0) - (Date.parse(a.date) || 0));
    messages.push(COMPOSE);
    openMessage(messages[0].id);
  }

  // ── API ──────────────────────────────────────────────────
  async function callApi(path, body) {
    const token = $("demoToken").value.trim();
    if (!token && !demoPublic) throw new Error("Paste the access key (DEMO_TOKEN) in the top right first.");
    const headers = { "Content-Type": "application/json" };
    if (token) headers["X-Demo-Token"] = token;
    const res = await fetch(path, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    });
    let data = {};
    try { data = await res.json(); } catch (_) { /* non-JSON error page */ }
    if (!res.ok) {
      const detail = data && data.detail ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)) : res.statusText;
      if (res.status === 401) throw new Error("That access key was not accepted. Check it matches DEMO_TOKEN on Render.");
      if (res.status === 429) throw new Error("Too many requests. Wait a minute and try again.");
      if (res.status === 503) throw new Error("The server has no DEMO_TOKEN configured, so agent requests are disabled.");
      if (res.status === 404 && path.startsWith("/runs/")) throw new Error("The server no longer has this run (it probably restarted). Run the agent again.");
      if (res.status === 400 && path.startsWith("/runs/")) throw new Error("This run is no longer waiting for approval. Run the agent again to get a fresh one.");
      throw new Error(`Request failed (${res.status}): ${detail}`);
    }
    return data;
  }

  // ── Actions ──────────────────────────────────────────────
  async function executeProcess() {
    if (!current) return;
    const btn = $("processBtn");
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Reading…';
    clearError();
    setDecisionEnabled(false);
    const raw = `From: ${current.from}\nTo: ${current.to}\nSubject: ${current.id === "compose" ? "Request" : current.subject}\n\n${$("msgBody").value}`;
    const runFor = current.id;
    try {
      const data = await callApi("/process", { raw_input: raw, input_source: "email" });
      runsByMessage[runFor] = data;
      if (current.id === runFor) { currentRunId = data.run_id; renderState(data); }
      renderInbox();
    } catch (err) {
      showError(err.message);
    } finally {
      btn.disabled = false;
      btn.innerHTML = 'Run agent <kbd>⌘↵</kbd>';
    }
  }

  async function handleDecision(decision) {
    if (!currentRunId) { showError("Run the agent first."); return; }
    clearError();
    setDecisionEnabled(false);
    const runFor = current.id;
    try {
      const path = `/runs/${currentRunId}/${decision === "approve" ? "approve" : "reject"}`;
      const data = await callApi(path, decision === "reject" ? { reason: "Rejected by reviewer" } : {});
      runsByMessage[runFor] = data;
      renderState(data);
      renderInbox();
    } catch (err) {
      showError(err.message);
      setDecisionEnabled(true);
    }
  }

  function setDecisionEnabled(on) {
    $("approveBtn").disabled = !on;
    $("rejectBtn").disabled = !on;
  }

  // ── Rendering ────────────────────────────────────────────
  function resetReview() {
    $("reviewEmpty").style.display = "";
    $("reviewBody").style.display = "none";
    $("statusPill").style.display = "none";
    setDecisionEnabled(false);
  }

  function describeChange(act, ex) {
    const who = ex.employee_name || ex.employee_id || "the employee";
    const inc = (act.update_payload || {})["$inc"] || {};
    switch (act.action_type) {
      case "deduct_leave": {
        const key = Object.keys(inc)[0] || "";
        const days = Math.abs(inc[key] || 0);
        const type = key.split(".")[1] || "leave";
        return [`Deduct ${days} ${type} leave day${days === 1 ? "" : "s"} from ${who}`, `employees · ${act.filter_query ? Object.values(act.filter_query).join(", ") : ""}`];
      }
      case "mark_invoice_paid":
        return [`Mark invoice ${ex.invoice_number || ""} as paid`, `${ex.vendor_name || "invoices"}${ex.amount ? " · ₹" + Number(ex.amount).toLocaleString("en-IN") : ""}`];
      case "close_ticket":
        return [`Resolve ticket ${ex.ticket_id || ""}`, `tickets${ex.priority ? " · " + ex.priority + " priority" : ""}`];
      default:
        return [act.reason || "No database change needed", act.collection || ""];
    }
  }

  function renderState(data) {
    $("reviewEmpty").style.display = "none";
    $("reviewBody").style.display = "";

    const states = {
      awaiting_approval: ["awaiting", "Waiting for you"],
      completed: ["completed", "Done"],
      rejected: ["rejected", "Rejected"],
      needs_human_review: ["review", "Sent to a person"],
      failed: ["failed", "Failed"],
    };
    const [cls, label] = states[data.status] || ["review", data.status || "Unknown"];
    const pill = $("statusPill");
    pill.className = `status ${cls}`;
    pill.style.display = "";
    $("statusPillText").textContent = label;

    const ex = data.extracted || {};
    const act = data.proposed_action || {};
    const hasChange = act.action_type && act.action_type !== "none";
    const awaiting = data.status === "awaiting_approval";

    // Proposed change
    $("changeBlock").style.display = "";
    if (hasChange) {
      const [summary, meta] = describeChange(act, ex);
      $("changeSummary").textContent = summary;
      $("changeMeta").textContent = meta;
      $("changeOp").textContent = JSON.stringify({ collection: act.collection, filter: act.filter_query, update: act.update_payload }, null, 2);
      $("changeRaw").style.display = "";
    } else {
      $("changeSummary").textContent = data.status === "needs_human_review" ? "Nothing changed. A person needs to look at this one." : (act.reason || "No database change needed.");
      $("changeMeta").textContent = "";
      $("changeRaw").style.display = "none";
    }
    $("decisionRow").style.display = awaiting ? "" : "none";
    setDecisionEnabled(awaiting);

    const outcomes = {
      completed: hasChange
        ? (demoPublic ? "Approved. The change was applied to the demo sandbox." : "Approved. The change has been written to the database.")
        : "No approval was needed.",
      rejected: "Rejected. Nothing was written.",
      needs_human_review: data.error ? `Why: ${data.error}` : "",
      failed: data.error ? `The update did not go through: ${data.error}` : "The update did not go through.",
    };
    $("outcome").textContent = outcomes[data.status] || (awaiting ? "Nothing is written until you approve." : "");

    // Extracted fields
    const fl = $("fieldList");
    fl.innerHTML = "";
    const typeRow = ["Type", TYPE_LABELS[data.document_type] || data.document_type || "—"];
    const rows = [typeRow].concat(
      Object.entries(FIELD_LABELS)
        .filter(([k]) => k !== "document_type" && ex[k] !== null && ex[k] !== undefined && ex[k] !== "")
        .filter(([k]) => k !== "issue_summary" || data.document_type === "support_ticket")
        .map(([k, label]) => [label, k === "amount" ? "₹" + Number(ex[k]).toLocaleString("en-IN") : String(ex[k])])
    );
    rows.forEach(([k, v]) => {
      const dt = document.createElement("dt"); dt.textContent = k;
      const dd = document.createElement("dd"); dd.textContent = v;
      fl.append(dt, dd);
    });

    // Draft
    const d = data.draft_reply;
    if (d && d.body) {
      $("draftBlock").style.display = "";
      $("draftTo").textContent = `To: ${d.to}`;
      $("draftSubject").textContent = `Subject: ${d.subject}`;
      $("draftBody").textContent = d.body;
    } else {
      $("draftBlock").style.display = "none";
    }

    // Steps
    const sl = $("stepList");
    sl.innerHTML = "";
    (data.tool_trace || []).forEach((t) => {
      const li = document.createElement("li");
      li.textContent = STEP_LABELS[t] || t;
      const code = document.createElement("code"); code.textContent = t;
      li.appendChild(code);
      sl.appendChild(li);
    });
  }

  async function copyDraft(btn) {
    try {
      await navigator.clipboard.writeText($("draftBody").textContent);
      btn.textContent = "Copied";
    } catch (_) {
      btn.textContent = "Copy failed";
    }
    setTimeout(() => { btn.textContent = "Copy reply"; }, 1500);
  }

  // ── Keyboard ─────────────────────────────────────────────
  document.addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") { e.preventDefault(); executeProcess(); return; }
    const typing = ["INPUT", "TEXTAREA"].includes(document.activeElement.tagName) && !document.activeElement.readOnly;
    if (typing || e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === "a" && !$("approveBtn").disabled) handleDecision("approve");
    if (e.key === "r" && !$("rejectBtn").disabled) handleDecision("reject");
  });

  async function loadConfig() {
    try {
      const res = await fetch("/config");
      if (res.ok) demoPublic = !!(await res.json()).demo_public;
    } catch (_) { /* assume a key is required */ }
    document.body.classList.toggle("demo-public", demoPublic);
  }

  loadKey();
  loadConfig();
  loadInbox();
</script>
</body>
</html>
"""
