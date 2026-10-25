"""
app/ui.py — Light-theme operational review dashboard for InboxPilot.
"""

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>InboxPilot — Operational Review</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {
      --sidebar-bg: #ffffff;
      --sidebar-text: #475569;
      --sidebar-active-bg: #f1f5f9;
      --sidebar-active-text: #0f172a;
      --body-bg: #f8fafc;
      --card-bg: #ffffff;
      --border-color: #e2e8f0;
      --text-primary: #0f172a;
      --text-secondary: #334155;
      --text-muted: #64748b;
      --primary: #2563eb;
      --primary-hover: #1d4ed8;
      --emerald: #059669;
      --emerald-hover: #047857;
      --rose: #dc2626;
      --rose-hover: #b91c1c;
      --font: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      --font-mono: 'JetBrains Mono', monospace;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: var(--font);
      background-color: var(--body-bg);
      color: var(--text-primary);
      min-height: 100vh;
      display: flex;
    }

    /* ── Left Sidebar (Clean White Theme) ──────────────────────────────────── */
    aside {
      width: 240px;
      background: var(--sidebar-bg);
      color: var(--sidebar-text);
      display: flex;
      flex-direction: column;
      flex-shrink: 0;
      border-right: 1px solid var(--border-color);
    }

    .brand {
      padding: 24px 20px;
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 18px;
      font-weight: 700;
      color: var(--text-primary);
      letter-spacing: -0.3px;
    }
    .brand-icon {
      width: 32px;
      height: 32px;
      background: #2563eb;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;
      font-size: 16px;
    }

    nav {
      flex: 1;
      padding: 0 12px;
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .nav-item {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 10px 14px;
      border-radius: 8px;
      font-size: 14px;
      font-weight: 500;
      color: var(--sidebar-text);
      text-decoration: none;
      cursor: pointer;
      transition: all 0.15s ease;
    }
    .nav-item:hover {
      background: #f1f5f9;
      color: var(--text-primary);
    }
    .nav-item.active {
      background: #f1f5f9;
      color: var(--text-primary);
      font-weight: 600;
    }
    .nav-badge {
      margin-left: auto;
      background: #2563eb;
      color: white;
      font-size: 11px;
      padding: 2px 7px;
      border-radius: 10px;
      font-weight: 600;
    }

    /* ── Main Layout ───────────────────────────────────────────────────────── */
    .main-wrapper {
      flex: 1;
      display: flex;
      flex-direction: column;
      overflow-y: auto;
    }

    header {
      padding: 20px 32px;
      background: #ffffff;
      border-bottom: 1px solid var(--border-color);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .header-title {
      font-size: 22px;
      font-weight: 700;
      color: var(--text-primary);
      letter-spacing: -0.5px;
    }
    .header-actions {
      display: flex;
      align-items: center;
      gap: 16px;
    }
    .token-box {
      display: flex;
      align-items: center;
      background: #f1f5f9;
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      padding: 6px 12px;
      gap: 8px;
      font-size: 12px;
    }
    .token-box input {
      border: none;
      background: transparent;
      outline: none;
      font-family: var(--font-mono);
      font-size: 12px;
      width: 170px;
      color: #334155;
    }

    .content-grid {
      padding: 28px 32px;
      display: grid;
      grid-template-columns: 380px 1fr;
      gap: 24px;
      max-width: 1440px;
    }

    /* ── Cards ─────────────────────────────────────────────────────────────── */
    .card {
      background: var(--card-bg);
      border: 1px solid var(--border-color);
      border-radius: 12px;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
      padding: 20px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .card-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .card-title {
      font-size: 16px;
      font-weight: 600;
      color: var(--text-primary);
    }

    .user-row {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .user-avatar {
      width: 40px;
      height: 40px;
      background: #e2e8f0;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 600;
      color: #475569;
      font-size: 14px;
    }
    .user-meta {
      display: flex;
      flex-direction: column;
    }
    .user-name {
      font-size: 14px;
      font-weight: 600;
      color: var(--text-primary);
    }
    .user-email {
      font-size: 12px;
      color: var(--text-muted);
    }

    .subject-line {
      font-size: 15px;
      font-weight: 600;
      color: var(--text-primary);
    }

    .message-body-text {
      font-size: 13.5px;
      line-height: 1.6;
      color: #334155;
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      padding: 14px;
      white-space: pre-wrap;
      font-family: inherit;
    }

    .sample-chips {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
    .chip {
      background: #f1f5f9;
      border: 1px solid #e2e8f0;
      color: #475569;
      padding: 4px 10px;
      border-radius: 6px;
      font-size: 11.5px;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.15s;
    }
    .chip:hover {
      background: #e2e8f0;
      color: #0f172a;
    }
    .chip.active {
      background: #eff6ff;
      border-color: #bfdbfe;
      color: #1d4ed8;
      font-weight: 600;
    }

    .btn-submit {
      background: var(--primary);
      color: #ffffff;
      border: none;
      border-radius: 8px;
      padding: 10px 16px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      transition: background 0.15s;
    }
    .btn-submit:hover { background: var(--primary-hover); }
    .btn-submit:disabled { opacity: 0.6; cursor: not-allowed; }

    /* ── Right Panel: Operational Modal & Draft ────────────────────────────── */
    .review-stack {
      display: flex;
      flex-direction: column;
      gap: 20px;
      position: relative;
    }

    /* Authentic Authorization Modal (as in image) */
    .auth-modal {
      background: #ffffff;
      border: 1px solid #cbd5e1;
      border-radius: 12px;
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.05);
      padding: 24px;
      display: none;
      flex-direction: column;
      gap: 16px;
      position: relative;
    }
    .auth-modal.visible {
      display: flex;
    }

    .auth-modal-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .auth-modal-title {
      font-size: 17px;
      font-weight: 700;
      color: #0f172a;
    }
    .auth-modal-close {
      cursor: pointer;
      color: #94a3b8;
      font-size: 18px;
      line-height: 1;
    }

    .section-label {
      font-size: 13px;
      font-weight: 600;
      color: #475569;
    }

    /* Modal Table */
    .modal-table {
      width: 100%;
      border-collapse: collapse;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      overflow: hidden;
      font-size: 13px;
    }
    .modal-table td {
      padding: 10px 14px;
      border-bottom: 1px solid #f1f5f9;
    }
    .modal-table tr:last-child td {
      border-bottom: none;
    }
    .modal-table td.col-label {
      width: 160px;
      background: #f8fafc;
      color: #64748b;
      font-weight: 500;
      border-right: 1px solid #e2e8f0;
    }
    .modal-table td.col-val {
      color: #0f172a;
      font-weight: 500;
      font-family: var(--font-mono);
      font-size: 12.5px;
    }

    .modal-actions {
      display: flex;
      gap: 12px;
      margin-top: 4px;
    }
    .btn-approve-clean {
      flex: 1;
      background: #059669;
      color: white;
      border: none;
      border-radius: 8px;
      padding: 11px 16px;
      font-size: 13.5px;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.15s;
    }
    .btn-approve-clean:hover { background: #047857; }

    .btn-reject-clean {
      flex: 1;
      background: #dc2626;
      color: white;
      border: none;
      border-radius: 8px;
      padding: 11px 16px;
      font-size: 13.5px;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.15s;
    }
    .btn-reject-clean:hover { background: #b91c1c; }

    /* Drafted Reply Card */
    .draft-card {
      background: #ffffff;
      border: 1px solid var(--border-color);
      border-radius: 12px;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
      padding: 20px;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }
    .draft-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .draft-recipient {
      font-size: 13px;
      color: var(--text-muted);
    }
    .draft-body {
      background: #fafafa;
      border: 1px solid #f1f5f9;
      border-radius: 8px;
      padding: 14px;
      font-size: 13.5px;
      line-height: 1.6;
      color: #334155;
      white-space: pre-wrap;
    }

    /* Status badge */
    .status-pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 10px;
      border-radius: 12px;
      font-size: 12px;
      font-weight: 600;
    }
    .status-pill.awaiting {
      background: #fef3c7;
      color: #92400e;
    }
    .status-pill.completed {
      background: #d1fae5;
      color: #065f46;
    }
    .status-pill.rejected {
      background: #fee2e2;
      color: #991b1b;
    }
    .status-pill.review {
      background: #e0e7ff;
      color: #3730a3;
    }
    .error-banner {
      display: none;
      margin: 20px 32px 0;
      padding: 10px 14px;
      border: 1px solid #fecaca;
      border-radius: 8px;
      background: #fef2f2;
      color: #991b1b;
      font-size: 13px;
    }
    .error-banner.visible { display: block; }
    .modal-actions button:disabled { opacity: 0.45; cursor: not-allowed; }
  </style>
</head>
<body>

  <!-- Left Sidebar -->
  <aside>
    <div class="brand">
      <div class="brand-icon">✉</div>
      <span>InboxPilot</span>
    </div>

    <nav>
      <div class="nav-item active" onclick="scrollToTop()">
        <span>📥</span>
        <span>Inbox</span>
      </div>
      <div class="nav-item" onclick="focusApproval()">
        <span>📝</span>
        <span>Pending Approvals</span>
        <span class="nav-badge" id="navBadge">0</span>
      </div>
    </nav>
  </aside>

  <!-- Main Content Area -->
  <div class="main-wrapper">
    <header>
      <div class="header-title">Operational Review</div>
      <div class="header-actions">
        <div class="token-box">
          <span style="color: #64748b;">Demo Token:</span>
          <input type="password" id="demoToken" placeholder="Paste DEMO_TOKEN" autocomplete="off">
        </div>
        <div id="statusPill" class="status-pill awaiting" style="display: none;">
          <span style="width: 6px; height: 6px; border-radius: 50%; background: currentColor;"></span>
          <span id="statusPillText">Awaiting Approval</span>
        </div>
      </div>
    </header>

    <div id="errorBanner" class="error-banner" role="alert"></div>

    <div class="content-grid">
      <!-- Inbound Column -->
      <div class="card">
        <div class="card-head">
          <span class="card-title">Inbound</span>
          <div class="sample-chips">
            <span class="chip active" onclick="loadSample('leave', this)">Leave</span>
            <span class="chip" onclick="loadSample('invoice', this)">Invoice</span>
            <span class="chip" onclick="loadSample('ticket', this)">Ticket</span>
          </div>
        </div>

        <div class="user-row">
          <div class="user-avatar" id="avatarBox">AS</div>
          <div class="user-meta">
            <span class="user-name" id="senderName">Aarav Sharma (EMP001)</span>
            <span class="user-email" id="senderEmail">aarav.sharma@acme.dev</span>
          </div>
        </div>

        <div class="subject-line" id="displaySubject">Casual Leave Application</div>

        <div class="message-body-text" id="displayBody">Hi HR,

I would like to apply for 2 days of casual leave from 2024-10-24 to 2024-10-25 for a family event.
My employee ID is EMP001. My manager Priya Patel has approved.

Regards,
Aarav Sharma</div>

        <button id="processBtn" class="btn-submit" onclick="executeProcess()">
          <span>Run LangGraph Agent</span>
        </button>
      </div>

      <!-- Right Review Stack -->
      <div class="review-stack">
        
        <!-- Authorization Required Modal (Exact Match to Image) -->
        <div id="authModal" class="auth-modal">
          <div class="auth-modal-header">
            <span class="auth-modal-title">Authorization Required</span>
          </div>

          <span class="section-label">Database Update</span>

          <table class="modal-table">
            <tr>
              <td class="col-label">Target Collection</td>
              <td class="col-val" id="rowCollection">—</td>
            </tr>
            <tr>
              <td class="col-label">Action</td>
              <td class="col-val" id="rowAction">—</td>
            </tr>
            <tr>
              <td class="col-label">Mutation Payload</td>
              <td class="col-val" id="rowPayload">—</td>
            </tr>
            <tr>
              <td class="col-label">Reason</td>
              <td class="col-val" id="rowReason">Run the agent to see the proposed update.</td>
            </tr>
          </table>

          <div class="modal-actions">
            <button id="approveBtn" class="btn-approve-clean" onclick="handleDecision('approve')" disabled>Approve & Execute</button>
            <button id="rejectBtn" class="btn-reject-clean" onclick="handleDecision('reject')" disabled>Reject</button>
          </div>
        </div>

        <!-- Drafted Reply Card -->
        <div class="draft-card">
          <div class="draft-header">
            <span class="card-title">Drafted Reply</span>
            <span class="draft-recipient" id="draftTo"></span>
          </div>

          <div class="draft-body" id="draftBody">Run the agent to generate a reply.</div>
        </div>

      </div>
    </div>
  </div>

  <script>
    let currentRunId = null;

    const SAMPLES = {
      leave: {
        avatar: "AS",
        name: "Aarav Sharma (EMP001)",
        email: "aarav.sharma@acme.dev",
        subject: "Casual Leave Application",
        body: "Hi HR,\\n\\nI would like to apply for 2 days of casual leave from 2024-10-24 to 2024-10-25 for a family event.\\nMy employee ID is EMP001. My manager Priya Patel has approved.\\n\\nRegards,\\nAarav Sharma"
      },
      invoice: {
        avatar: "CS",
        name: "CloudStack Billing",
        email: "billing@cloudstack.io",
        subject: "Invoice INV-2024-001 Due Reminder",
        body: "Dear Accounts Payable,\\n\\nPlease find attached the invoice INV-2024-001 for CloudStack Solutions.\\nAmount: $4,500.00 USD\\nDue Date: 2024-11-05\\nDescription: AWS Cloud Hosting October 2024"
      },
      ticket: {
        avatar: "RM",
        name: "Rohan Mehta",
        email: "rohan.mehta@acme.dev",
        subject: "Cannot access finance dashboard (Ticket TKT-302)",
        body: "Hi IT Support,\\n\\nFollowing up on ticket TKT-302. I still get a 403 Forbidden error since yesterday's release.\\nThis is blocking month-end closing, please resolve."
      }
    };

    function loadSample(key, el) {
      document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
      if (el) el.classList.add('active');

      const s = SAMPLES[key];
      document.getElementById('avatarBox').innerText = s.avatar;
      document.getElementById('senderName').innerText = s.name;
      document.getElementById('senderEmail').innerText = s.email;
      document.getElementById('displaySubject').innerText = s.subject;
      document.getElementById('displayBody').innerText = s.body.replace(/\\\\n/g, '\\n');
    }

    function showError(msg) {
      const el = document.getElementById('errorBanner');
      el.innerText = msg;
      el.classList.add('visible');
    }

    function clearError() {
      document.getElementById('errorBanner').classList.remove('visible');
    }

    function setDecisionEnabled(enabled) {
      document.getElementById('approveBtn').disabled = !enabled;
      document.getElementById('rejectBtn').disabled = !enabled;
    }

    async function callApi(path, body) {
      const token = document.getElementById('demoToken').value.trim();
      if (!token) {
        throw new Error('Paste the DEMO_TOKEN into the Demo Token box first.');
      }
      const res = await fetch(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Demo-Token': token },
        body: JSON.stringify(body)
      });
      let data = {};
      try { data = await res.json(); } catch (_) { /* non-JSON error page */ }
      if (!res.ok) {
        const detail = (data && data.detail) ? (typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)) : res.statusText;
        if (res.status === 401) throw new Error('Token rejected (401): check the Demo Token matches DEMO_TOKEN on Render.');
        if (res.status === 429) throw new Error('Rate limit reached (429): wait a minute and try again.');
        throw new Error(`Request failed (${res.status}): ${detail}`);
      }
      return data;
    }

    async function executeProcess() {
      const btn = document.getElementById('processBtn');
      btn.disabled = true;
      btn.innerText = 'Processing...';
      clearError();
      setDecisionEnabled(false);

      const email = document.getElementById('senderEmail').innerText;
      const subject = document.getElementById('displaySubject').innerText;
      const body = document.getElementById('displayBody').innerText;
      const rawText = `From: ${email}\nSubject: ${subject}\n\n${body}`;

      try {
        const data = await callApi('/process', { raw_input: rawText, input_source: 'email' });
        currentRunId = data.run_id;
        renderState(data);
      } catch (err) {
        showError(err.message);
      } finally {
        btn.disabled = false;
        btn.innerText = 'Run LangGraph Agent';
      }
    }

    function renderState(data) {
      const pill = document.getElementById('statusPill');
      const pillText = document.getElementById('statusPillText');
      const authModal = document.getElementById('authModal');
      const act = data.proposed_action || {};
      pill.style.display = 'inline-flex';

      document.getElementById('rowCollection').innerText = act.collection || '—';
      document.getElementById('rowAction').innerText = act.action_type || '—';
      document.getElementById('rowPayload').innerText =
        act.update_payload && Object.keys(act.update_payload).length ? JSON.stringify(act.update_payload) : '—';
      document.getElementById('rowReason').innerText = act.reason || data.error || data.message || '—';

      const states = {
        awaiting_approval: ['awaiting', 'Awaiting Approval', '1'],
        completed: ['completed', 'Completed & Executed', '0'],
        rejected: ['rejected', 'Rejected', '0'],
        needs_human_review: ['review', 'Needs Human Review', '0'],
        failed: ['rejected', 'Execution Failed', '0'],
      };
      const [cls, label, badge] = states[data.status] || ['review', data.status || 'Unknown', '0'];
      pill.className = `status-pill ${cls}`;
      pillText.innerText = label;
      document.getElementById('navBadge').innerText = badge;

      const awaiting = data.status === 'awaiting_approval';
      authModal.classList.toggle('visible', awaiting);
      setDecisionEnabled(awaiting);

      if (data.status === 'needs_human_review' && data.error) {
        showError(`Routed to human review: ${data.error}`);
      } else if (data.status === 'failed') {
        showError(data.error || data.message || 'Execution failed.');
      }

      const draft = data.draft_reply;
      if (draft && draft.body) {
        document.getElementById('draftTo').innerText = `To: ${draft.to}`;
        document.getElementById('draftBody').innerText = draft.body;
      } else {
        document.getElementById('draftTo').innerText = '';
        document.getElementById('draftBody').innerText = 'No reply drafted for this run.';
      }
    }

    async function handleDecision(decision) {
      if (!currentRunId) {
        showError('Run the agent first.');
        return;
      }
      clearError();
      setDecisionEnabled(false);
      const endpoint = `/runs/${currentRunId}/${decision === 'approve' ? 'approve' : 'reject'}`;
      try {
        const data = await callApi(endpoint, decision === 'reject' ? { reason: 'Rejected by operator' } : {});
        renderState(data);
      } catch (err) {
        showError(err.message);
        setDecisionEnabled(true);
      }
    }

    function scrollToTop() {
      const wrapper = document.querySelector('.main-wrapper') || window;
      wrapper.scrollTo({ top: 0, behavior: 'smooth' });
    }

    function focusApproval() {
      const modal = document.getElementById('authModal');
      if (modal) {
        modal.classList.add('visible');
        modal.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }

    // Auto-load leave preset on start
    window.addEventListener('DOMContentLoaded', () => {
      // Show initial awaiting state as preview
      document.getElementById('authModal').classList.add('visible');
    });
  </script>
</body>
</html>
"""
