import json
from datetime import datetime
from pathlib import Path
from typing import TypedDict, List, Dict, Any, Optional, Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from src.it_incident_agent.simulator import SimulatedITEnv
from src.it_incident_agent.rag import retrieve_evidence

load_dotenv()

GROQ_MODEL = "openai/gpt-oss-120b"
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)


# --- 1. Structured Output Schemas ---

class Hypothesis(BaseModel):
    cause: str = Field(description="Short name of the potential root cause")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")
    supporting_evidence: List[str] = Field(description="Tool outputs or doc facts supporting this cause")
    conflicting_evidence: List[str] = Field(description="Facts that weaken or rule out this cause")
    citations: List[str] = Field(description="Source filenames cited, e.g., vpn_troubleshooting_sop.md")


class DiagnosisReport(BaseModel):
    ranked_hypotheses: List[Hypothesis] = Field(description="Hypotheses ordered from most likely to least likely")
    recommended_action: Literal["restart_vpn_service", "escalate"] = Field(
        description="Must be exactly 'restart_vpn_service' if VPN daemon is stopped, otherwise 'escalate'"
    )
    requires_approval: bool = Field(description="True if the policy marks this action as RESTRICTED")
    reasoning: str = Field(description="Brief summary explaining why this action is justified")


# --- 2. Shared Graph State ---

class AgentState(TypedDict):
    incident_id: str
    incident_text: str
    retrieved_docs: List[Dict[str, Any]]
    tool_outputs: Dict[str, Any]
    diagnosis: Optional[Dict[str, Any]]
    approval_decision: Optional[str]        # "approve" or "reject"
    remediation_result: Optional[Dict[str, Any]]
    verification_result: Optional[Dict[str, Any]]
    final_status: Optional[str]             # "CLOSED_VERIFIED" or "ESCALATED"
    investigation_log: List[str]


# --- 3. Initialize Simulator & LLM ---

env = SimulatedITEnv(scenario="vpn_service_stopped")
llm = ChatGroq(model=GROQ_MODEL, temperature=0)


def log_step(logs: List[str], message: str) -> List[str]:
    timestamp = datetime.now().strftime("%H:%M:%S")
    return logs + [f"[{timestamp}] {message}"]


# --- 4. Graph Nodes ---

def retrieve_docs_node(state: AgentState) -> Dict[str, Any]:
    docs = retrieve_evidence(state["incident_text"], k=5)
    sources = sorted(set(d["source"] for d in docs))  # Deduplicates filenames in the log
    logs = log_step(state["investigation_log"], f"Retrieved {len(docs)} docs: {', '.join(sources)}")
    return {"retrieved_docs": docs, "investigation_log": logs}


def run_diagnostics_node(state: AgentState) -> Dict[str, Any]:
    net = env.check_network_status()
    auth = env.check_account_auth()
    vpn = env.check_vpn_status()

    outputs = {"network": net, "auth": auth, "vpn": vpn}
    logs = log_step(
        state["investigation_log"],
        f"Ran diagnostics -> network_up={net['network_up']}, auth_valid={auth['auth_token_valid']}, vpn_status={vpn['vpn_service_status']}",
    )
    return {"tool_outputs": outputs, "investigation_log": logs}


def rank_root_causes_node(state: AgentState) -> Dict[str, Any]:
    docs_text = "\n\n".join(
        f"]\n{d['content']}" for d in state["retrieved_docs"]
    )

    prompt = f"""You are an evidence-driven IT Incident Diagnosis AI.
Analyze the user's incident using ONLY the retrieved SOPs/policies and diagnostic tool outputs below.

USER INCIDENT:
{state['incident_text']}

RETRIEVED KNOWLEDGE BASE:
{docs_text}

DIAGNOSTIC TOOL OUTPUTS:
{state['tool_outputs']}

Instructions:
1. Rank at least 2 possible root causes from most likely to least likely.
2. Cite the exact source filenames (e.g., vpn_troubleshooting_sop.md, authorization_policy.md).
3. Follow the authorization policy strictly: if the recommended action is RESTRICTED, set requires_approval=True.
"""

    structured_llm = llm.with_structured_output(DiagnosisReport)
    report: DiagnosisReport = structured_llm.invoke(prompt)

    top_cause = report.ranked_hypotheses[0].cause if report.ranked_hypotheses else "Unknown"
    logs = log_step(
        state["investigation_log"],
        f"Diagnosis complete -> Top cause: '{top_cause}' | Proposed action: {report.recommended_action} (Approval required: {report.requires_approval})",
    )
    return {"diagnosis": report.model_dump(), "investigation_log": logs}


def approval_gate_node(state: AgentState) -> Dict[str, Any]:
    """Graph pauses right BEFORE this node. When resumed, it logs the admin's decision."""
    decision = state.get("approval_decision", "reject")
    logs = log_step(state["investigation_log"], f"Human admin decision received: {decision.upper()}")
    return {"investigation_log": logs}


def remediate_node(state: AgentState) -> Dict[str, Any]:
    """Executes the approved restricted action on the simulator."""
    action = state["diagnosis"]["recommended_action"]

    if action == "restart_vpn_service":
        result = env.restart_vpn_service()
    else:
        result = {"action_status": "skipped", "message": f"Unsupported action: {action}"}

    logs = log_step(state["investigation_log"], f"Executed remediation '{action}' -> {result['message']}")
    return {"remediation_result": result, "investigation_log": logs}


