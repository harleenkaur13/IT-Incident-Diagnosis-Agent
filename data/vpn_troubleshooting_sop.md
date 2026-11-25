# SOP-001: Corporate VPN Connection Failure Troubleshooting

## Symptoms
User reports VPN client fails to connect, times out, or shows connection errors.

## Diagnostic Steps (Run in Order)
1. Check Network & DNS: Verify `network_up` and `dns_resolving` are True. If False, escalate to Network Ops.
2. Check Account & Auth: Verify `account_locked` is False and `auth_token_valid` is True. If `auth_token_valid` is False, user must re-authenticate via SSO portal.
3. Check VPN Service: Verify `vpn_service_status` is `running`. If `stopped` or `ERR_VPN_DAEMON_NOT_RUNNING` is present, the local VPN daemon has crashed.

## Remediation
- For `ERR_VPN_DAEMON_NOT_RUNNING` (service stopped): Execute `restart_vpn_service`.
- Post-Remediation Verification: Always re-run `check_vpn_status` and confirm `vpn_connected` is True before closing the ticket.