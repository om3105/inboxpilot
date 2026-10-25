# 🎬 InboxPilot — 2-Minute Portfolio Demo Video Script

**Target Duration:** 2 minutes (120 seconds)  
**Presenter:** Agentic AI Engineer Intern Candidate  
**Screen Setup:** Split screen — Left: Terminal / Postman (or Swagger UI at `/docs`); Right: MongoDB Atlas & Langfuse Tracing Dashboard.

---

### [00:00 - 00:25] Hook & Problem Statement
* **Visual:** Show InboxPilot architecture diagram on the screen, then transition to Swagger UI (`https://inboxpilot-demo.onrender.com/docs`).
* **Spoken Script:**
  > *"Hi, I'm [Your Name]. In enterprise ops, operations teams spend thousands of hours reading inbound employee leave requests, supplier invoices, and IT tickets, cross-checking internal databases, and manually drafting responses.
  >
  > Today, I'm presenting **InboxPilot**: a production-grade, human-in-the-loop AI agent built with LangGraph, FastAPI, and MongoDB Atlas. What makes InboxPilot unique is that while it automates extraction and drafting end-to-end, it enforces a strict human-in-the-loop gate before executing any sensitive database writes—persisting paused state in MongoDB so runs survive server restarts."*

---

### [00:25 - 00:55] Step 1: Ingestion, Extraction & Interruption
* **Visual:** In Swagger UI, execute `POST /process` with sample `samples/leave_request_01.eml` (Aarav Sharma requesting 2 days of casual leave).
* **Spoken Script:**
  > *"Let's submit a raw leave request from our engineering team. The agent parses the email, uses our structured LLM provider to extract employee ID EMP001 and leave dates into Pydantic models, and queries MongoDB to check his available balance.
  > 
  > Notice the API response: the status is `awaiting_approval`, with `requires_approval: true`. Under the hood, LangGraph hit an `interrupt()` node. The agent has already drafted a professional reply and formulated a proposed balance deduction, but it paused without mutating the database."*

---

### [00:55 - 01:25] Step 2: Human Sign-Off & Execution
* **Visual:** Point out the `proposed_action` payload (`$inc: {"leave_balance.casual": -2}`). Then call `POST /runs/{run_id}/approve` with header `X-Demo-Token`.
* **Spoken Script:**
  > *"As the human manager, I inspect the proposed mutation and verify the employee's remaining balance. I click 'Approve'.
  >
  > The API immediately calls LangGraph's checkpointer using the persistent `thread_id` and resumes execution. The agent applies the atomic update to MongoDB Atlas, records the audit trail, and marks the run `completed`. If I had rejected the run, the agent would terminate cleanly without modifying records."*

---

### [01:25 - 01:45] Step 3: Observability with Langfuse
* **Visual:** Switch browser tab to Langfuse Cloud project. Open the trace corresponding to the `run_id`.
* **Spoken Script:**
  > *"Every single run is instrumented with Langfuse. Here in the trace view, we can inspect each node: exact latency breakdown, token consumption, the structured schema extraction, and database execution results. If an extraction failed or a prompt injection occurred, I can pinpoint the offending node in seconds."*

---

### [01:45 - 02:00] Conclusion & Benchmark Results
* **Visual:** Display the 50-example benchmark evaluation table.
* **Spoken Script:**
  > *"To ensure reliability, I evaluated InboxPilot against a 50-case benchmark including adversarial prompt injections and malformed emails. Every case is scored strictly, and CI blocks any regression. No prompt injection ever produced a database write, and the runner reports exactly which ambiguous cases still fail, so I know where to improve next.
  >
  > The live demo and complete codebase are available on GitHub and Render. Thank you!"*
