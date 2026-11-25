# POL-004: IT Remediation Authorization Policy

## Read-Only Diagnostic Tools
Tools that only inspect system state (`check_network_status`, `check_account_auth`, `check_vpn_status`) are SAFE and may be executed autonomously by the AI agent without human approval.

## Restricted Remediation Actions
Any action that modifies system state or restarts services (`restart_vpn_service`, `unlock_user_account`) is RESTRICTED.
- The AI agent MUST pause and request explicit human IT admin approval before executing a restricted action.
- If approval is rejected, the agent must NOT execute the action and must escalate the incident to Level-2 IT Support.