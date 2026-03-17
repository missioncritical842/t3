"""NetBrain Field Discovery job for Nautobot.

Pulls a sample device and its interfaces from NetBrain and logs
the raw JSON structure. Used to identify all available fields
for mapping and faking decisions.
"""

from __future__ import annotations

import json

import requests
import urllib3

from nautobot.apps.jobs import BooleanVar, IntegerVar, Job, StringVar, register_jobs

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

NETBRAIN_API_BASE = "/ServicesAPI/API/V1"


class NetBrainFieldDiscovery(Job):
    """Pull sample data from NetBrain and log raw field structures."""

    class Meta:
        name = "NetBrain: Field Discovery"
        description = (
            "Fetches sample devices, interfaces, and sites from NetBrain "
            "and logs all raw JSON fields. Read-only -- writes nothing."
        )
        commit_default = False
        has_sensitive_variables = True

    host = StringVar(
        label="NetBrain Host",
        description="Base URL or IP (e.g. https://10.134.98.133)",
        default="https://10.134.98.133",
    )
    username = StringVar(
        label="Username",
        default="nautobotapi",
    )
    password = StringVar(
        label="Password",
        default="",
        required=False,
    )
    client_id = StringVar(
        label="Authentication ID (Client ID)",
        default="",
        required=False,
    )
    client_secret = StringVar(
        label="Client Secret",
        default="",
        required=False,
    )
    tenant_domain = StringVar(
        label="Tenant Domain",
        description="NetBrain tenant domain name",
        default="",
        required=False,
    )
    sample_count = IntegerVar(
        label="Sample Device Count",
        description="How many diverse device types to sample (max 10)",
        default=5,
        required=False,
    )
    fetch_interfaces = BooleanVar(
        label="Fetch Interfaces",
        description="Also fetch interface details for each sample device",
        default=True,
        required=False,
    )
    fetch_sites = BooleanVar(
        label="Fetch Sites",
        description="Also fetch the site tree",
        default=True,
        required=False,
    )

    def run(self, host="", username="", password="", client_id="",
            client_secret="", tenant_domain="", sample_count=2,
            fetch_interfaces=True, fetch_sites=True, **kwargs):

        host = (host or "").rstrip("/")
        sample_count = min(int(sample_count or 2), 5)

        # --- Login ---
        token = self._login(host, username, password, client_id, client_secret)
        if not token:
            return "FAILED: login"

        headers = {"Token": token, "Content-Type": "application/json"}

        try:
            # --- Discover available tenants/domains ---
            tenant_domain = self._discover_tenants(host, headers, tenant_domain)

            # --- Set tenant domain if provided ---
            if tenant_domain:
                self._set_tenant_domain(host, headers, tenant_domain)

            # --- Discover devices ---
            self._discover_devices(host, headers, sample_count, fetch_interfaces)

            # --- Discover sites ---
            if fetch_sites:
                self._discover_sites(host, headers)

        finally:
            # --- Logout ---
            self._logout(host, headers)

        self.logger.info("Field discovery complete.")
        return "SUCCESS"

    # ------------------------------------------------------------------
    # Auth helpers
    # ------------------------------------------------------------------

    def _login(self, host, username, password, client_id, client_secret):
        login_url = f"{host}{NETBRAIN_API_BASE}/Session"
        body = {"username": username, "password": password}
        if client_id:
            body["authentication_id"] = client_id
        if client_secret:
            body["client_secret"] = client_secret

        self.logger.info("Logging in to %s ...", login_url)
        try:
            resp = requests.post(login_url, json=body,
                                 headers={"Content-Type": "application/json"},
                                 verify=False, timeout=15)
        except Exception as exc:
            self.logger.error("Login failed: %s", exc)
            return None

        if resp.status_code != 200:
            self.logger.error("Login HTTP %s: %s", resp.status_code, resp.text[:500])
            return None

        token = resp.json().get("token", "")
        if not token:
            self.logger.error("No token in login response")
            return None

        self.logger.info("Login OK")
        return token

    def _set_tenant_domain(self, host, headers, domain):
        url = f"{host}{NETBRAIN_API_BASE}/Session/CurrentDomain"
        tenant = domain.split("/")[0]
        dom = domain.split("/")[-1]
        self.logger.info("Setting tenant domain to: %s / %s", tenant, dom)

        # Try multiple payload formats -- R12.1 may differ from docs
        payloads = [
            {"tenantName": tenant, "domainName": dom},
            {"tenant_name": tenant, "domain_name": dom},
            {"TenantName": tenant, "DomainName": dom},
        ]
        for payload in payloads:
            try:
                resp = requests.put(url, json=payload,
                                    headers=headers, verify=False, timeout=15)
                self.logger.info("Set domain HTTP %s (payload keys: %s): %s",
                                 resp.status_code, list(payload.keys()),
                                 resp.text[:300])
                if resp.status_code == 200:
                    return
            except Exception as exc:
                self.logger.warning("Set domain failed: %s", exc)

        # Also try GET to see current domain
        try:
            resp = requests.get(url, headers=headers, verify=False, timeout=15)
            self.logger.info("GET CurrentDomain HTTP %s: %s", resp.status_code, resp.text[:300])
        except Exception as exc:
            self.logger.info("GET CurrentDomain failed: %s", exc)

    def _discover_tenants(self, host, headers, existing_domain=""):
        """List available tenants and their domains. Returns tenant/domain string if auto-detected."""
        url = f"{host}{NETBRAIN_API_BASE}/CMDB/Tenants"
        self.logger.info("Fetching tenants from %s ...", url)
        first_tenant = ""
        first_domain = ""
        try:
            resp = requests.get(url, headers=headers, verify=False, timeout=15)
            self.logger.info("Tenants HTTP %s", resp.status_code)
            if resp.status_code == 200:
                data = resp.json()
                tenants = data.get("tenants", data.get("data", []))
                self.logger.info("Tenants response: %s", json.dumps(data, indent=2)[:2000])
                for t in tenants[:3]:
                    tid = t.get("tenantId", t.get("id", ""))
                    tname = t.get("tenantName", t.get("name", ""))
                    self.logger.info("  Tenant: %s (id: %s)", tname, tid)
                    dname = self._discover_domains(host, headers, tid)
                    if not first_tenant and tname:
                        first_tenant = tname
                    if not first_domain and dname:
                        first_domain = dname
            else:
                self.logger.info("Tenants response: %s", resp.text[:500])
        except Exception as exc:
            self.logger.warning("Tenants fetch failed: %s", exc)

        # Auto-detect tenant/domain if not provided
        if not existing_domain and first_tenant and first_domain:
            auto = f"{first_tenant}/{first_domain}"
            self.logger.info("Auto-detected tenant/domain: %s", auto)
            return auto
        return existing_domain

    def _discover_domains(self, host, headers, tenant_id):
        """List domains for a tenant. Returns first domain name found."""
        url = f"{host}{NETBRAIN_API_BASE}/CMDB/Domains"
        first_dname = ""
        try:
            resp = requests.get(url, headers=headers, verify=False, timeout=15,
                                params={"tenantId": tenant_id})
            if resp.status_code == 200:
                data = resp.json()
                domains = data.get("domains", data.get("data", []))
                for d in domains[:5]:
                    dname = d.get("domainName", d.get("name", ""))
                    did = d.get("domainId", d.get("id", ""))
                    self.logger.info("    Domain: %s (id: %s)", dname, did)
                    if not first_dname and dname:
                        first_dname = dname
            else:
                self.logger.info("    Domains HTTP %s: %s", resp.status_code, resp.text[:200])
        except Exception as exc:
            self.logger.info("    Domains fetch failed: %s", exc)
        return first_dname

    def _logout(self, host, headers):
        try:
            requests.delete(f"{host}{NETBRAIN_API_BASE}/Session",
                            headers=headers, verify=False, timeout=10)
            self.logger.info("Logged out.")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Device discovery
    # ------------------------------------------------------------------

    def _discover_devices(self, host, headers, sample_count, fetch_interfaces):
        self.logger.info("=" * 60)
        self.logger.info("DEVICE FIELD DISCOVERY")
        self.logger.info("=" * 60)

        # Fetch a larger batch to find diverse device types
        url = f"{host}{NETBRAIN_API_BASE}/CMDB/Devices"
        self.logger.info("Fetching devices from %s (limit=100) ...", url)

        all_devices = []
        skip = 0
        while len(all_devices) < 200:
            try:
                resp = requests.get(url, headers=headers, verify=False, timeout=30,
                                    params={"skip": skip, "limit": 100})
            except Exception as exc:
                self.logger.error("Device fetch failed: %s", exc)
                break

            if resp.status_code != 200:
                self.logger.warning("Device list HTTP %s at skip=%d: %s",
                                    resp.status_code, skip, resp.text[:300])
                break

            data = resp.json()
            batch = data.get("devices", data.get("data", []))
            if not batch:
                break
            all_devices.extend(batch)
            skip += len(batch)
            if len(batch) < 100:
                break

        self.logger.info("Total devices fetched: %d", len(all_devices))
        devices = all_devices

        # Log all unique subTypeNames to see device diversity
        sub_types = {}
        for d in devices:
            st = d.get("subTypeName", "unknown")
            sub_types[st] = sub_types.get(st, 0) + 1
        self.logger.info("Device type distribution:")
        for st, count in sorted(sub_types.items(), key=lambda x: -x[1]):
            self.logger.info("  %s: %d", st, count)

        # Pick sample devices: prefer non-AWS, diverse types
        seen_types = set()
        selected = []
        # First pass: one of each non-AWS type
        for d in devices:
            st = d.get("subTypeName", "")
            if "AWS" not in st and st not in seen_types:
                selected.append(d)
                seen_types.add(st)
                if len(selected) >= sample_count:
                    break
        # Second pass: if not enough non-AWS, add AWS types not yet seen
        if len(selected) < sample_count:
            for d in devices:
                st = d.get("subTypeName", "")
                if st not in seen_types:
                    selected.append(d)
                    seen_types.add(st)
                    if len(selected) >= sample_count:
                        break
        # Third pass: fill remaining from any
        if len(selected) < sample_count:
            for d in devices:
                if d not in selected:
                    selected.append(d)
                    if len(selected) >= sample_count:
                        break

        devices = selected
        self.logger.info("Selected %d diverse sample devices", len(devices))

        if not devices:
            self.logger.warning("No devices returned. Response keys: %s", list(data.keys()))
            self.logger.info("Full response (truncated): %s", json.dumps(data, indent=2)[:2000])
            return

        self.logger.info("Got %d device(s)", len(devices))

        for i, dev in enumerate(devices[:sample_count]):
            self.logger.info("-" * 50)
            self.logger.info("DEVICE %d/%d", i + 1, sample_count)
            self.logger.info("-" * 50)

            # Log all top-level keys
            self.logger.info("Top-level keys: %s", sorted(dev.keys()))

            # Log each field with its type and a sample value
            for key in sorted(dev.keys()):
                val = dev[key]
                val_type = type(val).__name__
                val_preview = str(val)[:200]
                self.logger.info("  %s (%s): %s", key, val_type, val_preview)

            hostname = dev.get("name", dev.get("hostname", "unknown"))

            # Fetch full device attributes
            self._fetch_device_attributes(host, headers, hostname)

            # Fetch interfaces
            if fetch_interfaces:
                self._fetch_interfaces(host, headers, hostname)

    def _try_alternate_device_endpoints(self, host, headers, sample_count, fetch_interfaces):
        """Try other NetBrain API endpoints for device listing."""
        alternates = [
            "/CMDB/Devices/BasicInfo",
            "/CMDB/DeviceGroups",
        ]
        for path in alternates:
            url = f"{host}{NETBRAIN_API_BASE}{path}"
            self.logger.info("Trying alternate: %s", url)
            try:
                resp = requests.get(url, headers=headers, verify=False, timeout=15)
                self.logger.info("  HTTP %s, keys: %s",
                                 resp.status_code,
                                 list(resp.json().keys()) if resp.status_code == 200 else resp.text[:200])
            except Exception as exc:
                self.logger.info("  Failed: %s", exc)

    def _fetch_device_attributes(self, host, headers, hostname):
        """Fetch detailed attributes for a single device."""
        url = f"{host}{NETBRAIN_API_BASE}/CMDB/Devices/Attributes"
        self.logger.info("Fetching attributes for '%s' ...", hostname)

        try:
            resp = requests.get(url, headers=headers, verify=False, timeout=15,
                                params={"hostname": hostname})
        except Exception as exc:
            self.logger.warning("Attributes fetch failed: %s", exc)
            return

        if resp.status_code != 200:
            self.logger.warning("Attributes HTTP %s: %s", resp.status_code, resp.text[:300])
            return

        data = resp.json()
        attrs = data.get("attributes", data)

        self.logger.info("DEVICE ATTRIBUTES for '%s':", hostname)
        self.logger.info("  Attribute keys: %s", sorted(attrs.keys()) if isinstance(attrs, dict) else type(attrs).__name__)

        if isinstance(attrs, dict):
            for key in sorted(attrs.keys()):
                val = attrs[key]
                val_type = type(val).__name__
                val_preview = str(val)[:200]
                self.logger.info("  ATTR %s (%s): %s", key, val_type, val_preview)

    # ------------------------------------------------------------------
    # Interface discovery
    # ------------------------------------------------------------------

    def _fetch_interfaces(self, host, headers, hostname):
        """Fetch interfaces for a device and log field structures."""
        self.logger.info("=" * 40)
        self.logger.info("INTERFACES for '%s'", hostname)
        self.logger.info("=" * 40)

        url = f"{host}{NETBRAIN_API_BASE}/CMDB/Interfaces"
        try:
            resp = requests.get(url, headers=headers, verify=False, timeout=30,
                                params={"hostname": hostname})
        except Exception as exc:
            self.logger.warning("Interface fetch failed: %s", exc)
            return

        if resp.status_code != 200:
            self.logger.warning("Interfaces HTTP %s: %s", resp.status_code, resp.text[:300])
            # Try alternate
            url2 = f"{host}{NETBRAIN_API_BASE}/CMDB/Interfaces/Attributes"
            self.logger.info("Trying %s ...", url2)
            try:
                resp = requests.get(url2, headers=headers, verify=False, timeout=15,
                                    params={"hostname": hostname})
                self.logger.info("  HTTP %s", resp.status_code)
            except Exception as exc:
                self.logger.warning("  Failed: %s", exc)
                return

        if resp.status_code != 200:
            return

        data = resp.json()
        interfaces = data.get("interfaces", data.get("data", []))

        if not interfaces:
            self.logger.info("No interfaces returned. Keys: %s", list(data.keys()))
            self.logger.info("Response (truncated): %s", json.dumps(data, indent=2)[:1000])
            return

        self.logger.info("Got %d interface(s) -- showing first 3", len(interfaces))

        for i, intf in enumerate(interfaces[:3]):
            self.logger.info("  --- Interface %d ---", i + 1)
            if isinstance(intf, dict):
                self.logger.info("  Keys: %s", sorted(intf.keys()))
                for key in sorted(intf.keys()):
                    val = intf[key]
                    val_type = type(val).__name__
                    val_preview = str(val)[:200]
                    self.logger.info("    %s (%s): %s", key, val_type, val_preview)
            else:
                # Interface might be a string (just the name) -- fetch attributes
                self.logger.info("  Interface value (type %s): %s", type(intf).__name__, str(intf)[:300])

        # If interfaces are strings (names), fetch attributes for the first one
        if interfaces and isinstance(interfaces[0], str):
            self.logger.info("Interfaces are names -- fetching attributes for first 3...")
            for intf_name in interfaces[:3]:
                self._fetch_interface_attributes(host, headers, hostname, intf_name)

    def _fetch_interface_attributes(self, host, headers, hostname, intf_name):
        """Fetch detailed attributes for a single interface."""
        url = f"{host}{NETBRAIN_API_BASE}/CMDB/Interfaces/Attributes"
        self.logger.info("  Fetching attributes for interface '%s' on '%s' ...", intf_name, hostname)
        try:
            resp = requests.get(url, headers=headers, verify=False, timeout=15,
                                params={"hostname": hostname, "interfaceName": intf_name})
        except Exception as exc:
            self.logger.warning("  Interface attributes fetch failed: %s", exc)
            return

        if resp.status_code != 200:
            self.logger.warning("  Interface attrs HTTP %s: %s", resp.status_code, resp.text[:300])
            return

        data = resp.json()
        attrs = data.get("attributes", data)
        # Unwrap {intf_name: {actual_attrs}} wrapper
        if isinstance(attrs, dict) and len(attrs) == 1:
            key0 = list(attrs.keys())[0]
            if isinstance(attrs[key0], dict):
                attrs = attrs[key0]
        self.logger.info("  INTERFACE ATTRIBUTES for '%s':", intf_name)
        if isinstance(attrs, dict):
            self.logger.info("    Keys (%d): %s", len(attrs), sorted(attrs.keys()))
            for key in sorted(attrs.keys()):
                val = attrs[key]
                val_type = type(val).__name__
                val_preview = str(val)[:300]
                self.logger.info("    %s (%s): %s", key, val_type, val_preview)
        else:
            self.logger.info("    Value: %s", str(attrs)[:500])

    # ------------------------------------------------------------------
    # Site discovery
    # ------------------------------------------------------------------

    def _discover_sites(self, host, headers):
        self.logger.info("=" * 60)
        self.logger.info("SITE TREE DISCOVERY")
        self.logger.info("=" * 60)

        # R12.1 uses POST /CMDB/Sites/ChildSites with sitePath for tree traversal
        # First try root level
        url = f"{host}{NETBRAIN_API_BASE}/CMDB/Sites/ChildSites"
        self.logger.info("Fetching root sites from %s (POST) ...", url)

        try:
            resp = requests.post(url, json={"sitePath": "My Network"},
                                 headers=headers, verify=False, timeout=30)
        except Exception as exc:
            self.logger.error("Site fetch failed: %s", exc)
            return

        self.logger.info("Sites HTTP %s", resp.status_code)

        if resp.status_code != 200:
            self.logger.warning("Sites response: %s", resp.text[:500])
            # Try GET as fallback
            try:
                resp = requests.get(f"{host}{NETBRAIN_API_BASE}/CMDB/Sites",
                                    headers=headers, verify=False, timeout=15)
                self.logger.info("GET /Sites HTTP %s: %s", resp.status_code, resp.text[:500])
            except Exception as exc:
                self.logger.warning("GET fallback failed: %s", exc)
            return

        data = resp.json()
        sites = data.get("sites", data.get("data", data.get("childSites", [])))

        if not sites:
            self.logger.info("Response keys: %s", list(data.keys()))
            self.logger.info("Response (truncated): %s", json.dumps(data, indent=2)[:2000])
            return

        self.logger.info("Got %d site(s) -- showing first 10", len(sites))
        for i, site in enumerate(sites[:10]):
            self.logger.info("  --- Site %d ---", i + 1)
            if isinstance(site, dict):
                self.logger.info("  Keys: %s", sorted(site.keys()))
                for key in sorted(site.keys()):
                    val = site[key]
                    val_type = type(val).__name__
                    val_preview = str(val)[:200]
                    self.logger.info("    %s (%s): %s", key, val_type, val_preview)
            else:
                self.logger.info("  Value: %s", str(site)[:300])


register_jobs(NetBrainFieldDiscovery)
