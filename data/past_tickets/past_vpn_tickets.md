# Historical Resolved VPN Incidents

## Ticket #INC-8821
- Symptom: Employee could not connect to corporate VPN after laptop woke from sleep.
- Evidence: Network up (True), Auth valid (True), VPN service status was `stopped` with `ERR_VPN_DAEMON_NOT_RUNNING`.
- Resolution: Admin approved `restart_vpn_service`. Verification confirmed `vpn_connected: True`. Ticket closed.

## Ticket #INC-8904
- Symptom: VPN failing to connect since morning login.
- Evidence: Network up (True), VPN service running, but `auth_token_valid` was False (`ERR_AUTH_TOKEN_EXPIRED`).
- Resolution: Escalated to user/IT to refresh SSO token. Restarting VPN alone did not fix the issue.