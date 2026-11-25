from datetime import datetime
import streamlit as st

from src.it_incident_agent.agent import (
    AgentState,
    build_graph,
    env,
    save_audit_log,
)

st.set_page_config(page_title="Evidence-Driven IT Incident Agent", layout="wide")
st.title("Evidence-Driven Agentic AI — IT Incident Diagnosis")
st.caption("Phase 1 Prototype: Retrieval → Diagnostics → Ranked Hypotheses → Human Approval → Verified Resolution")

# --- Sidebar: Scenario Control ---
with st.sidebar:
    st.header("Simulator Controls")
    scenario = st.selectbox(
        "Select Fault Scenario",
        options=["vpn_service_stopped", "auth_expired"],
        format_func=lambda x: "VPN Service Stopped (Resolvable)" if x == "vpn_service_stopped" else "Auth Token Expired (Needs Escalation)",
    )
    if st.button("Reset Demo", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# --- Initialize Session State ---
if "graph" not in st.session_state:
    st.session_state.graph = None
if "config" not in st.session_state:
    st.session_state.config = None
if "state" not in st.session_state:
    st.session_state.state = None
if "stage" not in st.session_state:
    st.session_state.stage = "idle"  # idle -> awaiting_approval -> done
if "log_path" not in st.session_state:
    st.session_state.log_path = None

# --- Incident Intake ---
incident_text = st.text_input(
    "Report an IT Incident:",
    value="My corporate VPN is failing to connect since this morning.",
)

if st.button("Start Investigation", type="primary"):
    env.reset(scenario)
    graph = build_graph()
    incident_id = f"INC-{datetime.now().strftime('%H%M%S')}"
    config = {"configurable": {"thread_id": incident_id}}

    initial_state: AgentState = {
        "incident_id": incident_id,
        "incident_text": incident_text,
        "retrieved_docs": [],
        "tool_outputs": {},
        "diagnosis": None,
        "approval_decision": None,
        "remediation_result": None,
        "verification_result": None,
        "final_status": None,
        "investigation_log": [],
    }

    with st.spinner("Retrieving SOPs, running diagnostics, and ranking root causes..."):
        paused_state = graph.invoke(initial_state, config=config)

    st.session_state.graph = graph
    st.session_state.config = config
    st.session_state.state = paused_state
    st.session_state.stage = "awaiting_approval"
    st.session_state.log_path = None
    st.rerun()

# --- Main Split-Screen Dashboard ---
if st.session_state.state:
    state = st.session_state.state
    col_left, col_right = st.columns([1, 1.2], gap="large")

    # LEFT COLUMN: Timeline & Evidence
    with col_left:
        st.subheader(f"Investigation Timeline ({state['incident_id']})")
        for entry in state["investigation_log"]:
            st.markdown(f"- `{entry}`")

        with st.expander("Diagnostic Tool Outputs (Simulator)", expanded=False):
            st.json(state["tool_outputs"])

        with st.expander("Retrieved Knowledge Base Chunks (FAISS)", expanded=False):
            for doc in state["retrieved_docs"]:
                st.markdown(f"**{doc['source']}** (distance: `{doc['score']}`)")
                st.caption(doc["content"])
                st.divider()

    # RIGHT COLUMN: Ranked Root Causes & Approval Panel
    with col_right:
        diag = state["diagnosis"]
        st.subheader("Ranked Root Causes")

        for i, h in enumerate(diag["ranked_hypotheses"], 1):
            with st.container(border=True):
                st.markdown(f"**{i}. {h['cause']}** — Confidence: `{int(h['confidence'] * 100)}%`")
                st.progress(min(max(float(h["confidence"]), 0.0), 1.0))
                st.markdown(f"**Supporting:** {', '.join(h['supporting_evidence']) or 'None'}")
                st.markdown(f"**Conflicting:** {', '.join(h['conflicting_evidence']) or 'None'}")
                st.caption(f"Citations: {', '.join(h['citations'])}")

        st.subheader("Authorization & Resolution Panel")
        with st.container(border=True):
            st.markdown(f"**Proposed Action:** `{diag['recommended_action']}`")
            st.markdown(f"**Requires Admin Approval:** `{diag['requires_approval']}`")
            st.markdown(f"**Reasoning:** {diag['reasoning']}")

            if st.session_state.stage == "awaiting_approval":
                btn_col1, btn_col2 = st.columns(2)
                if btn_col1.button("Approve & Execute", type="primary", use_container_width=True):
                    with st.spinner("Executing remediation and verifying recovery..."):
                        st.session_state.graph.update_state(
                            st.session_state.config, {"approval_decision": "approve"}
                        )
                        final_state = st.session_state.graph.invoke(None, config=st.session_state.config)
                        st.session_state.state = final_state
                        st.session_state.log_path = str(save_audit_log(final_state))
                        st.session_state.stage = "done"
                        st.rerun()

                if btn_col2.button("Reject & Escalate", use_container_width=True):
                    with st.spinner("Escalating incident to Level-2 IT Support..."):
                        st.session_state.graph.update_state(
                            st.session_state.config, {"approval_decision": "reject"}
                        )
                        final_state = st.session_state.graph.invoke(None, config=st.session_state.config)
                        st.session_state.state = final_state
                        st.session_state.log_path = str(save_audit_log(final_state))
                        st.session_state.stage = "done"
                        st.rerun()

            elif st.session_state.stage == "done":
                status = state["final_status"]
                if status == "CLOSED_VERIFIED":
                    st.success("Status: CLOSED_VERIFIED — Post-remediation check confirmed VPN is connected.")
                else:
                    st.warning("Status: ESCALATED — Handed off to Level-2 IT Support with full evidence trail.")

                if state.get("verification_result"):
                    st.caption(f"Verification Check Output: {state['verification_result']}")
                if st.session_state.log_path:
                    st.caption(f"Audit log saved to `{st.session_state.log_path}`")