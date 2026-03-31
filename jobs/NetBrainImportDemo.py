"""NetBrain -> Nautobot Import (Minimal Identity + Observations).

Five modes:
  1) Audit Only       — scan NetBrain, log missing devices as CSV, no writes
  2) Audit + Update   — same scan, also refresh observations on existing devices
  3) Import by List   — paste hostnames from a previous audit, import those
  4) Import All       — import every missing device (requires confirmation)
  5) Update Obs List  — paste hostnames, refresh observation data on existing devices

Matches NetBrain devices to existing Nautobot devices by hostname (primary)
or serial number (fallback). Adds observations["netbrain"] alongside existing
observations from other sources (netdata_chassis, netdata_device_inventory, etc.).

Faker controlled by NAUTOBOT_FAKER env var.
"""

from __future__ import annotations

import json
import os
import time

import requests
import urllib3

from nautobot.apps.jobs import (
    BooleanVar,
    ChoiceVar,
    Job,
    StringVar,
    TextVar,
    register_jobs,
)
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

# NetBrain device categories (~1,042 devices)
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

MODE_CHOICES = [
    ("audit", "1) Audit Only — log missing devices as CSV, no writes"),
    ("audit_update", "2) Audit + Update — log missing, refresh observations on existing"),
    ("import_list", "3) Import by List — paste hostnames to import"),
    ("import_all", "4) Import All Missing — requires confirmation"),
    ("update_list", "5) Update Observations by List — refresh data for pasted hostnames"),
]

VENDOR_MAP = {
    "arista networks": "Arista",
    "aruba networks": "Aruba",
    "cisco systems": "Cisco",
    "f5, inc": "F5", "f5, inc.": "F5", "f5 networks": "F5",
    "palo alto networks": "Palo Alto Networks",
    "netscout": "NetScout",
}


def _normalize_vendor(raw):
    return VENDOR_MAP.get(raw.strip().lower(), raw.strip())


