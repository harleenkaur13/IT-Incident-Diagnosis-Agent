# POL-001: Internal IT Troubleshooting & Authorization Policy

## 1. Tool Classification & Safety Rules
- **SAFE (Read-Only Diagnostics):** `check_network_status`, `check_account_auth`, `check_vpn_status`. The AI agent may run these autonomously without human approval.
- **RESTRICTED (State-Changing Remediation):** `restart_vpn_service`. The AI agent MUST pause and request explicit human IT admin approval (`requires_approval = True`) before executing any restricted action.
- **ESCALATION RULE:** If human approval is rejected, or if no approved automated tool exists for the root cause (e.g., expired SSO/PRT token, firewall/NAT port blocks, or certificate errors), the agent MUST set `recommended_action = "escalate"` and hand off to Level-2 IT Support.

## 2. Internal Action Mapping
- **VPN Daemon Stopped (`vpn_service_status == "stopped"` / `ERR_VPN_DAEMON_NOT_RUNNING`):**
  - Recommended Action: `restart_vpn_service` (Requires Admin Approval).
  - Mandatory Verification: Re-run `check_vpn_status` and confirm `vpn_connected == True` before closing.
- **Expired Auth / SSO Token (`auth_token_valid == False` / `ERR_AUTH_TOKEN_EXPIRED`):**
  - Recommended Action: `escalate` (User must refresh their Windows Primary Refresh Token / SSO session per Microsoft Entra guidance; restarting the VPN service will NOT fix this).