from datetime import datetime
from typing import Dict, Any


class SimulatedITEnv:
    """
    A simple, deterministic IT environment for simulating VPN incidents.
    Holds the current machine/network state and exposes read/write tools.
    """

    def __init__(self, scenario: str = "vpn_service_stopped"):
        self.scenario = scenario
        self.state: Dict[str, Any] = {}
        self.reset(scenario)

    def reset(self, scenario: str = "vpn_service_stopped") -> None:
        """Resets the environment to a known broken state for testing/demos."""
        self.scenario = scenario

        if scenario == "vpn_service_stopped":
            # Primary Demo Scenario: Internet & Auth are fine, but the VPN daemon crashed.
            self.state = {
                "user_id": "emp_1042",
                "network_up": True,
                "dns_resolving": True,
                "auth_token_valid": True,
                "account_locked": False,
                "vpn_service_status": "stopped",   # <-- Root cause
                "vpn_connected": False,
                "last_error": "ERR_VPN_DAEMON_NOT_RUNNING",
            }
        elif scenario == "auth_expired":
            # Secondary Scenario: VPN service is running, but auth token expired.
            self.state = {
                "user_id": "emp_1042",
                "network_up": True,
                "dns_resolving": True,
                "auth_token_valid": False,         # <-- Root cause
                "account_locked": False,
                "vpn_service_status": "running",
                "vpn_connected": False,
                "last_error": "ERR_AUTH_TOKEN_EXPIRED",
            }
        else:
            raise ValueError(f"Unknown scenario: {scenario}")

    # --- READ TOOLS (Safe Diagnostics) ---

    def check_network_status(self) -> Dict[str, Any]:
        """Checks basic internet connectivity and DNS resolution."""
        return {
            "tool": "check_network_status",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "network_up": self.state["network_up"],
            "dns_resolving": self.state["dns_resolving"],
        }

    def check_account_auth(self) -> Dict[str, Any]:
        """Checks if the user's account is locked or if their SSO token is expired."""
        return {
            "tool": "check_account_auth",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "user_id": self.state["user_id"],
            "account_locked": self.state["account_locked"],
            "auth_token_valid": self.state["auth_token_valid"],
        }

    def check_vpn_status(self) -> Dict[str, Any]:
        """Checks the VPN client service status and active tunnel connection."""
        return {
            "tool": "check_vpn_status",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "vpn_service_status": self.state["vpn_service_status"],
            "vpn_connected": self.state["vpn_connected"],
            "last_error": self.state["last_error"],
        }

    # --- WRITE TOOLS (Restricted Remediation Actions) ---

    def restart_vpn_service(self) -> Dict[str, Any]:
        """
        [RESTRICTED] Restarts the local VPN client daemon and attempts to reconnect.
        Only succeeds in connecting if network and auth are healthy.
        """
        self.state["vpn_service_status"] = "running"

        if self.state["network_up"] and self.state["auth_token_valid"] and not self.state["account_locked"]:
            self.state["vpn_connected"] = True
            self.state["last_error"] = None
            result = "VPN service restarted and tunnel reconnected successfully."
        else:
            self.state["vpn_connected"] = False
            result = "VPN service restarted, but connection still failed due to another issue."

        return {
            "tool": "restart_vpn_service",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "action_status": "executed",
            "message": result,
        }


# --- Quick Sanity Test ---
if __name__ == "__main__":
    env = SimulatedITEnv(scenario="vpn_service_stopped")

    print("1. Initial Diagnostics:")
    print("  Network:", env.check_network_status())
    print("  Auth:   ", env.check_account_auth())
    print("  VPN:    ", env.check_vpn_status())

    print("\n2. Applying Remediation (Restart VPN):")
    print("  Action: ", env.restart_vpn_service())

    print("\n3. Post-Remediation Verification:")
    print("  VPN:    ", env.check_vpn_status())