class NetBrainImportDemo(Job):
    """Import network devices from NetBrain with four operating modes."""

    class Meta:
        name = "NetBrain: Import Demo"
        description = (
            "Four modes: (1) Audit missing devices as CSV, (2) Audit + update "
            "observations, (3) Import from pasted list, (4) Import all missing. "
            "Faker always ON."
        )
        commit_default = False
        has_sensitive_variables = True

    # --- Mode selection ---
    mode = ChoiceVar(
        choices=MODE_CHOICES,
        label="Mode",
        description="Select operating mode",
    )

    # --- Credentials ---
    host = StringVar(default="https://10.134.98.133", label="NetBrain Host")
    username = StringVar(default="nautobotapi", label="Username")
    password = StringVar(default="", required=False, label="Password",
                         description="Leave blank to use stored credentials")
    client_id = StringVar(default="", required=False, label="Client ID",
                          description="Leave blank to use stored credentials")
    client_secret = StringVar(default="", required=False, label="Client Secret",
                              description="Leave blank to use stored credentials")

    # --- Options ---
    include_waps = BooleanVar(
        label="Include WAPs", default=False, required=False,
        description="Include wireless APs (~390 devices). Uncheck for faster scan.",
    )

    # --- Mode 3: Import by List ---
    device_list = TextVar(
        label="Device List (Mode 3 only)",
        description="Paste hostnames from a previous audit, one per line. CSV lines accepted (hostname is first column).",
        default="",
        required=False,
    )

    # --- Safety confirmation for modes 3 and 4 ---
    confirm_import = BooleanVar(
        label="I am sure I want to import devices",
        description="Required for modes 3 and 4.",
        default=False,
        required=False,
    )
    confirm_yes = StringVar(
        label="Type YES to confirm",
        description="Required for modes 3 and 4.",
        default="",
        required=False,
    )

    def run(self, mode="audit", host="", username="", password="",
            client_id="", client_secret="", include_waps=False,
            device_list="", confirm_import=False, confirm_yes="", **kwargs):

        host = (host or "").rstrip("/")
        stored = self._load_stored_creds()
        username = (username or "").strip() or os.environ.get("NETBRAIN_USERNAME", "") or stored.get("username", "nautobotapi")
        password = (password or "").strip() or os.environ.get("NETBRAIN_PASSWORD", "") or stored.get("password", "")
        client_id = (client_id or "").strip() or os.environ.get("NETBRAIN_CLIENT_ID", "") or stored.get("client_id", "")
        client_secret = (client_secret or "").strip() or os.environ.get("NETBRAIN_CLIENT_SECRET", "") or stored.get("client_secret", "")

        # Faker controlled by NAUTOBOT_FAKER env var
        faker_on = _sanitize_enabled()

        # Safety check for import modes
        if mode in ("import_list", "import_all"):
            if not confirm_import or (confirm_yes or "").strip().upper() != "YES":
                self.logger.error("Import requires both the confirmation checkbox AND typing YES.")
                return "ABORTED: confirmation required"

        target_types = set(TARGET_SUBTYPES)
        if not include_waps:
            target_types -= {"Cisco Meraki AP", "Aruba IAP", "LWAP"}

        self.logger.info("=" * 60)
        self.logger.info("NetBrain Import Demo")
        self.logger.info("  mode: %s", mode)
        self.logger.info("  faker: %s", "ON" if faker_on else "OFF")
        self.logger.info("  include_waps: %s", include_waps)
        self.logger.info("=" * 60)

        stats = {"fetched": 0, "missing": 0, "existing": 0,
                 "created": 0, "updated": 0, "errors": 0}

        # --- Mode 3: Import by List ---
        if mode == "import_list":
            return self._run_import_list(host, username, password, client_id,
                                          client_secret, device_list, stats)

        # --- Mode 5: Update Observations by List ---
        if mode == "update_list":
            return self._run_update_list(host, username, password, client_id,
                                          client_secret, device_list, stats)

        # --- Modes 1, 2, 4: need full inventory scan ---
        token = self._login(host, username, password, client_id, client_secret)
        if not token:
            return "FAILED: login"
        headers = {"Token": token, "Content-Type": "application/json"}

        try:
            self._set_domain(host, headers)

            # Get existing devices in Nautobot (by name and serial for matching)
            existing_names = set(Device.objects.values_list("name", flat=True))
            existing_serials = {s for s in Device.objects.values_list("serial", flat=True) if s}
            self.logger.info("Existing devices in Nautobot: %d", len(existing_names))

            # Scan NetBrain inventory
            nb_devices = self._scan_inventory(host, headers, target_types)
            stats["fetched"] = len(nb_devices)

            # Classify each as missing or existing
            # Match by hostname first, then serial fallback
            missing = []
            existing = []
            for hn, attrs in nb_devices:
                name = (attrs.get("name") or "").strip()
                serial = (attrs.get("sn") or "").strip()
                display_name = _fake_hostname(name) if (name and faker_on) else name
                display_serial = _fake_serial(serial) if (serial and faker_on) else serial

                # Try matching by name, then by serial
                matched_device = None
                if name and name in existing_names:
                    matched_device = name
                elif display_name and display_name in existing_names:
                    matched_device = display_name
                elif serial and serial in existing_serials:
                    matched_device = f"serial:{serial}"
                elif display_serial and display_serial in existing_serials:
                    matched_device = f"serial:{display_serial}"

                if matched_device:
                    existing.append((hn, attrs, matched_device))
                else:
                    missing.append((hn, attrs, display_name or name))

            stats["missing"] = len(missing)
            stats["existing"] = len(existing)

            self.logger.info("NetBrain devices: %d total, %d missing, %d existing",
                             len(nb_devices), len(missing), len(existing))

            # --- Generate CSV of missing devices ---
            self._save_missing_csv(missing)

            # --- Mode 2: Update observations on existing devices ---
            if mode in ("audit_update", "import_all"):
                active = Status.objects.get(name="Active")
                self.logger.info("")
                self.logger.info("Updating observations on %d existing devices...", len(existing))
                for hn, attrs, match_key in existing:
                    try:
                        device = self._find_device(match_key)
                        if device:
                            self._update_observations(device, hn, attrs)
                            stats["updated"] += 1
                        else:
                            self.logger.warning("  Could not find device for %s", match_key)
                    except Exception as exc:
                        self.logger.error("  Update error for %s: %s", match_key, exc)
                        stats["errors"] += 1

            # --- Mode 4: Import all missing ---
            if mode == "import_all":
                active = Status.objects.get(name="Active")
                self.logger.info("")
                self.logger.info("Importing %d missing devices...", len(missing))
                for i, (hn, attrs, display_name) in enumerate(missing):
                    try:
                        self._create_device(hn, attrs, display_name, active, stats)
                        if (i + 1) % 100 == 0:
                            self.logger.info("  Progress: %d/%d created", i + 1, len(missing))
                    except Exception as exc:
                        self.logger.error("  Error creating %s: %s", display_name, exc)
                        stats["errors"] += 1

        finally:
            self._logout(host, headers)

        self.logger.info("")
        self.logger.info("=" * 60)
        self.logger.info("COMPLETE")
        for k, v in stats.items():
            self.logger.info("  %s: %d", k, v)
        self.logger.info("=" * 60)
        return json.dumps(stats)

    # ------------------------------------------------------------------
    # Mode 5: Update Observations by List
    # ------------------------------------------------------------------

    def _run_update_list(self, host, username, password, client_id,
                          client_secret, device_list, stats):
        """Update observations on existing devices from a pasted hostname list."""
        hostnames = self._parse_device_list(device_list)
        if not hostnames:
            self.logger.error("No hostnames provided in device list")
            return "FAILED: empty list"

        self.logger.info("Updating observations for %d devices from list...", len(hostnames))

        token = self._login(host, username, password, client_id, client_secret)
        if not token:
            return "FAILED: login"
        headers = {"Token": token, "Content-Type": "application/json"}

        try:
            self._set_domain(host, headers)
            existing_names = set(Device.objects.values_list("name", flat=True))
            not_found = []

            for i, hn in enumerate(hostnames):
                try:
                    time.sleep(0.1)
                    attrs = self._get_attrs(host, headers, hn)
                    if not attrs:
                        self.logger.warning("  No attributes for '%s', skipping", hn)
                        stats["errors"] += 1
                        continue

                    name = (attrs.get("name") or "").strip()
                    serial = (attrs.get("sn") or "").strip()
                    faker_on = _sanitize_enabled()
                    display_name = _fake_hostname(name) if (name and faker_on) else name

                    # Match by real name, faked name, or serial
                    device = Device.objects.filter(name=name).first() if name else None
                    if not device and display_name and display_name != name:
                        device = Device.objects.filter(name=display_name).first()
                    if not device and serial:
                        device = Device.objects.filter(serial=serial).first()

                    if device:
                        self.logger.info("  Updating: %s (%s)", device.name, attrs.get("subTypeName", ""))
                        self._update_observations(device, hn, attrs, log_diff=True)
                        stats["updated"] += 1
                    else:
                        not_found.append((hn, attrs, display_name or name))
                        self.logger.info("  Device '%s' not in Nautobot, skipping update", name)

                    if (i + 1) % 50 == 0:
                        self.logger.info("  Progress: %d/%d", i + 1, len(hostnames))

                except Exception as exc:
                    self.logger.error("  Error on '%s': %s", hn, exc)
                    stats["errors"] += 1

            # Generate CSV for devices not found in Nautobot
            stats["missing"] = len(not_found)
            self._save_missing_csv(not_found)

        finally:
            self._logout(host, headers)

        self.logger.info("")
        self.logger.info("=" * 60)
        self.logger.info("LIST UPDATE COMPLETE")
        for k, v in stats.items():
            self.logger.info("  %s: %d", k, v)
        self.logger.info("=" * 60)
        return json.dumps(stats)

    # ------------------------------------------------------------------
    # Mode 3: Import by List
    # ------------------------------------------------------------------

    def _run_import_list(self, host, username, password, client_id,
                          client_secret, device_list, stats):
        """Import devices from a pasted hostname list."""
        hostnames = self._parse_device_list(device_list)
        if not hostnames:
            self.logger.error("No hostnames provided in device list")
            return "FAILED: empty list"

        self.logger.info("Importing %d devices from list...", len(hostnames))

        token = self._login(host, username, password, client_id, client_secret)
        if not token:
            return "FAILED: login"
        headers = {"Token": token, "Content-Type": "application/json"}

        try:
            self._set_domain(host, headers)
            active = Status.objects.get(name="Active")

            for i, hn in enumerate(hostnames):
                try:
                    time.sleep(0.1)
                    attrs = self._get_attrs(host, headers, hn)
                    if not attrs:
                        self.logger.warning("  No attributes for '%s', skipping", hn)
                        stats["errors"] += 1
                        continue

                    name = (attrs.get("name") or "").strip()
                    display_name = _fake_hostname(name) if name else f"device-{i}"

                    self._create_device(hn, attrs, display_name, active, stats)

                    if (i + 1) % 50 == 0:
                        self.logger.info("  Progress: %d/%d", i + 1, len(hostnames))

                except Exception as exc:
                    self.logger.error("  Error on '%s': %s", hn, exc)
                    stats["errors"] += 1

            # Check what's still missing and generate CSV
            existing_names = set(Device.objects.values_list("name", flat=True))
            still_missing = []
            for hn in hostnames:
                attrs = self._get_attrs(host, headers, hn)
                if attrs:
                    name = (attrs.get("name") or "").strip()
                    display_name = _fake_hostname(name) if name else ""
                    if display_name and display_name not in existing_names:
                        still_missing.append((hn, attrs, display_name))
            self._save_missing_csv(still_missing)

        finally:
            self._logout(host, headers)

        self.logger.info("")
        self.logger.info("=" * 60)
        self.logger.info("LIST IMPORT COMPLETE")
        for k, v in stats.items():
            self.logger.info("  %s: %d", k, v)
        self.logger.info("=" * 60)
        return json.dumps(stats)

    # ------------------------------------------------------------------
    # Device creation
    # ------------------------------------------------------------------

    def _create_device(self, raw_hostname, raw_attrs, display_name, active_status, stats):
        """Create a single device with minimal identity + observations."""
        faker_on = _sanitize_enabled()
        serial = (raw_attrs.get("sn") or "").strip()
        display_serial = _fake_serial(serial) if (serial and faker_on) else serial
        vendor = _normalize_vendor(raw_attrs.get("vendor") or "Unknown") or "Unknown"
        model = (raw_attrs.get("model") or "Unknown").strip() or "Unknown"
        sub_type = (raw_attrs.get("subTypeName") or "Unknown").strip() or "Unknown"
        driver = (raw_attrs.get("driverName") or "").strip()

        # Build observation payload
        obs_payload = {
            "schema_version": 1,
            "meta": {"fetched_at": _utc_now_iso(), "source": "netbrain_import_demo",
                     "nb_hostname": raw_hostname},
            "data": {"remote": raw_attrs},
        }
        if _sanitize_enabled():
            obs_payload = _sanitize_json_tree(obs_payload, skip_keys=frozenset({
                "schema_version", "source", "vendor", "model",
                "subTypeName", "driverName", "ver", "os",
            }))

        # Create Nautobot objects
        mfr, _ = Manufacturer.objects.get_or_create(name=vendor)
        dtype, _ = DeviceType.objects.get_or_create(model=model, manufacturer=mfr)
        role, rc = Role.objects.get_or_create(name=sub_type)
        if rc:
            from django.contrib.contenttypes.models import ContentType
            role.content_types.add(ContentType.objects.get_for_model(Device))
        platform = None
        if driver:
            platform, _ = Platform.objects.get_or_create(name=driver)

        device = Device(
            name=display_name,
            serial=display_serial,
            device_type=dtype,
            platform=platform,
            role=role,
            status=active_status,
            location=self._get_fallback_location(active_status),
        )
        cf = device._custom_field_data or {}
        obs = cf.get(OBS_CF_KEY) or {}
        obs[OBS_NAMESPACE] = obs_payload
        obs["_sanitized"] = True
        cf[OBS_CF_KEY] = obs
        cf["system_of_record"] = "NetBrain"
        cf["last_synced_from_sor"] = _utc_now_iso()[:10]
        device._custom_field_data = cf
        device.validated_save()
        stats["created"] += 1

    def _update_observations(self, device, raw_hostname, raw_attrs, log_diff=False):
        """Refresh observations on an existing device without recreating it."""
        # Capture old remote data for diff
        old_remote = {}
        if log_diff:
            cf_old = device._custom_field_data or {}
            obs_old = cf_old.get(OBS_CF_KEY) or {}
            nb_old = obs_old.get(OBS_NAMESPACE) or {}
            old_remote = nb_old.get("data", {}).get("remote", {})

        obs_payload = {
            "schema_version": 1,
            "meta": {"fetched_at": _utc_now_iso(), "source": "netbrain_import_demo",
                     "nb_hostname": raw_hostname},
            "data": {"remote": raw_attrs},
        }
        if _sanitize_enabled():
            obs_payload = _sanitize_json_tree(obs_payload, skip_keys=frozenset({
                "schema_version", "source", "vendor", "model",
                "subTypeName", "driverName", "ver", "os",
            }))

        # Log field changes
        if log_diff and old_remote:
            new_remote = obs_payload.get("data", {}).get("remote", {})
            added = set(new_remote.keys()) - set(old_remote.keys())
            removed = set(old_remote.keys()) - set(new_remote.keys())
            changed = []
            for k in set(new_remote.keys()) & set(old_remote.keys()):
                if str(new_remote.get(k)) != str(old_remote.get(k)):
                    changed.append(k)
            if added:
                self.logger.info("    + Added fields: %s", sorted(added))
            if removed:
                self.logger.info("    - Removed fields: %s", sorted(removed))
            if changed:
                self.logger.info("    ~ Changed fields: %s", sorted(changed))
            if not added and not removed and not changed:
                self.logger.info("    (no changes)")

        cf = device._custom_field_data or {}
        obs = cf.get(OBS_CF_KEY) or {}
        obs[OBS_NAMESPACE] = obs_payload
        obs["_sanitized"] = True
        cf[OBS_CF_KEY] = obs
        cf["last_synced_from_sor"] = _utc_now_iso()[:10]
        device._custom_field_data = cf
        device.validated_save()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find_device(self, match_key):
        """Find a device by name or serial match key."""
        if match_key.startswith("serial:"):
            serial = match_key[7:]
            return Device.objects.filter(serial=serial).first()
        return Device.objects.filter(name=match_key).first()

    def _parse_device_list(self, device_list):
        """Parse hostnames from text input. Supports plain list or CSV (hostname is first column)."""
        hostnames = []
        for line in (device_list or "").strip().splitlines():
            line = line.strip()
            if not line or line.startswith("hostname,"):
                continue
            hn = line.split(",")[0].strip()
            if hn:
                hostnames.append(hn)
        return hostnames

    def _save_missing_csv(self, missing):
        """Generate CSV of missing devices and save as downloadable FileProxy."""
        if not missing:
            self.logger.info("No missing devices — CSV not generated.")
            return
        import io
        csv_buf = io.StringIO()
        csv_buf.write("hostname,faked_name,subTypeName,vendor,model,mgmtIP,site\n")
        for item in missing:
            # Support both (hn, attrs, display_name) tuples and (hn, attrs) tuples
            if len(item) == 3:
                hn, attrs, display_name = item
            else:
                hn, attrs = item
                name = (attrs.get("name") or "").strip()
                display_name = _fake_hostname(name) if name else ""
            vendor = _normalize_vendor(attrs.get("vendor") or "Unknown")
            model = (attrs.get("model") or "").strip().replace(",", ";")
            sub_type = attrs.get("subTypeName", "")
            mgmt_ip = (attrs.get("mgmtIP") or "").strip()
            site = (attrs.get("site") or "").strip().replace(",", ";")
            csv_buf.write(f"{hn},{display_name},{sub_type},{vendor},{model},{mgmt_ip},{site}\n")

        csv_content = csv_buf.getvalue()
        self.logger.info("Missing devices: %d (CSV generated)", len(missing))

        try:
            from django.core.files.base import ContentFile
            from nautobot.extras.models import FileProxy
            timestamp = _utc_now_iso()[:19].replace(":", "-")
            filename = f"netbrain_missing_devices_{timestamp}.csv"
            fp = FileProxy(name=filename)
            fp.file.save(filename, ContentFile(csv_content.encode("utf-8")))
            fp.save()
            base_url = "https://netbrain.crbg.nautobot.cloud"
            download_url = f"{base_url}/api/extras/file-proxies/{fp.pk}/download/"
            self.logger.info("CSV saved: %s", filename)
            self.logger.info("Download CSV: %s", download_url)
        except Exception as exc:
            self.logger.warning("Could not save CSV file: %s", exc)
            self.logger.info("CSV content logged below instead:")
            for line in csv_content.strip().split("\n")[:20]:
                self.logger.info("  %s", line)

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
        from django.contrib.contenttypes.models import ContentType
        from nautobot.dcim.models import Device, Location, LocationType
        lt, _ = LocationType.objects.get_or_create(name="Site", defaults={"nestable": False})
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

    def _scan_inventory(self, host, headers, target_types):
        """Scan full inventory, return list of (hostname, attrs) for target device types."""
        results = []
        skip = 0

        self.logger.info("Scanning inventory for %d target types...", len(target_types))

        for page in range(260):
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
                            time.sleep(0.1)
                            attrs = self._get_attrs(host, headers, hn)
                            if attrs:
                                results.append((hn, attrs))

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
