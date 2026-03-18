"""NetBrain API Connectivity Test job for Nautobot.

Tests authentication and basic API reachability to NetBrain.
Logs status and headers only -- no data written to Nautobot.
"""

from __future__ import annotations

import requests
import urllib3

from nautobot.apps.jobs import Job, StringVar, register_jobs

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

NETBRAIN_API_BASE = "/ServicesAPI/API/V1"


class NetBrainConnectivityTest(Job):
    """Test auth and connectivity to the NetBrain REST API."""

    class Meta:
        name = "NetBrain: Connectivity Test"
        description = (
            "Test authentication and API reachability for NetBrain. "
            "Logs HTTP status and response headers only -- no data written."
        )
        commit_default = False
        has_sensitive_variables = True

    host = StringVar(
        label="NetBrain Host",
        description="Base URL or IP (e.g. https://10.134.98.133)",
        default="https://10.134.98.133",  # DNS (netbrain.crbgf.net) may not resolve from Nautobot cloud
    )
    username = StringVar(
        label="Username",
        default="nautobotapi",
    )
    password = StringVar(
        label="Password",
        description="Or set NETBRAIN_PASSWORD env var",
        default="aB1psTV?veX5dPBf@jx%kese56RB",
        required=False,
    )
    client_id = StringVar(
        label="Authentication ID (Client ID)",
        description="Or set NETBRAIN_CLIENT_ID env var",
        default="lpf4oqee-3dmfvrwg",
        required=False,
    )
    client_secret = StringVar(
        label="Client Secret",
        description="Or set NETBRAIN_CLIENT_SECRET env var",
        default="uBZY15clyPuV9YhuTNkp3iCxKDbXwqjA",
        required=False,
    )

    def run(self, host="", username="", password="", client_id="", client_secret="", **kwargs):
        import os
        host = (host or "").rstrip("/")
        username = (username or "").strip() or os.environ.get("NETBRAIN_USERNAME", "nautobotapi")
        password = (password or "").strip() or os.environ.get("NETBRAIN_PASSWORD", "")
        client_id = (client_id or "").strip() or os.environ.get("NETBRAIN_CLIENT_ID", "")
        client_secret = (client_secret or "").strip() or os.environ.get("NETBRAIN_CLIENT_SECRET", "")
        login_url = f"{host}{NETBRAIN_API_BASE}/Session"

        # --- Step 1: Login ---
        self.logger.info("Attempting login to %s ...", login_url)
        body = {
            "username": username,
            "password": password,
        }
        if client_id:
            body["authentication_id"] = client_id
        if client_secret:
            body["client_secret"] = client_secret

        try:
            resp = requests.post(
                login_url,
                json=body,
                headers={"Content-Type": "application/json"},
                verify=False,
                timeout=15,
            )
        except requests.exceptions.ConnectTimeout:
            self.logger.error("Connection TIMED OUT -- host not reachable.")
            return
        except requests.exceptions.ConnectionError as exc:
            self.logger.error("Connection FAILED: %s", exc)
            return

        self.logger.info("Login HTTP %s", resp.status_code)
        self.logger.info("Response headers: %s", dict(resp.headers))

        if resp.status_code != 200:
            self.logger.error("Login failed. Body: %s", resp.text[:500])
            return

        data = resp.json()
        token = data.get("token", "")
        if not token:
            self.logger.error("No token in response. Body: %s", data)
            return

        self.logger.info("Login SUCCESS -- token starts with: %s...", token[:12])

        # --- Step 2: Product Version (lightweight read) ---
        version_url = f"{host}{NETBRAIN_API_BASE}/System/ProductVersion"
        self.logger.info("Fetching product version from %s ...", version_url)

        try:
            resp2 = requests.get(
                version_url,
                headers={"Token": token, "Content-Type": "application/json"},
                verify=False,
                timeout=15,
            )
            self.logger.info("Version HTTP %s", resp2.status_code)
            if resp2.status_code == 200:
                self.logger.info("Product version: %s", resp2.json())
            else:
                self.logger.warning("Version check returned: %s", resp2.text[:300])
        except Exception as exc:
            self.logger.warning("Version check failed: %s", exc)

        # --- Step 3: Logout ---
        logout_url = f"{host}{NETBRAIN_API_BASE}/Session"
        self.logger.info("Logging out...")
        try:
            requests.delete(
                logout_url,
                headers={"Token": token, "Content-Type": "application/json"},
                verify=False,
                timeout=10,
            )
            self.logger.info("Logout complete.")
        except Exception as exc:
            self.logger.warning("Logout failed: %s", exc)

        self.logger.info("NetBrain connectivity test PASSED.")
        return "SUCCESS"


register_jobs(NetBrainConnectivityTest)
