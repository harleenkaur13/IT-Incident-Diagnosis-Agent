# Evidence-Driven Agentic AI for IT Incident Diagnosis & Verified Resolution

> Major Project, Phase 1 prototype  
> Dept. of Computer Science and Engineering, Dr. B R Ambedkar National Institute of Technology, Jalandhar

A Phase 1 prototype of an auditable, evidence-driven agentic AI workflow for IT incident troubleshooting. Instead of suggesting fixes the way a standard RAG chatbot does, the system:

1. retrieves internal SOPs and policies,
2. runs read-only diagnostics against a **simulated** IT environment,
3. ranks root causes with supporting and conflicting evidence and citations,
4. pauses for human approval before any restricted action, and
5. verifies that the service has recovered before closing the ticket.

> **Note:** All infrastructure in this project is simulated. No real systems are touched, and results may not transfer directly to real environments.

---

## Workflow

```text
Incident report
      │
      ▼
Retrieve SOPs / policies / past tickets (RAG)
      │
      ▼
Run read-only diagnostic tools (simulator)
      │
      ▼
Rank root-cause hypotheses (LLM, structured output, with citations)
      │
      ▼
Restricted action proposed ──► Human approval gate (Approve / Reject)
      │                                   │
   Approved                            Rejected
      │                                   │
      ▼                                   ▼
Execute remediation                  ESCALATED
      │
      ▼
Re-run diagnostics to verify
      │
      ├── Recovered ──► CLOSED_VERIFIED
      └── Not recovered ──► ESCALATED
```

---

## What It Currently Does (Phase 1 Scope)

### Knowledge Retrieval (RAG)

- Indexes curated VPN troubleshooting SOPs, authorization policies and historical tickets.
- Embeddings: `BAAI/bge-small-en-v1.5`.
- Vector store: local **FAISS** index.
- Every retrieved chunk carries a source citation.

### Deterministic IT Simulator

Stateful, reproducible fault scenarios:

| Scenario | Description |
|---|---|
| `vpn_service_stopped` | The VPN service is down |
| `auth_expired` | The user's authentication has expired |

Tools:

| Type | Tool | Notes |
|---|---|---|
| Diagnostic (read-only) | `check_network_status` | Network reachability |
| Diagnostic (read-only) | `check_account_auth` | Account / authentication state |
| Diagnostic (read-only) | `check_vpn_status` | VPN service state |
| Remediation (restricted) | `restart_vpn_service` | Requires human approval |

### LangGraph Agentic Orchestration

- Retrieves relevant documentation and runs safe diagnostic checks.
- Uses Groq (`openai/gpt-oss-120b`) with structured outputs to produce ranked hypotheses with confidence scores, supporting and conflicting evidence, and source citations.
- **Human-in-the-loop (HITL) approval gate:** execution pauses before any restricted action, using LangGraph checkpointing (`MemorySaver`).
- **Post-remediation verification and escalation:**
  - Diagnostics are re-run after an approved fix to confirm recovery, ending in `CLOSED_VERIFIED`.
  - If the action is rejected or recovery cannot be verified, the incident is escalated to Level-2 IT Support (`ESCALATED`).

### Audit Trail

A complete JSON investigation log is saved for every run at `logs/<incident_id>.json`.

### Interactive Demo UI

A split-screen **Streamlit** dashboard showing:

- the live investigation timeline,
- tool outputs,
- cited SOPs,
- ranked root causes,
- Approve / Reject controls.

---

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- A [Groq API key](https://console.groq.com/)

---

## How to Run

### 1. Clone the repository

```bash
git clone https://github.com/harleenkaur13/IT-Incident-Diagnosis-Agent.git
cd IT-Incident-Diagnosis-Agent
```

### 2. Install dependencies

```bash
uv sync
```

### 3. Configure environment variables

Copy `.env.example` to `.env`:

```bash
# macOS / Linux
cp .env.example .env

# Windows (PowerShell)
Copy-Item .env.example .env
```

Then add your Groq API key to `.env`:

```env
GROQ_API_KEY=your_groq_api_key_here
```

> Never commit `.env` to version control.

### 4. Launch the Streamlit demo UI

```bash
uv run streamlit run app.py
```

Open the local URL shown in your terminal (usually `http://localhost:8501`).

---

## Example Run

1. Select a scenario (for example `vpn_service_stopped`) and submit an incident such as "VPN won't connect".
2. The agent retrieves the relevant SOP and policy, then runs the read-only checks.
3. The UI shows ranked root causes with confidence, evidence for and against, and citations.
4. The agent proposes `restart_vpn_service` and pauses.
5. Click **Approve** or **Reject**.
   - **Approve:** the fix runs, diagnostics are re-run, and the incident ends as `CLOSED_VERIFIED` if the service recovered.
   - **Reject** or failed verification: the incident ends as `ESCALATED` with an evidence summary.
6. Inspect the full trace in `logs/<incident_id>.json`.

---

## Limitations (Phase 1)

- The environment is simulated and deterministic; only two fault scenarios are implemented.
- Only one restricted remediation tool is available.
- Checkpointing uses in-memory `MemorySaver`, so paused incidents are not persisted across restarts.
- No baseline comparison or large-scale evaluation yet.
- Results depend on the external LLM API (Groq) being reachable.

---

## Planned Work (Phase 2)

- More scenarios: account lockout, DNS misconfiguration, outdated VPN client, ambiguous cases.
- More remediation tools and an explicit policy table (allowed / needs approval / forbidden).
- Evaluation against fixed-step and RAG-only baselines: diagnosis accuracy, verification rate, unauthorized-action prevention, tool calls, latency.
- Persistent incident history and a feedback loop that reuses verified incidents in retrieval.
- Separate Employee Portal and IT Support Dashboard.

---

## Team

| Name | Roll No. |
|---|---|
| Harleen Kaur | 23117012 |
| Ramanjot Singh | 23117030 |
| Stanzin Druksel | 23103141 |

**Mentor:** Dr. Rajneesh Rani, Associate Professor, Dept. of Computer Science and Engineering, Dr. B R Ambedkar NIT Jalandhar

---

## References

- Lewis et al. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks.* <https://arxiv.org/abs/2005.11401>
- LangGraph Documentation: Persistence and Human-in-the-Loop. <https://docs.langchain.com/oss/python/langgraph/persistence>
- NIST (2023). *Artificial Intelligence Risk Management Framework (AI RMF 1.0).* <https://doi.org/10.6028/NIST.AI.100-1>
- Microsoft OpenRCA, Root-Cause Analysis Benchmark. <https://microsoft.github.io/OpenRCA/>
- Microsoft Learn, Windows Networking Troubleshooting. <https://learn.microsoft.com/en-us/troubleshoot/windows-server/networking/troubleshoot-tcp-ip-communication-guidance>
