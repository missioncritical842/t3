"""NetBrain -> Nautobot Import Demo.

Fetches real network devices from NetBrain datacenter sites and imports
them into Nautobot with full field mapping. NAUTOBOT_FAKER is always ON
for this demo job to protect sensitive data. Logs are sanitized.
"""

from __future__ import annotations

import json
import time

import requests
import urllib3

from nautobot.apps.jobs import BooleanVar, IntegerVar, Job, StringVar, register_jobs
from nautobot.dcim.models import (
    Device,
    DeviceType,
    Interface,
    Location,
    LocationType,
    Manufacturer,
    Platform,
)
from nautobot.extras.models import Role, Status, Tag
from nautobot.ipam.models import IPAddress, IPAddressToInterface, Namespace, Prefix

from .netbrain_utils import (
    _fake_hostname,
    _fake_ip,
    _fake_ip_cidr,
    _fake_serial,
    _guess_interface_type,
    _map_intf_status,
    _nb_ip_to_cidr,
    _normalize_ip,
    _parse_site_path,
    _sanitize_device_attrs,
    _sanitize_enabled,
    _sanitize_interface_attrs,
    _sanitize_json_tree,
    _utc_now_iso,
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

V1 = "/ServicesAPI/API/V1"

# Network device types worth importing
NETWORK_TYPES = {
    "Cisco IOS Switch", "Cisco Router", "Cisco Nexus Switch",
    "Cisco ACI Spine Switch", "Arista Switch", "Palo Alto Firewall",
    "F5 Load Balancer", "Aruba Switch", "SilverPeak WAN Optimizer",
    "Cisco Meraki Firewall", "Cisco Meraki Switch", "Cisco WLC",
    "Cisco Meraki AP", "Aruba IAP", "Cisco ISE", "LWAP",
    "Cisco Meraki Controller", "Cisco Meraki Z-Series Gateway",
    "AWS DX Router", "NetScout Router",
}


def _mask(val, kind="str"):
    """Mask a value for safe logging."""
    if not val:
        return "(empty)"
    s = str(val)
    if kind == "ip":
        parts = s.split(".")
        if len(parts) == 4:
            return f"{parts[0]}.x.x.{parts[3]}"
        return "x.x.x.x"
    if kind == "serial":
        return f"{s[:3]}***"
    if kind == "host":
        return f"{s[:4]}***" if len(s) > 4 else "***"
    return f"{s[:6]}..." if len(s) > 6 else s


class NetBrainImportDemo(Job):
    """Import network devices from NetBrain into Nautobot (demo with faker)."""

    class Meta:
        name = "NetBrain: Import Demo"
        description = (
            "Fetches network devices from NetBrain datacenter sites and imports "
            "into Nautobot. Always fakes sensitive data for safe demo. "
            "Creates Manufacturers, DeviceTypes, Roles, Platforms, Locations, "
            "Devices, Interfaces, and IPs."
        )
        commit_default = False
        has_sensitive_variables = True

    host = StringVar(default="https://10.134.98.133", label="NetBrain Host")
    username = StringVar(default="nautobotapi", label="Username")
    password = StringVar(default="aB1psTV?veX5dPBf@jx%kese56RB", required=False, label="Password",
                         description="Or set NETBRAIN_PASSWORD env var")
    client_id = StringVar(default="lpf4oqee-3dmfvrwg", required=False, label="Client ID",
                          description="Or set NETBRAIN_CLIENT_ID env var")
    client_secret = StringVar(default="uBZY15clyPuV9YhuTNkp3iCxKDbXwqjA", required=False, label="Client Secret",
                              description="Or set NETBRAIN_CLIENT_SECRET env var")

    dry_run = BooleanVar(
        label="Dry Run",
        description="Log what would happen without writing to DB.",
        default=True, required=False,
    )
    device_limit = IntegerVar(
        label="Device Limit",
        description="Max network devices to import (1-20).",
        default=5, required=False,
    )
    sync_interfaces = BooleanVar(
        label="Sync Interfaces",
        description="Also import interfaces and IPs for each device.",
        default=True, required=False,
    )

    def run(self, host="", username="", password="", client_id="",
            client_secret="", dry_run=True, device_limit=5,
            sync_interfaces=True, **kwargs):

        import os
        host = (host or "").rstrip("/")
        # Env var fallbacks when form fields are blank
        username = (username or "").strip() or os.environ.get("NETBRAIN_USERNAME", "nautobotapi")
        password = (password or "").strip() or os.environ.get("NETBRAIN_PASSWORD", "")
        client_id = (client_id or "").strip() or os.environ.get("NETBRAIN_CLIENT_ID", "")
        client_secret = (client_secret or "").strip() or os.environ.get("NETBRAIN_CLIENT_SECRET", "")
        device_limit = max(1, min(int(device_limit or 5), 20))
        # Always fake for demo safety
        faker_on = True

        self.logger.info("=" * 60)
        self.logger.info("NetBrain Import Demo")
        self.logger.info("  dry_run: %s", dry_run)
        self.logger.info("  faker: ALWAYS ON (demo mode)")
        self.logger.info("  device_limit: %d", device_limit)
        self.logger.info("  sync_interfaces: %s", sync_interfaces)
        self.logger.info("=" * 60)

        stats = {
            "devices_fetched": 0, "devices_created": 0, "devices_updated": 0,
            "interfaces_created": 0, "interfaces_updated": 0,
            "ips_created": 0, "locations_created": 0,
            "skipped": 0, "errors": 0,
        }

        # --- Login with retry ---
        token = self._login(host, username, password, client_id, client_secret)
        if not token:
            return "FAILED: login"
        headers = {"Token": token, "Content-Type": "application/json"}

        try:
            # --- Set domain ---
            self._set_domain(host, headers)

            # --- Pre-fetch Nautobot statuses ---
            active_status = Status.objects.get(name="Active")
            planned_status = Status.objects.get(name="Planned")
            failed_status = Status.objects.get(name="Failed")
            status_map = {"Active": active_status, "Planned": planned_status, "Failed": failed_status}

            # --- Find network devices via site queries ---
            network_devices = self._find_network_devices(host, headers, device_limit)
            stats["devices_fetched"] = len(network_devices)

            if not network_devices:
                self.logger.warning("No network devices found in datacenter sites")
                return json.dumps(stats)

            # --- Import each device ---
            for i, (hostname, raw_attrs) in enumerate(network_devices):
                self.logger.info("-" * 40)
                # Sanitize attrs for import AND logging
                attrs = _sanitize_device_attrs(raw_attrs)
                safe_name = attrs.get("name", "?")
                sub_type = attrs.get("subTypeName", "?")

                self.logger.info("Device %d/%d: %s (%s)",
                                 i + 1, len(network_devices), safe_name, sub_type)

                try:
                    device_obj = self._import_device(attrs, active_status, dry_run, stats)

                    if sync_interfaces and device_obj and not dry_run:
                        self._import_interfaces(
                            host, headers, hostname, device_obj,
                            active_status, status_map, dry_run, stats,
                        )
                    elif sync_interfaces and dry_run:
                        # Still fetch and log interface count
                        intf_names = self._get_interfaces(host, headers, hostname)
                        self.logger.info("  [DRY-RUN] Would sync %d interfaces", len(intf_names))

                except Exception as exc:
                    self.logger.error("  Error: %s", exc)
                    stats["errors"] += 1

                time.sleep(0.5)  # rate limit protection

        finally:
            self._logout(host, headers)

        self.logger.info("=" * 60)
        self.logger.info("IMPORT COMPLETE")
        for k, v in stats.items():
            self.logger.info("  %s: %d", k, v)
        self.logger.info("=" * 60)
        return json.dumps(stats)

    # ------------------------------------------------------------------
    # NetBrain API
    # ------------------------------------------------------------------

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
        """Set tenant/domain using UUIDs (R12.x requirement)."""
        try:
            r = requests.get(f"{host}{V1}/CMDB/Tenants", headers=headers,
                             verify=False, timeout=30)
            if r.status_code != 200:
                return
            tenants = r.json().get("tenants", [])
            if not tenants:
                return
            tid = tenants[0].get("tenantId", "")

            r2 = requests.get(f"{host}{V1}/CMDB/Domains", params={"tenantId": tid},
                              headers=headers, verify=False, timeout=30)
            if r2.status_code != 200:
                return
            domains = r2.json().get("domains", [])
            if not domains:
                return
            did = domains[0].get("domainId", "")

            r3 = requests.put(f"{host}{V1}/Session/CurrentDomain",
                              json={"tenantId": tid, "domainId": did},
                              headers=headers, verify=False, timeout=30)
            self.logger.info("Domain set: HTTP %s", r3.status_code)
        except Exception as exc:
            self.logger.warning("Domain setup: %s", exc)

    def _find_network_devices(self, host, headers, limit):
        """Query datacenter sites, sample hostnames, find network devices."""
        import random
        site_hostnames = []

        sites = [
            "My Network/DataCenter-AMER/AM5/AM5 - Data Center",
            "My Network/DataCenter-AMER/AM6/AM6 - Data Center",
        ]
        for site_path in sites:
            try:
                r = requests.get(f"{host}{V1}/CMDB/Sites/Devices",
                                 params={"sitePath": site_path},
                                 headers=headers, verify=False, timeout=60)
                if r.status_code == 200:
                    devs = r.json().get("devices", [])
                    self.logger.info("Site '%s': %d devices", site_path.split("/")[-1], len(devs))
                    for d in devs:
                        hn = d.get("hostname", "")
                        if hn:
                            site_hostnames.append(hn)
            except Exception as exc:
                self.logger.warning("Site query failed: %s", exc)

        if not site_hostnames:
            return []

        self.logger.info("Total site hostnames: %d", len(site_hostnames))

        # Sample and probe for network device types
        random.seed(42)
        sample = random.sample(site_hostnames, min(80, len(site_hostnames)))
        results = []
        probed = 0

        for hn in sample:
            if len(results) >= limit:
                break
            try:
                time.sleep(0.5)
                r = requests.get(f"{host}{V1}/CMDB/Devices/Attributes",
                                 params={"hostname": hn},
                                 headers=headers, verify=False, timeout=30)
                if r.status_code == 200:
                    attrs = r.json().get("attributes", {})
                    st = attrs.get("subTypeName", "")
                    probed += 1
                    if st in NETWORK_TYPES:
                        results.append((hn, attrs))
                        self.logger.info("  Found: %s (%s)", _mask(hn, "host"), st)
            except Exception:
                pass

        self.logger.info("Probed %d hostnames, found %d network devices", probed, len(results))
        return results

    def _get_interfaces(self, host, headers, hostname):
        try:
            r = requests.get(f"{host}{V1}/CMDB/Interfaces",
                             params={"hostname": hostname},
                             headers=headers, verify=False, timeout=30)
            if r.status_code == 200:
                return r.json().get("interfaces", [])
        except Exception:
            pass
        return []

    def _get_interface_attrs(self, host, headers, hostname, intf_name):
        try:
            r = requests.get(f"{host}{V1}/CMDB/Interfaces/Attributes",
                             params={"hostname": hostname, "interfaceName": intf_name},
                             headers=headers, verify=False, timeout=30)
            if r.status_code == 200:
                attrs = r.json().get("attributes", {})
                if isinstance(attrs, dict) and len(attrs) == 1:
                    key = list(attrs.keys())[0]
                    if isinstance(attrs[key], dict):
                        return attrs[key]
                return attrs
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

    # ------------------------------------------------------------------
    # Nautobot import logic
    # ------------------------------------------------------------------

    def _import_device(self, attrs, active_status, dry_run, stats):
        """Create/update a Nautobot Device from sanitized NetBrain attrs."""
        name = (attrs.get("name") or "").strip()
        if not name:
            stats["skipped"] += 1
            return None

        vendor = (attrs.get("vendor") or "Unknown").strip() or "Unknown"
        model = (attrs.get("model") or "Unknown").strip() or "Unknown"
        sub_type = (attrs.get("subTypeName") or "Unknown").strip() or "Unknown"
        driver = (attrs.get("driverName") or "").strip()
        serial = (attrs.get("sn") or "").strip()
        asset_tag = (attrs.get("assetTag") or "").strip() or None
        descr = (attrs.get("descr") or "").strip()
        site_path = attrs.get("site", "")
        ver = (attrs.get("ver") or "").strip()

        self.logger.info("  vendor=%s model=%s", vendor, model)
        self.logger.info("  site=%s", site_path)

        if dry_run:
            self.logger.info("  [DRY-RUN] Would create device: %s", name)
            return None

        # Create related objects
        manufacturer, _ = Manufacturer.objects.get_or_create(name=vendor)
        device_type, _ = DeviceType.objects.get_or_create(
            model=model, manufacturer=manufacturer)
        role, role_created = Role.objects.get_or_create(name=sub_type)
        if role_created:
            from django.contrib.contenttypes.models import ContentType
            ct = ContentType.objects.get_for_model(Device)
            role.content_types.add(ct)

        platform = None
        if driver:
            platform, _ = Platform.objects.get_or_create(name=driver)

        location = self._get_or_create_location(site_path, active_status, stats)

        # Create/update device
        device, created = Device.objects.get_or_create(
            name=name,
            defaults={
                "device_type": device_type,
                "role": role,
                "status": active_status,
                "location": location,
                "serial": serial or "",
                "asset_tag": asset_tag,
                "comments": descr,
                "platform": platform,
            },
        )

        if created:
            stats["devices_created"] += 1
            self.logger.info("  CREATED: %s", name)
        else:
            changed = []
            if serial and device.serial != serial:
                device.serial = serial
                changed.append("serial")
            if descr and device.comments != descr:
                device.comments = descr
                changed.append("comments")
            if platform and device.platform != platform:
                device.platform = platform
                changed.append("platform")
            if changed:
                device.validated_save()
                stats["devices_updated"] += 1
                self.logger.info("  UPDATED: %s (%s)", name, ", ".join(changed))
            else:
                self.logger.info("  UNCHANGED: %s", name)

        # Tags
        tags = attrs.get("assignTags", [])
        if isinstance(tags, list):
            for t in tags:
                tag, _ = Tag.objects.get_or_create(name=t)
                device.tags.add(tag)

        # Custom fields
        cf = device._custom_field_data or {}
        cf["system_of_record"] = "NetBrain"
        cf["last_synced_from_sor"] = _utc_now_iso()[:10]
        # Store sanitized observation
        obs = cf.get("observations") or {}
        if not isinstance(obs, dict):
            obs = {}
        sanitized_attrs = _sanitize_json_tree(attrs, skip_keys=frozenset({
            "vendor", "model", "subTypeName", "driverName", "ver", "os",
            "hasBGPConfig", "hasOSPFConfig", "hasMulticastConfig",
            "hasMCLAGConfig", "hasNATConfig", "isHA",
        }))
        obs["netbrain"] = {
            "data": {"remote": sanitized_attrs},
            "meta": {"fetched_at": _utc_now_iso(), "source": "netbrain_import_demo"},
            "schema_version": 1,
        }
        obs["_sanitized"] = True
        cf["observations"] = obs
        device._custom_field_data = cf
        device.validated_save()

        # Management IP
        mgmt_ip = (attrs.get("mgmtIP") or "").strip()
        if mgmt_ip:
            self._sync_mgmt_ip(device, mgmt_ip, active_status, stats)

        return device

    def _import_interfaces(self, host, headers, nb_hostname, device_obj,
                            active_status, status_map, dry_run, stats):
        """Fetch and import interfaces for a device."""
        intf_names = self._get_interfaces(host, headers, nb_hostname)
        if not intf_names:
            return

        self.logger.info("  Importing %d interfaces...", len(intf_names))

        for intf_name in intf_names[:30]:  # cap per device
            if not isinstance(intf_name, str) or not intf_name.strip():
                continue

            time.sleep(0.3)
            raw_attrs = self._get_interface_attrs(host, headers, nb_hostname, intf_name)
            if not raw_attrs:
                continue

            # Always sanitize
            attrs = _sanitize_interface_attrs(raw_attrs)

            nb_name = (attrs.get("name") or intf_name).strip()
            intf_status_str = _map_intf_status(attrs.get("intfStatus", ""))
            intf_status = status_map.get(intf_status_str, active_status)
            intf_type = _guess_interface_type(nb_name, attrs.get("speed", ""))
            description = (attrs.get("descr") or "").strip()
            mac = (attrs.get("macAddr") or "").strip() or None

            if dry_run:
                continue

            intf_obj, created = Interface.objects.get_or_create(
                device=device_obj,
                name=nb_name,
                defaults={
                    "type": intf_type,
                    "status": intf_status,
                    "description": description,
                    "mac_address": mac,
                },
            )

            if created:
                stats["interfaces_created"] += 1
            else:
                changed = False
                if description and intf_obj.description != description:
                    intf_obj.description = description
                    changed = True
                if mac and intf_obj.mac_address != mac:
                    intf_obj.mac_address = mac
                    changed = True
                if changed:
                    intf_obj.validated_save()
                    stats["interfaces_updated"] += 1

            # Sync IPs
            ips = attrs.get("ips", [])
            if isinstance(ips, list):
                for ip_entry in ips:
                    if isinstance(ip_entry, dict):
                        cidr = _nb_ip_to_cidr(ip_entry)
                        if cidr:
                            self._sync_ip(intf_obj, cidr, active_status, stats)

    def _sync_mgmt_ip(self, device, ip_str, active_status, stats):
        cidr = _normalize_ip(ip_str)
        if not cidr:
            return

        self._ensure_prefix(cidr, active_status)
        ip_obj, created = IPAddress.objects.get_or_create(
            address=cidr, defaults={"status": active_status})
        if created:
            stats["ips_created"] += 1

        # Use the actual mgmtIntf name if we have it, else "mgmt0"
        mgmt_intf, _ = Interface.objects.get_or_create(
            device=device, name="mgmt0",
            defaults={"type": "virtual", "status": active_status})

        IPAddressToInterface.objects.get_or_create(
            ip_address=ip_obj, interface=mgmt_intf)

        if device.primary_ip4 != ip_obj:
            device.primary_ip4 = ip_obj
            device.validated_save()

    def _sync_ip(self, intf_obj, cidr, active_status, stats):
        self._ensure_prefix(cidr, active_status)
        ip_obj, created = IPAddress.objects.get_or_create(
            address=cidr, defaults={"status": active_status})
        if created:
            stats["ips_created"] += 1
        IPAddressToInterface.objects.get_or_create(
            ip_address=ip_obj, interface=intf_obj)

    def _ensure_prefix(self, cidr, active_status):
        try:
            import ipaddress
            network = ipaddress.ip_interface(cidr).network
            covering = (str(network.supernet(new_prefix=24))
                        if network.prefixlen > 24 else str(network))
            ns = Namespace.objects.get(name="Global")
            Prefix.objects.get_or_create(
                prefix=covering, namespace=ns,
                defaults={"status": active_status})
        except Exception:
            pass

    def _get_or_create_location(self, site_path, active_status, stats):
        segments = _parse_site_path(site_path)
        if not segments:
            segments = ["Unassigned"]
        if segments and segments[0] == "My Network":
            segments = segments[1:]
        if not segments:
            segments = ["Unassigned"]

        # Ensure LocationTypes
        region_type, _ = LocationType.objects.get_or_create(
            name="Region", defaults={"nestable": True})
        site_type, _ = LocationType.objects.get_or_create(
            name="Site", defaults={"nestable": False})
        if not site_type.parent:
            site_type.parent = region_type
            site_type.validated_save()

        # Build hierarchy
        parent = None
        for seg in segments[:-1]:
            loc, created = Location.objects.get_or_create(
                name=seg, location_type=region_type,
                defaults={"status": active_status, "parent": parent})
            if created:
                stats["locations_created"] += 1
            parent = loc

        site_name = segments[-1]
        location, created = Location.objects.get_or_create(
            name=site_name, location_type=site_type,
            defaults={"status": active_status, "parent": parent})
        if created:
            stats["locations_created"] += 1

        return location


register_jobs(NetBrainImportDemo)
