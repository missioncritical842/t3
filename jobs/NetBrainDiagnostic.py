"""Diagnostic job to investigate why only AWS devices appear in NetBrain API."""

from __future__ import annotations

import json

import requests
import urllib3

from nautobot.apps.jobs import Job, StringVar, register_jobs

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class NetBrainDiagnostic(Job):
    """Deep diagnostic: investigate device visibility in NetBrain API."""

    class Meta:
        name = "NetBrain: API Diagnostic"
        description = "Investigates why only AWS devices appear. Tests domain, API versions, sites, device groups."
        commit_default = False
        has_sensitive_variables = True

    host = StringVar(default="https://10.134.98.133")
    username = StringVar(default="nautobotapi")
    password = StringVar(default="", required=False)
    client_id = StringVar(default="", required=False)
    client_secret = StringVar(default="", required=False)

    def run(self, host="", username="", password="", client_id="", client_secret="", **kwargs):
        host = (host or "").rstrip("/")
        V1 = "/ServicesAPI/API/V1"

        # --- Login ---
        token = self._login(host, V1, username, password, client_id, client_secret)
        if not token:
            return "FAILED"
        h = {"Token": token, "Content-Type": "application/json"}

        try:
            # ============================================================
            # TEST 1: Verify domain context
            # ============================================================
            self.logger.info("=" * 60)
            self.logger.info("TEST 1: Domain context")
            self.logger.info("=" * 60)

            # Get tenant/domain IDs
            tid, did, tname, dname = self._get_tenant_domain_ids(host, V1, h)
            self.logger.info("Tenant: %s (%s)", tname, tid)
            self.logger.info("Domain: %s (%s)", dname, did)

            # Set domain
            if tid and did:
                r = requests.put(f"{host}{V1}/Session/CurrentDomain",
                                 json={"tenantId": tid, "domainId": did},
                                 headers=h, verify=False, timeout=15)
                self.logger.info("Set domain: HTTP %s - %s", r.status_code, r.text[:200])

            # Verify: try to get current domain info
            for method in ["GET", "POST"]:
                try:
                    r = requests.request(method, f"{host}{V1}/Session/CurrentDomain",
                                         headers=h, verify=False, timeout=10, json={})
                    self.logger.info("%s CurrentDomain: HTTP %s - %s", method, r.status_code, r.text[:300])
                except Exception as e:
                    self.logger.info("%s CurrentDomain: %s", method, e)

            # ============================================================
            # TEST 2: Device count and last page check
            # ============================================================
            self.logger.info("=" * 60)
            self.logger.info("TEST 2: Total device count")
            self.logger.info("=" * 60)

            # Scan across the full inventory range
            for skip_val in [8000, 9000, 10000, 12000, 15000, 20000, 25000, 30000, 40000, 50000]:
                r = requests.get(f"{host}{V1}/CMDB/Devices",
                                 params={"skip": skip_val, "limit": 10},
                                 headers=h, verify=False, timeout=15)
                if r.status_code == 200:
                    devs = r.json().get("devices", [])
                    types = {}
                    for d in devs:
                        st = d.get("subTypeName", "?")
                        types[st] = types.get(st, 0) + 1
                    self.logger.info("skip=%d: got %d devices, types: %s", skip_val, len(devs), types)
                else:
                    self.logger.info("skip=%d: HTTP %s - %s", skip_val, r.status_code, r.text[:200])

            # ============================================================
            # TEST 3: API V2 and V3
            # ============================================================
            self.logger.info("=" * 60)
            self.logger.info("TEST 3: API V2 and V3 endpoints")
            self.logger.info("=" * 60)

            for ver in ["V2", "V3"]:
                base = f"/ServicesAPI/API/{ver}"
                for endpoint in ["/CMDB/Devices", "/CMDB/Sites", "/CMDB/Domains"]:
                    url = f"{host}{base}{endpoint}"
                    try:
                        r = requests.get(url, params={"skip": 0, "limit": 10},
                                         headers=h, verify=False, timeout=10)
                        body = r.text[:300]
                        self.logger.info("%s %s: HTTP %s - %s", ver, endpoint, r.status_code, body)
                        if r.status_code == 200:
                            data = r.json()
                            devs = data.get("devices", [])
                            if devs:
                                types = set(d.get("subTypeName", "?") for d in devs[:10])
                                self.logger.info("  Device types: %s", types)
                    except Exception as e:
                        self.logger.info("%s %s: %s", ver, endpoint, e)

            # ============================================================
            # TEST 4: Device groups
            # ============================================================
            self.logger.info("=" * 60)
            self.logger.info("TEST 4: Device groups")
            self.logger.info("=" * 60)

            for endpoint in ["/CMDB/DeviceGroups", "/CMDB/DeviceTypes",
                             "/CMDB/Devices/DeviceTypes"]:
                url = f"{host}{V1}{endpoint}"
                try:
                    r = requests.get(url, headers=h, verify=False, timeout=10)
                    self.logger.info("GET %s: HTTP %s - %s", endpoint, r.status_code, r.text[:500])
                except Exception as e:
                    self.logger.info("GET %s: %s", endpoint, e)

            # ============================================================
            # TEST 5: Site tree exploration
            # ============================================================
            self.logger.info("=" * 60)
            self.logger.info("TEST 5: Site tree")
            self.logger.info("=" * 60)

            # Try various site endpoints and methods
            site_endpoints = [
                ("GET", "/CMDB/Sites", {}),
                ("POST", "/CMDB/Sites", {}),
                ("GET", "/CMDB/Sites/ChildSites", {}),
                ("POST", "/CMDB/Sites/ChildSites", {"sitePath": "My Network"}),
                ("POST", "/CMDB/Sites/ChildSites", {"sitePath": ""}),
                ("GET", "/CMDB/Sites/SiteInfo", {"sitePath": "My Network"}),
                ("POST", "/CMDB/Sites/SiteInfo", {"sitePath": "My Network"}),
                ("GET", "/CMDB/Sites/SiteDevices", {"sitePath": "My Network"}),
                ("POST", "/CMDB/Sites/SiteDevices", {"sitePath": "My Network"}),
            ]
            for method, path, body in site_endpoints:
                url = f"{host}{V1}{path}"
                try:
                    if method == "GET":
                        r = requests.get(url, params=body, headers=h, verify=False, timeout=10)
                    else:
                        r = requests.post(url, json=body, headers=h, verify=False, timeout=10)
                    self.logger.info("%s %s %s: HTTP %s - %s",
                                     method, path, body or "", r.status_code, r.text[:500])
                except Exception as e:
                    self.logger.info("%s %s: %s", method, path, e)

            # ============================================================
            # TEST 6: Search/filter devices by vendor
            # ============================================================
            self.logger.info("=" * 60)
            self.logger.info("TEST 6: Filtered device queries")
            self.logger.info("=" * 60)

            # Try various filter approaches
            filter_tests = [
                {"skip": 0, "limit": 10, "ip": "10."},
                {"skip": 0, "limit": 10, "type": "Router"},
                {"skip": 0, "limit": 10, "type": "Switch"},
                {"skip": 0, "limit": 10, "type": "Firewall"},
                {"skip": 0, "limit": 10, "subTypeName": "Cisco Router"},
            ]
            for params in filter_tests:
                try:
                    r = requests.get(f"{host}{V1}/CMDB/Devices",
                                     params=params, headers=h, verify=False, timeout=10)
                    if r.status_code == 200:
                        devs = r.json().get("devices", [])
                        types = set(d.get("subTypeName", "?") for d in devs)
                        self.logger.info("Filter %s: %d devices, types: %s", params, len(devs), types)
                    else:
                        self.logger.info("Filter %s: HTTP %s - %s", params, r.status_code, r.text[:200])
                except Exception as e:
                    self.logger.info("Filter %s: %s", params, e)

            # Try POST-based search
            search_bodies = [
                {"hostname": "*"},
                {"vendor": "Cisco"},
                {"vendor": "Arista"},
            ]
            for body in search_bodies:
                try:
                    r = requests.post(f"{host}{V1}/CMDB/Devices/Search",
                                      json=body, headers=h, verify=False, timeout=10)
                    self.logger.info("POST Search %s: HTTP %s - %s", body, r.status_code, r.text[:300])
                except Exception as e:
                    self.logger.info("POST Search %s: %s", body, e)

            # ============================================================
            # TEST 7: Check user privileges / accessible domains
            # ============================================================
            self.logger.info("=" * 60)
            self.logger.info("TEST 7: User / privilege info")
            self.logger.info("=" * 60)

            priv_endpoints = [
                "/CMDB/Users",
                "/CMDB/Roles",
                "/Session/UserInfo",
                "/System/UserSettings",
            ]
            for ep in priv_endpoints:
                try:
                    r = requests.get(f"{host}{V1}{ep}", headers=h, verify=False, timeout=10)
                    self.logger.info("GET %s: HTTP %s - %s", ep, r.status_code, r.text[:500])
                except Exception as e:
                    self.logger.info("GET %s: %s", ep, e)

        finally:
            requests.delete(f"{host}{V1}/Session", headers=h, verify=False, timeout=10)
            self.logger.info("Logged out.")

        return "DONE"

    def _login(self, host, base, username, password, client_id, client_secret):
        body = {"username": username, "password": password}
        if client_id:
            body["authentication_id"] = client_id
        if client_secret:
            body["client_secret"] = client_secret
        try:
            r = requests.post(f"{host}{base}/Session", json=body,
                              headers={"Content-Type": "application/json"},
                              verify=False, timeout=15)
            if r.status_code == 200:
                token = r.json().get("token", "")
                if token:
                    self.logger.info("Login OK")
                    return token
            self.logger.error("Login failed: HTTP %s - %s", r.status_code, r.text[:300])
        except Exception as e:
            self.logger.error("Login failed: %s", e)
        return None

    def _get_tenant_domain_ids(self, host, base, headers):
        tid = did = tname = dname = ""
        try:
            r = requests.get(f"{host}{base}/CMDB/Tenants", headers=headers, verify=False, timeout=10)
            if r.status_code == 200:
                tenants = r.json().get("tenants", [])
                if tenants:
                    tid = tenants[0].get("tenantId", "")
                    tname = tenants[0].get("tenantName", "")
                    r2 = requests.get(f"{host}{base}/CMDB/Domains",
                                      params={"tenantId": tid},
                                      headers=headers, verify=False, timeout=10)
                    if r2.status_code == 200:
                        domains = r2.json().get("domains", [])
                        if domains:
                            did = domains[0].get("domainId", "")
                            dname = domains[0].get("domainName", "")
        except Exception:
            pass
        return tid, did, tname, dname


register_jobs(NetBrainDiagnostic)
