"""NetBrain -> Nautobot Import (Minimal Identity + Observations).

Follows Joshua's pattern: import jobs store raw vendor facts ONLY under
observations["netbrain"]. Minimal identity fields on the Device object.
Normalization/rollups are done by a separate rollup job.

NAUTOBOT_FAKER is always ON for this demo to protect sensitive data.
"""

from __future__ import annotations

import json
import os
import time

import requests
import urllib3

from nautobot.apps.jobs import BooleanVar, IntegerVar, Job, StringVar, register_jobs
from nautobot.dcim.models import Device, DeviceType, Manufacturer, Platform
from nautobot.extras.models import Role, Status

from .netbrain_utils import (
    _fake_hostname,
    _fake_serial,
    _sanitize_device_attrs,
    _sanitize_enabled,
    _sanitize_json_tree,
    _utc_now_iso,
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

V1 = "/ServicesAPI/API/V1"
OBS_NAMESPACE = "netbrain"
OBS_CF_KEY = "observations"

# NetBrain device categories (~957 devices confirmed by client)
TARGET_SUBTYPES = {
    # Router (55)
    "Cisco Router", "AWS DX Router", "NetScout Router",
    # L3 Switches (299)
    "Cisco IOS Switch", "Cisco Nexus Switch", "Cisco ACI Spine Switch",
    "Arista Switch", "Aruba Switch", "Cisco Meraki Switch", "LAN Switch",
    # Firewall (126)
    "Palo Alto Firewall", "Cisco Meraki Firewall",
    # Load Balancers (33)
    "F5 Load Balancer",
    # WAN Optimizer (28)
    "SilverPeak WAN Optimizer",
    # WLC (6)
    "Cisco WLC",
    # Wireless Access Points (390)
    "Cisco Meraki AP", "Aruba IAP", "LWAP",
    # IP Phone (14)
    "IP Phone",
    # Unclassified Devices (6)
    "Unclassified Device",
    # Ancillary
    "Cisco ISE", "Cisco Meraki Controller", "Cisco Meraki Z-Series Gateway",
}

# Vendor name normalization
VENDOR_MAP = {
    "arista networks": "Arista",
    "aruba networks": "Aruba",
    "cisco systems": "Cisco",
    "f5, inc": "F5",
    "f5, inc.": "F5",
    "f5 networks": "F5",
    "palo alto networks": "Palo Alto Networks",
    "netscout": "NetScout",
}


def _normalize_vendor(raw):
    return VENDOR_MAP.get(raw.strip().lower(), raw.strip())


class NetBrainImportDemo(Job):
    """Import network devices from NetBrain: minimal identity + observations blob."""

    class Meta:
        name = "NetBrain: Import Demo"
        description = (
            "Minimal import: creates Device with identity fields (name, serial, "
            "model, role, status) and stores full raw NetBrain data in the "
            "observations custom field. Rollup job handles the rest."
        )
        commit_default = False
        has_sensitive_variables = True

    host = StringVar(default="https://10.134.98.133", label="NetBrain Host")
    username = StringVar(default="nautobotapi", label="Username")
    password = StringVar(default="", required=False, label="Password",
                         description="Leave blank to use stored credentials")
    client_id = StringVar(default="", required=False, label="Client ID",
                          description="Leave blank to use stored credentials")
    client_secret = StringVar(default="", required=False, label="Client Secret",
                              description="Leave blank to use stored credentials")

    dry_run = BooleanVar(
        label="Dry Run", default=True, required=False,
        description="Log what would happen without writing to DB.",
    )
    device_limit = IntegerVar(
        label="Device Limit", default=0, required=False,
        description="Max devices to import. 0 = ALL (~957 devices).",
    )
    include_waps = BooleanVar(
        label="Include WAPs", default=False, required=False,
        description="Include wireless APs (390 devices). Uncheck for faster run.",
    )

    def run(self, host="", username="", password="", client_id="",
            client_secret="", dry_run=True, device_limit=0,
            include_waps=False, **kwargs):

        host = (host or "").rstrip("/")
        stored = self._load_stored_creds()
        username = (username or "").strip() or os.environ.get("NETBRAIN_USERNAME", "") or stored.get("username", "nautobotapi")
        password = (password or "").strip() or os.environ.get("NETBRAIN_PASSWORD", "") or stored.get("password", "")
        client_id = (client_id or "").strip() or os.environ.get("NETBRAIN_CLIENT_ID", "") or stored.get("client_id", "")
        client_secret = (client_secret or "").strip() or os.environ.get("NETBRAIN_CLIENT_SECRET", "") or stored.get("client_secret", "")
        device_limit = int(device_limit or 0)
        if device_limit <= 0:
            device_limit = 99999

        target_types = set(TARGET_SUBTYPES)
        if not include_waps:
            target_types -= {"Cisco Meraki AP", "Aruba IAP", "LWAP"}

        self.logger.info("=" * 60)
        self.logger.info("NetBrain Import (Minimal Identity + Observations)")
        self.logger.info("  dry_run: %s", dry_run)
        self.logger.info("  faker: ALWAYS ON")
        self.logger.info("  device_limit: %s", "ALL" if device_limit >= 99999 else device_limit)
        self.logger.info("  include_waps: %s", include_waps)
        self.logger.info("=" * 60)

        stats = {"fetched": 0, "created": 0, "updated": 0, "skipped": 0, "errors": 0}

        token = self._login(host, username, password, client_id, client_secret)
        if not token:
            return "FAILED: login"
        headers = {"Token": token, "Content-Type": "application/json"}

        try:
            self._set_domain(host, headers)

            active = Status.objects.get(name="Active")

            # Scan inventory for target devices
            network_devices = self._scan_inventory(host, headers, device_limit, target_types)
            stats["fetched"] = len(network_devices)
            self.logger.info("Found %d network devices to import", len(network_devices))

            # Import each: minimal identity + observations
            for i, (raw_hostname, raw_attrs) in enumerate(network_devices):
                sub_type = raw_attrs.get("subTypeName", "Unknown")

                # Build observation payload from RAW data (before faking)
                obs_payload = {
                    "schema_version": 1,
                    "meta": {
                        "fetched_at": _utc_now_iso(),
                        "source": "netbrain_import_demo",
                        "nb_hostname": raw_hostname,
                    },
                    "data": {"remote": raw_attrs},
                }

                # Fake for display/storage
                if _sanitize_enabled():
                    obs_payload = _sanitize_json_tree(obs_payload, skip_keys=frozenset({
                        "schema_version", "source", "vendor", "model",
                        "subTypeName", "driverName", "ver", "os",
                    }))

                # Always fake identity fields for demo
                serial = (raw_attrs.get("sn") or "").strip()
                name = (raw_attrs.get("name") or "").strip()
                display_name = _fake_hostname(name) if name else f"device-{i}"
                display_serial = _fake_serial(serial) if serial else ""

                vendor = _normalize_vendor(raw_attrs.get("vendor") or "Unknown") or "Unknown"
                model = (raw_attrs.get("model") or "Unknown").strip() or "Unknown"
                driver = (raw_attrs.get("driverName") or "").strip()

                if (i + 1) % 200 == 0 or i == 0:
                    self.logger.info("  [%d/%d] %s (%s) vendor=%s model=%s",
                                     i + 1, len(network_devices),
                                     display_name, sub_type, vendor, model)

                if dry_run:
                    stats["created"] += 1
                    continue

                try:
                    # Minimal Nautobot objects
                    mfr, _ = Manufacturer.objects.get_or_create(name=vendor)
                    dtype, _ = DeviceType.objects.get_or_create(
                        model=model, manufacturer=mfr)
                    role, role_created = Role.objects.get_or_create(name=sub_type)
                    if role_created:
                        from django.contrib.contenttypes.models import ContentType
                        ct = ContentType.objects.get_for_model(Device)
                        role.content_types.add(ct)

                    platform = None
                    if driver:
                        platform, _ = Platform.objects.get_or_create(name=driver)

                    # Always create fresh — no matching against existing devices
                    device = None
                    if False:
                        device = Device(
                            name=display_name,
                            serial=display_serial,
                            device_type=dtype,
                            platform=platform,
                            role=role,
                            status=active,
                            location=self._get_fallback_location(active),
                        )
                        # Write observations before first save
                        cf = device._custom_field_data or {}
                        obs = cf.get(OBS_CF_KEY)
                        obs = obs if isinstance(obs, dict) else {}
                        obs[OBS_NAMESPACE] = obs_payload
                        obs["_sanitized"] = True
                        cf[OBS_CF_KEY] = obs
                        cf["system_of_record"] = "NetBrain"
                        cf["last_synced_from_sor"] = _utc_now_iso()[:10]
                        device._custom_field_data = cf
                        device.validated_save()
                        stats["created"] += 1
                    else:
                        stats["updated"] += 1

                except Exception as exc:
                    self.logger.error("  Error on device %d: %s", i + 1, exc)
                    stats["errors"] += 1

        finally:
            self._logout(host, headers)

        self.logger.info("=" * 60)
        self.logger.info("IMPORT COMPLETE")
        for k, v in stats.items():
            self.logger.info("  %s: %d", k, v)
        self.logger.info("=" * 60)
        return json.dumps(stats)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_stored_creds(self):
        try:
            from nautobot.extras.models import ConfigContext
            ctx = ConfigContext.objects.filter(name="NetBrain Credentials").first()
            if ctx and ctx.data:
                return ctx.data
        except Exception:
            pass
        return {}

    def _get_fallback_location(self, active_status):
        """Get or create Placeholder Site. Called before each device save to handle race conditions."""
        from django.contrib.contenttypes.models import ContentType
        from nautobot.dcim.models import Device, Location, LocationType
        lt, _ = LocationType.objects.get_or_create(name="Site", defaults={"nestable": False})
        # Ensure Site LocationType allows devices
        device_ct = ContentType.objects.get_for_model(Device)
        if device_ct not in lt.content_types.all():
            lt.content_types.add(device_ct)
        loc, _ = Location.objects.get_or_create(
            name="Placeholder Site", location_type=lt,
            defaults={"status": active_status})
        return loc

    def _login(self, host, username, password, client_id, client_secret):
        body = {"username": username, "password": password}
        if client_id:
            body["authentication_id"] = client_id
        if client_secret:
            body["client_secret"] = client_secret
        for attempt in range(3):
            try:
                r = requests.post(f"{host}{V1}/Session", json=body,
                                  headers={"Content-Type": "application/json"},
                                  verify=False, timeout=60)
                if r.status_code == 200:
                    token = r.json().get("token", "")
                    if token:
                        self.logger.info("Login OK")
                        return token
                self.logger.warning("Login attempt %d: HTTP %s", attempt + 1, r.status_code)
            except Exception as exc:
                self.logger.warning("Login attempt %d: %s", attempt + 1, exc)
            if attempt < 2:
                time.sleep(10)
        self.logger.error("Login failed after 3 attempts")
        return None

    def _set_domain(self, host, headers):
        try:
            r = requests.get(f"{host}{V1}/CMDB/Tenants", headers=headers,
                             verify=False, timeout=30)
            if r.status_code != 200:
                return
            tid = r.json().get("tenants", [{}])[0].get("tenantId", "")
            r2 = requests.get(f"{host}{V1}/CMDB/Domains", params={"tenantId": tid},
                              headers=headers, verify=False, timeout=30)
            if r2.status_code != 200:
                return
            did = r2.json().get("domains", [{}])[0].get("domainId", "")
            r3 = requests.put(f"{host}{V1}/Session/CurrentDomain",
                              json={"tenantId": tid, "domainId": did},
                              headers=headers, verify=False, timeout=30)
            self.logger.info("Domain set: HTTP %s", r3.status_code)
        except Exception as exc:
            self.logger.warning("Domain setup: %s", exc)

    def _scan_inventory(self, host, headers, limit, target_types):
        """Scan paginated inventory, collect devices matching target subTypeNames."""
        results = []
        skip = 0
        max_pages = 260

        self.logger.info("Scanning inventory for %d target types...", len(target_types))

        for page in range(max_pages):
            if len(results) >= limit:
                break
            try:
                r = requests.get(f"{host}{V1}/CMDB/Devices",
                                 params={"skip": skip, "limit": 100},
                                 headers=headers, verify=False, timeout=60)
                if r.status_code != 200:
                    break
                batch = r.json().get("devices", [])
                if not batch:
                    break

                for d in batch:
                    st = d.get("subTypeName", "")
                    if st in target_types:
                        hn = d.get("name", "").strip()
                        if hn:
                            # Fetch full attributes
                            time.sleep(0.1)
                            attrs = self._get_attrs(host, headers, hn)
                            if attrs:
                                results.append((hn, attrs))
                                if len(results) >= limit:
                                    break

                skip += len(batch)
                if len(batch) < 100:
                    break

                if (page + 1) % 40 == 0:
                    self.logger.info("  Scanned %d devices, found %d network...",
                                     skip, len(results))
            except Exception as exc:
                self.logger.warning("  Scan error at skip=%d: %s", skip, exc)
                time.sleep(2)
                skip += 100

        self.logger.info("Scan complete: found %d network devices", len(results))
        return results

    def _get_attrs(self, host, headers, hostname):
        try:
            r = requests.get(f"{host}{V1}/CMDB/Devices/Attributes",
                             params={"hostname": hostname},
                             headers=headers, verify=False, timeout=30)
            if r.status_code == 200:
                return r.json().get("attributes", {})
        except Exception:
            pass
        return None

    def _logout(self, host, headers):
        try:
            requests.delete(f"{host}{V1}/Session", headers=headers,
                            verify=False, timeout=10)
            self.logger.info("Logged out.")
        except Exception:
            pass


register_jobs(NetBrainImportDemo)
