"""Deep dive: find every device type in NetBrain inventory."""

from __future__ import annotations

import json

import requests
import urllib3

from nautobot.apps.jobs import Job, StringVar, register_jobs

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

V1 = "/ServicesAPI/API/V1"


class NetBrainDeepDive(Job):
    """Exhaustive scan for all device types, device groups, and site devices."""

    class Meta:
        name = "NetBrain: Deep Dive"
        description = "Fine-grained scan of full inventory, device groups, and site-based queries."
        commit_default = False
        has_sensitive_variables = True

    host = StringVar(default="https://10.134.98.133")
    username = StringVar(default="nautobotapi")
    password = StringVar(default="", required=False)
    client_id = StringVar(default="", required=False)
    client_secret = StringVar(default="", required=False)

    def run(self, host="", username="", password="", client_id="", client_secret="", **kwargs):
        host = (host or "").rstrip("/")
        token = self._login(host, username, password, client_id, client_secret)
        if not token:
            return "FAILED"
        h = {"Token": token, "Content-Type": "application/json"}

        try:
            # Set domain
            tid, did = self._set_domain(host, h)

            # ============================================================
            # 1. Fine-grained device type scan (every 200 skip)
            # ============================================================
            self.logger.info("=" * 60)
            self.logger.info("PART 1: Fine-grained device type scan (every 200)")
            self.logger.info("=" * 60)

            all_types = {}
            skip = 0
            while skip < 26000:
                try:
                    r = requests.get(f"{host}{V1}/CMDB/Devices",
                                     params={"skip": skip, "limit": 100},
                                     headers=h, verify=False, timeout=15)
                    if r.status_code != 200:
                        break
                    devs = r.json().get("devices", [])
                    if not devs:
                        self.logger.info("  skip=%d: empty -- end of inventory", skip)
                        break
                    batch_types = {}
                    for d in devs:
                        st = d.get("subTypeName", "?")
                        batch_types[st] = batch_types.get(st, 0) + 1
                        all_types[st] = all_types.get(st, 0) + 1
                    # Only log when type changes or new types appear
                    self.logger.info("  skip=%d: %d devs, types: %s", skip, len(devs), batch_types)
                    if len(devs) < 100:
                        self.logger.info("  Partial page at skip=%d, end of range", skip)
                        break
                except Exception as e:
                    self.logger.info("  skip=%d: error %s", skip, e)
                    break
                skip += 200

            self.logger.info("COMPLETE DEVICE TYPE DISTRIBUTION:")
            for st, count in sorted(all_types.items(), key=lambda x: -x[1]):
                self.logger.info("  %s: %d", st, count)
            self.logger.info("TOTAL: %d devices", sum(all_types.values()))

            # ============================================================
            # 2. All device groups + query devices in BGP groups
            # ============================================================
            self.logger.info("=" * 60)
            self.logger.info("PART 2: Device groups")
            self.logger.info("=" * 60)

            try:
                r = requests.get(f"{host}{V1}/CMDB/DeviceGroups",
                                 headers=h, verify=False, timeout=15)
                if r.status_code == 200:
                    groups = r.json().get("deviceGroups", [])
                    self.logger.info("Total device groups: %d", len(groups))
                    for g in groups[:50]:
                        self.logger.info("  Group: %s (id: %s, type: %s)",
                                         g.get("name"), g.get("id"), g.get("type"))

                    # Try to get devices from first BGP group
                    bgp_groups = [g for g in groups if "BGP" in g.get("name", "")]
                    non_bgp = [g for g in groups if "BGP" not in g.get("name", "")]

                    if non_bgp:
                        self.logger.info("Non-BGP groups:")
                        for g in non_bgp[:20]:
                            self.logger.info("  %s", g.get("name"))

                    # Try to get devices from groups
                    for g in (bgp_groups[:3] + non_bgp[:3]):
                        gid = g.get("id", "")
                        gname = g.get("name", "")
                        # Try various endpoints to get group members
                        for endpoint in [
                            f"/CMDB/DeviceGroups/{gid}/Devices",
                            f"/CMDB/DeviceGroups/Devices",
                        ]:
                            try:
                                # GET with group id
                                r2 = requests.get(
                                    f"{host}{V1}{endpoint}",
                                    params={"groupId": gid, "limit": 10},
                                    headers=h, verify=False, timeout=10)
                                self.logger.info("  GET %s (group=%s): HTTP %s - %s",
                                                 endpoint, gname, r2.status_code, r2.text[:300])
                                if r2.status_code == 200:
                                    gdevs = r2.json().get("devices", [])
                                    if gdevs:
                                        for gd in gdevs[:5]:
                                            self.logger.info("    Device: %s (%s) - %s",
                                                             gd.get("name", "?"),
                                                             gd.get("subTypeName", "?"),
                                                             gd.get("mgmtIP", ""))
                                    break
                            except Exception as e:
                                self.logger.info("  GET %s: %s", endpoint, e)

                        # Also try POST
                        try:
                            r2 = requests.post(
                                f"{host}{V1}/CMDB/DeviceGroups/Devices",
                                json={"groupName": gname, "limit": 10},
                                headers=h, verify=False, timeout=10)
                            if r2.status_code == 200:
                                self.logger.info("  POST DeviceGroups/Devices (group=%s): %s",
                                                 gname, r2.text[:300])
                        except Exception:
                            pass
            except Exception as e:
                self.logger.error("Device groups error: %s", e)

            # ============================================================
            # 3. Site-based device queries
            # ============================================================
            self.logger.info("=" * 60)
            self.logger.info("PART 3: Devices by site")
            self.logger.info("=" * 60)

            # Get child sites of key locations
            site_paths = [
                "My Network",
                "My Network/DataCenter-AMER",
                "My Network/DataCenter-AMER/AM5",
                "My Network/DataCenter-AMER/AM5/AM5 - Data Center",
                "My Network/DataCenter-AMER/AM6",
                "My Network/DataCenter-EMEA",
                "My Network/CRBGF Branch Offices",
                "My Network/Auto Site/ACI",
            ]
            for sp in site_paths:
                # Get child sites
                try:
                    r = requests.get(f"{host}{V1}/CMDB/Sites/ChildSites",
                                     params={"sitePath": sp},
                                     headers=h, verify=False, timeout=10)
                    if r.status_code == 200:
                        children = r.json().get("sites", [])
                        child_names = [c.get("sitePath", "?") for c in children[:10]]
                        self.logger.info("ChildSites of '%s': %d children: %s",
                                         sp, len(children), child_names)
                    else:
                        self.logger.info("ChildSites of '%s': HTTP %s", sp, r.status_code)
                except Exception as e:
                    self.logger.info("ChildSites of '%s': %s", sp, e)

                # Try to get devices at this site
                for endpoint in ["/CMDB/Sites/Devices", "/CMDB/Sites/SiteDevices"]:
                    try:
                        r = requests.get(f"{host}{V1}{endpoint}",
                                         params={"sitePath": sp, "limit": 10},
                                         headers=h, verify=False, timeout=10)
                        if r.status_code == 200:
                            data = r.json()
                            devs = data.get("devices", data.get("data", []))
                            self.logger.info("GET %s '%s': %d devices", endpoint, sp, len(devs))
                            for d in (devs or [])[:5]:
                                if isinstance(d, dict):
                                    self.logger.info("    %s (%s) %s",
                                                     d.get("name", "?"),
                                                     d.get("subTypeName", d.get("deviceTypeName", "?")),
                                                     d.get("mgmtIP", ""))
                                else:
                                    self.logger.info("    %s", str(d)[:200])
                        elif r.status_code != 404:
                            self.logger.info("GET %s '%s': HTTP %s - %s",
                                             endpoint, sp, r.status_code, r.text[:200])
                    except Exception as e:
                        self.logger.info("GET %s '%s': %s", endpoint, sp, e)

            # ============================================================
            # 4. Try searching by hostname patterns
            # ============================================================
            self.logger.info("=" * 60)
            self.logger.info("PART 4: Device search by hostname")
            self.logger.info("=" * 60)

            # Try getting specific devices by hostname pattern
            test_hostnames = ["*cisco*", "*nexus*", "*arista*", "*switch*",
                              "*router*", "*fw*", "*firewall*", "*palo*",
                              "*asa*", "*core*", "*edge*", "*border*"]
            for hn in test_hostnames:
                try:
                    r = requests.get(f"{host}{V1}/CMDB/Devices",
                                     params={"hostname": hn, "limit": 10},
                                     headers=h, verify=False, timeout=10)
                    if r.status_code == 200:
                        devs = r.json().get("devices", [])
                        if devs:
                            types = set(d.get("subTypeName", "?") for d in devs)
                            names = [d.get("name", "?") for d in devs[:3]]
                            self.logger.info("hostname='%s': %d hits, types=%s, names=%s",
                                             hn, len(devs), types, names)
                        else:
                            self.logger.info("hostname='%s': 0 hits", hn)
                    else:
                        self.logger.info("hostname='%s': HTTP %s - %s",
                                         hn, r.status_code, r.text[:200])
                except Exception as e:
                    self.logger.info("hostname='%s': %s", hn, e)

        finally:
            requests.delete(f"{host}{V1}/Session", headers=h, verify=False, timeout=10)
            self.logger.info("Logged out.")

        return "DONE"

    def _login(self, host, username, password, client_id, client_secret):
        body = {"username": username, "password": password}
        if client_id:
            body["authentication_id"] = client_id
        if client_secret:
            body["client_secret"] = client_secret
        try:
            r = requests.post(f"{host}{V1}/Session", json=body,
                              headers={"Content-Type": "application/json"},
                              verify=False, timeout=15)
            if r.status_code == 200:
                token = r.json().get("token", "")
                if token:
                    self.logger.info("Login OK")
                    return token
            self.logger.error("Login failed: %s", r.text[:300])
        except Exception as e:
            self.logger.error("Login failed: %s", e)
        return None

    def _set_domain(self, host, headers):
        tid = did = ""
        try:
            r = requests.get(f"{host}{V1}/CMDB/Tenants", headers=headers, verify=False, timeout=10)
            if r.status_code == 200:
                t = r.json().get("tenants", [{}])[0]
                tid = t.get("tenantId", "")
                r2 = requests.get(f"{host}{V1}/CMDB/Domains",
                                  params={"tenantId": tid},
                                  headers=headers, verify=False, timeout=10)
                if r2.status_code == 200:
                    d = r2.json().get("domains", [{}])[0]
                    did = d.get("domainId", "")
            if tid and did:
                r3 = requests.put(f"{host}{V1}/Session/CurrentDomain",
                                  json={"tenantId": tid, "domainId": did},
                                  headers=headers, verify=False, timeout=10)
                self.logger.info("Domain set: HTTP %s", r3.status_code)
        except Exception as e:
            self.logger.warning("Domain setup: %s", e)
        return tid, did


register_jobs(NetBrainDeepDive)