def verify_node(state: AgentState) -> Dict[str, Any]:
    """Re-runs VPN diagnostics to prove the service actually recovered."""
    check = env.check_vpn_status()
    recovered = check["vpn_connected"] is True

    status_msg = "VERIFIED: VPN is now connected." if recovered else "FAILED: VPN is still disconnected."
    logs = log_step(state["investigation_log"], f"Post-remediation verification -> {status_msg}")
    return {"verification_result": check, "investigation_log": logs}


def close_ticket_node(state: AgentState) -> Dict[str, Any]:
    logs = log_step(state["investigation_log"], "Ticket CLOSED (verified recovery).")
    return {"final_status": "CLOSED_VERIFIED", "investigation_log": logs}


def escalate_node(state: AgentState) -> Dict[str, Any]:
    logs = log_step(state["investigation_log"], "Incident ESCALATED to Level-2 IT Support with evidence summary.")
    return {"final_status": "ESCALATED", "investigation_log": logs}


# --- 5. Conditional Routing Functions ---

def route_after_approval(state: AgentState) -> str:
    action = state["diagnosis"].get("recommended_action")
    if state.get("approval_decision") == "approve" and action == "restart_vpn_service":
        return "remediate"
    return "escalate"


def route_after_verification(state: AgentState) -> str:
    if state.get("verification_result", {}).get("vpn_connected") is True:
        return "close_ticket"
    return "escalate"


# --- 6. Build & Compile the Graph (with HITL Checkpointing) ---

def build_graph():
    builder = StateGraph(AgentState)

    builder.add_node("retrieve_docs", retrieve_docs_node)
    builder.add_node("run_diagnostics", run_diagnostics_node)
    builder.add_node("rank_root_causes", rank_root_causes_node)
    builder.add_node("approval_gate", approval_gate_node)
    builder.add_node("remediate", remediate_node)
    builder.add_node("verify", verify_node)
    builder.add_node("close_ticket", close_ticket_node)
    builder.add_node("escalate", escalate_node)

    builder.add_edge(START, "retrieve_docs")
    builder.add_edge("retrieve_docs", "run_diagnostics")
    builder.add_edge("run_diagnostics", "rank_root_causes")
    builder.add_edge("rank_root_causes", "approval_gate")

    builder.add_conditional_edges(
        "approval_gate",
        route_after_approval,
        {"remediate": "remediate", "escalate": "escalate"},
    )
    builder.add_edge("remediate", "verify")
    builder.add_conditional_edges(
        "verify",
        route_after_verification,
        {"close_ticket": "close_ticket", "escalate": "escalate"},
    )
    builder.add_edge("close_ticket", END)
    builder.add_edge("escalate", END)

    memory = MemorySaver()
    # Pause right before approval_gate so a human can review & approve/reject
    return builder.compile(checkpointer=memory, interrupt_before=["approval_gate"])


def save_audit_log(state: Dict[str, Any]) -> Path:
    """Saves the full investigation trace to logs/<incident_id>.json."""
    out_file = LOGS_DIR / f"{state['incident_id']}.json"
    out_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return out_file


# --- Interactive Terminal Test ---
if __name__ == "__main__":
    env.reset("vpn_service_stopped")
    graph = build_graph()

    incident_id = f"INC-{datetime.now().strftime('%H%M%S')}"
    config = {"configurable": {"thread_id": incident_id}}

    initial_state: AgentState = {
        "incident_id": incident_id,
        "incident_text": "My corporate VPN is failing to connect since this morning.",
        "retrieved_docs": [],
        "tool_outputs": {},
        "diagnosis": None,
        "approval_decision": None,
        "remediation_result": None,
        "verification_result": None,
        "final_status": None,
        "investigation_log": [],
    }

    # Step 1: Run until the HITL pause
    print(f"\n--- Starting Investigation ({incident_id}) ---")
    paused_state = graph.invoke(initial_state, config=config)

    diag = paused_state["diagnosis"]
    print("\n=== RANKED ROOT CAUSES ===")
    for i, h in enumerate(diag["ranked_hypotheses"], 1):
        print(f"{i}. {h['cause']} (Confidence: {h['confidence']}) | Citations: {h['citations']}")

    print("\n=== APPROVAL REQUIRED ===")
    print(f"Proposed Action: {diag['recommended_action']}")
    print(f"Reasoning:       {diag['reasoning']}")

    # Step 2: Ask the human admin in the terminal
    choice = input("\nType 'approve' to execute or 'reject' to escalate: ").strip().lower()
    decision = "approve" if choice == "approve" else "reject"

    # Step 3: Inject decision into graph state and resume
    graph.update_state(config, {"approval_decision": decision})
    final_state = graph.invoke(None, config=config)

    print("\n=== FINAL INVESTIGATION LOG ===")
    for entry in final_state["investigation_log"]:
        print(" ", entry)

    print(f"\nFinal Status: {final_state['final_status']}")
    log_path = save_audit_log(final_state)
    print(f"Audit log saved to: {log_path}")