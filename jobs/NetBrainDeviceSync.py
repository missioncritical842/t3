"""NetBrain -> Nautobot Device Sync job.

Fetches devices and interfaces from NetBrain and creates/updates
corresponding objects in Nautobot. Respects NAUTOBOT_FAKER env var
for data sanitization and dry_run toggle for safe testing.
"""

from __future__ import annotations

import json

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
    _fake_site_path,
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

NETBRAIN_API_BASE = "/ServicesAPI/API/V1"


class NetBrainDeviceSync(Job):
    """Sync devices and interfaces from NetBrain into Nautobot."""

    class Meta:
        name = "NetBrain: Device Sync"
        description = (
            "Fetches devices and interfaces from NetBrain and creates/updates "
            "Nautobot objects. Supports NAUTOBOT_FAKER for data sanitization "
            "and dry_run mode for safe testing."
        )
        commit_default = False
        has_sensitive_variables = True

    # --- NetBrain connection ---
    host = StringVar(
        label="NetBrain Host",
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
    tenant_name = StringVar(
        label="Tenant Name",
        default="Initial Tenant",
        required=False,
    )
    domain_name = StringVar(
        label="Domain Name",
        default="Corebridge",
        required=False,
    )

    # --- Sync options ---
    dry_run = BooleanVar(
        label="Dry Run (no DB writes)",
        description="When ON, logs what would happen but writes nothing. Start with ON.",
        default=True,
        required=False,
    )
    sync_interfaces = BooleanVar(
        label="Sync Interfaces",
        description="Also fetch and sync interface data for each device.",
        default=True,
        required=False,
    )
    device_limit = IntegerVar(
        label="Device Limit",
        description="Max devices to sync (10-100). Use small numbers for testing.",
        default=10,
        required=False,
    )

    # --- Counters ---

    def run(self, host="", username="", password="", client_id="",
            client_secret="", tenant_name="", domain_name="",
            dry_run=True, sync_interfaces=True, device_limit=10, **kwargs):

        host = (host or "").rstrip("/")
        device_limit = max(10, min(int(device_limit or 10), 100))
        faker_on = _sanitize_enabled()

        self.logger.info("=" * 60)
        self.logger.info("NetBrain Device Sync")
        self.logger.info("  dry_run: %s", dry_run)
        self.logger.info("  NAUTOBOT_FAKER: %s", "ON" if faker_on else "OFF")
        self.logger.info("  device_limit: %d", device_limit)
        self.logger.info("  sync_interfaces: %s", sync_interfaces)
        self.logger.info("=" * 60)

        # Counters
        stats = {
            "devices_fetched": 0,
            "devices_created": 0,
            "devices_updated": 0,
            "interfaces_created": 0,
            "interfaces_updated": 0,
            "ips_created": 0,
            "skipped": 0,
            "errors": 0,
        }

        # --- Login ---
        token = self._nb_login(host, username, password, client_id, client_secret)
        if not token:
            return "FAILED: login"

        headers = {"Token": token, "Content-Type": "application/json"}

        try:
            # --- Set domain ---
            if tenant_name and domain_name:
                self._nb_set_domain(host, headers, tenant_name, domain_name)

            # --- Pre-fetch Nautobot lookups ---
            active_status = Status.objects.get(name="Active")
            planned_status = Status.objects.get(name="Planned")
            failed_status = Status.objects.get(name="Failed")
            status_map = {
                "Active": active_status,
                "Planned": planned_status,
                "Failed": failed_status,
            }

            # --- Fetch devices ---
            devices = self._nb_get_devices(host, headers, device_limit)
            stats["devices_fetched"] = len(devices)
            self.logger.info("Fetched %d devices from NetBrain", len(devices))

            # --- Process each device ---
            for i, dev_basic in enumerate(devices):
                hostname = (dev_basic.get("name") or "").strip()
                if not hostname:
                    stats["skipped"] += 1
                    continue

                self.logger.info("-" * 40)
                self.logger.info("Device %d/%d: %s", i + 1, len(devices), hostname)

                try:
                    # Fetch full attributes
                    attrs = self._nb_get_device_attrs(host, headers, hostname)
                    if not attrs:
                        self.logger.warning("  No attributes returned, skipping")
                        stats["skipped"] += 1
                        continue

                    # Sanitize if faker enabled
                    if faker_on:
                        attrs = _sanitize_device_attrs(attrs)
                        self.logger.info("  [FAKER] Device attrs sanitized")

                    # Sync device to Nautobot
                    device_obj = self._sync_device(attrs, active_status, dry_run, stats)

                    # Sync interfaces
                    if sync_interfaces and device_obj:
                        self._sync_device_interfaces(
                            host, headers, hostname, device_obj,
                            active_status, status_map, faker_on, dry_run, stats,
                        )

                except Exception as exc:
                    self.logger.error("  Error processing device %s: %s", hostname, exc)
                    stats["errors"] += 1

        finally:
            self._nb_logout(host, headers)

        # --- Summary ---
        self.logger.info("=" * 60)
        self.logger.info("SYNC COMPLETE")
        for k, v in stats.items():
            self.logger.info("  %s: %d", k, v)
        self.logger.info("=" * 60)

        return json.dumps(stats)

    # ------------------------------------------------------------------
    # NetBrain API helpers
    # ------------------------------------------------------------------

    def _nb_login(self, host, username, password, client_id, client_secret):
        url = f"{host}{NETBRAIN_API_BASE}/Session"
        body = {"username": username, "password": password}
        if client_id:
            body["authentication_id"] = client_id
        if client_secret:
            body["client_secret"] = client_secret

        self.logger.info("Logging in to NetBrain...")
        try:
            resp = requests.post(url, json=body,
                                 headers={"Content-Type": "application/json"},
                                 verify=False, timeout=15)
        except Exception as exc:
            self.logger.error("Login failed: %s", exc)
            return None

        if resp.status_code != 200:
            self.logger.error("Login HTTP %s: %s", resp.status_code, resp.text[:500])
            return None

        token = resp.json().get("token", "")
        if token:
            self.logger.info("Login OK")
        return token or None

    def _nb_set_domain(self, host, headers, tenant_name, domain_name):
        url = f"{host}{NETBRAIN_API_BASE}/Session/CurrentDomain"
        self.logger.info("Setting domain: %s / %s", tenant_name, domain_name)
        try:
            resp = requests.put(
                url,
                json={"tenantName": tenant_name, "domainName": domain_name},
                headers=headers, verify=False, timeout=15,
            )
            if resp.status_code == 200:
                self.logger.info("Domain set OK")
            else:
                self.logger.warning("Set domain HTTP %s: %s", resp.status_code, resp.text[:300])
        except Exception as exc:
            self.logger.warning("Set domain failed: %s", exc)

    def _nb_get_devices(self, host, headers, limit):
        url = f"{host}{NETBRAIN_API_BASE}/CMDB/Devices"
        all_devices = []
        skip = 0
        page_size = min(limit, 100)

        while len(all_devices) < limit:
            try:
                resp = requests.get(url, headers=headers, verify=False, timeout=30,
                                    params={"skip": skip, "limit": page_size})
                if resp.status_code != 200:
                    self.logger.warning("Devices HTTP %s at skip=%d", resp.status_code, skip)
                    break

                data = resp.json()
                devices = data.get("devices", data.get("data", []))
                if not devices:
                    break

                all_devices.extend(devices)
                skip += len(devices)

                if len(devices) < page_size:
                    break
            except Exception as exc:
                self.logger.error("Device fetch failed: %s", exc)
                break

        return all_devices[:limit]

    def _nb_get_device_attrs(self, host, headers, hostname):
        url = f"{host}{NETBRAIN_API_BASE}/CMDB/Devices/Attributes"
        try:
            resp = requests.get(url, headers=headers, verify=False, timeout=15,
                                params={"hostname": hostname})
            if resp.status_code != 200:
                return None
            data = resp.json()
            return data.get("attributes", data)
        except Exception:
            return None

    def _nb_get_interfaces(self, host, headers, hostname):
        url = f"{host}{NETBRAIN_API_BASE}/CMDB/Interfaces"
        try:
            resp = requests.get(url, headers=headers, verify=False, timeout=30,
                                params={"hostname": hostname})
            if resp.status_code != 200:
                return []
            data = resp.json()
            return data.get("interfaces", data.get("data", []))
        except Exception:
            return []

    def _nb_get_interface_attrs(self, host, headers, hostname, intf_name):
        url = f"{host}{NETBRAIN_API_BASE}/CMDB/Interfaces/Attributes"
        try:
            resp = requests.get(url, headers=headers, verify=False, timeout=15,
                                params={"hostname": hostname, "interfaceName": intf_name})
            if resp.status_code != 200:
                return None
            data = resp.json()
            attrs = data.get("attributes", data)
            if isinstance(attrs, dict) and len(attrs) == 1:
                # Response is {interface_name: {actual_attrs}}
                key = list(attrs.keys())[0]
                if isinstance(attrs[key], dict):
                    return attrs[key]
            return attrs
        except Exception:
            return None

    def _nb_logout(self, host, headers):
        try:
            requests.delete(f"{host}{NETBRAIN_API_BASE}/Session",
                            headers=headers, verify=False, timeout=10)
            self.logger.info("Logged out of NetBrain.")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Nautobot sync logic
    # ------------------------------------------------------------------

    def _sync_device(self, attrs, active_status, dry_run, stats):
        """Create or update a Nautobot Device from NetBrain attributes."""
        name = (attrs.get("name") or "").strip()
        if not name:
            return None

        vendor_name = (attrs.get("vendor") or "Unknown").strip() or "Unknown"
        model_name = (attrs.get("model") or "Unknown").strip() or "Unknown"
        sub_type = (attrs.get("subTypeName") or "Unknown").strip() or "Unknown"
        driver = (attrs.get("driverName") or "").strip()
        serial = (attrs.get("sn") or "").strip()
        asset_tag = (attrs.get("assetTag") or "").strip() or None
        descr = (attrs.get("descr") or "").strip()
        site_path = attrs.get("site", "")

        # Resolve or create related objects
        manufacturer = self._get_or_create_manufacturer(vendor_name, dry_run)
        device_type = self._get_or_create_device_type(manufacturer, model_name, dry_run)
        role = self._get_or_create_role(sub_type, dry_run)
        platform = self._get_or_create_platform(driver, dry_run) if driver else None
        location = self._get_or_create_location(site_path, dry_run)

        if dry_run:
            self.logger.info("  [DRY-RUN] Would sync device: %s", name)
            self.logger.info("    manufacturer=%s model=%s role=%s", vendor_name, model_name, sub_type)
            self.logger.info("    serial=%s site=%s", serial, site_path)
            return None

        # Create or update device
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
            },
        )

        if created:
            stats["devices_created"] += 1
            self.logger.info("  CREATED device: %s", name)
        else:
            # Update fields
            changed = False
            if serial and device.serial != serial:
                device.serial = serial
                changed = True
            if asset_tag and device.asset_tag != asset_tag:
                device.asset_tag = asset_tag
                changed = True
            if descr and device.comments != descr:
                device.comments = descr
                changed = True
            if platform and device.platform != platform:
                device.platform = platform
                changed = True
            if changed:
                device.validated_save()
                stats["devices_updated"] += 1
                self.logger.info("  UPDATED device: %s", name)
            else:
                self.logger.info("  UNCHANGED device: %s", name)

        # Set platform if available
        if platform and device.platform != platform:
            device.platform = platform
            device.validated_save()

        # Sync tags
        tags = attrs.get("assignTags", [])
        if tags and isinstance(tags, list):
            for tag_name in tags:
                tag, _ = Tag.objects.get_or_create(name=tag_name)
                device.tags.add(tag)

        # Set custom fields
        cf_data = device._custom_field_data or {}
        cf_data["system_of_record"] = "NetBrain"
        cf_data["last_synced_from_sor"] = _utc_now_iso()[:10]  # date only
        # Store raw NetBrain attrs as observation
        obs = cf_data.get("observations") or {}
        if not isinstance(obs, dict):
            obs = {}
        obs["netbrain"] = {
            "data": {"remote": attrs},
            "meta": {"fetched_at": _utc_now_iso(), "source": "netbrain_device_sync"},
            "schema_version": 1,
        }
        if _sanitize_enabled():
            obs["_sanitized"] = True
        cf_data["observations"] = obs
        device._custom_field_data = cf_data
        device.validated_save()

        # Sync management IP
        mgmt_ip_str = (attrs.get("mgmtIP") or "").strip()
        if mgmt_ip_str:
            self._sync_mgmt_ip(device, mgmt_ip_str, active_status, stats)

        return device

    def _sync_device_interfaces(self, host, headers, nb_hostname, device_obj,
                                 active_status, status_map, faker_on, dry_run, stats):
        """Fetch and sync interfaces for a device."""
        intf_names = self._nb_get_interfaces(host, headers, nb_hostname)
        if not intf_names:
            self.logger.info("  No interfaces found")
            return

        self.logger.info("  Found %d interfaces", len(intf_names))

        for intf_name in intf_names[:50]:  # cap at 50 per device
            if not isinstance(intf_name, str):
                continue
            intf_name = intf_name.strip()
            if not intf_name:
                continue

            # Fetch attributes
            intf_attrs = self._nb_get_interface_attrs(host, headers, nb_hostname, intf_name)
            if not intf_attrs:
                continue

            if faker_on:
                intf_attrs = _sanitize_interface_attrs(intf_attrs)

            nb_name = (intf_attrs.get("name") or intf_name).strip()
            intf_status_str = _map_intf_status(intf_attrs.get("intfStatus", ""))
            intf_status = status_map.get(intf_status_str, active_status)
            intf_type = _guess_interface_type(nb_name, intf_attrs.get("speed", ""))
            description = (intf_attrs.get("descr") or "").strip()
            mac = (intf_attrs.get("macAddr") or "").strip() or None

            if dry_run:
                self.logger.info("  [DRY-RUN] Would sync interface: %s (%s)", nb_name, intf_type)
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

            # Sync IPs on this interface
            ips = intf_attrs.get("ips", [])
            if isinstance(ips, list):
                for ip_entry in ips:
                    if not isinstance(ip_entry, dict):
                        continue
                    cidr = _nb_ip_to_cidr(ip_entry)
                    if cidr:
                        self._sync_interface_ip(intf_obj, cidr, active_status, dry_run, stats)

    def _sync_mgmt_ip(self, device, ip_str, active_status, stats):
        """Create management IP and assign as primary_ip4."""
        cidr = _normalize_ip(ip_str)
        if not cidr:
            return

        self._ensure_prefix(cidr, active_status)

        ip_obj, created = IPAddress.objects.get_or_create(
            address=cidr,
            defaults={"status": active_status},
        )
        if created:
            stats["ips_created"] += 1

        # Create mgmt interface if needed
        mgmt_intf, _ = Interface.objects.get_or_create(
            device=device,
            name="mgmt0",
            defaults={
                "type": "virtual",
                "status": active_status,
            },
        )

        IPAddressToInterface.objects.get_or_create(
            ip_address=ip_obj,
            interface=mgmt_intf,
        )

        if device.primary_ip4 != ip_obj:
            device.primary_ip4 = ip_obj
            device.validated_save()

    def _sync_interface_ip(self, intf_obj, cidr, active_status, dry_run, stats):
        """Create an IP address and assign to an interface."""
        if dry_run:
            return

        self._ensure_prefix(cidr, active_status)

        ip_obj, created = IPAddress.objects.get_or_create(
            address=cidr,
            defaults={"status": active_status},
        )
        if created:
            stats["ips_created"] += 1

        IPAddressToInterface.objects.get_or_create(
            ip_address=ip_obj,
            interface=intf_obj,
        )

    def _ensure_prefix(self, cidr, active_status):
        """Ensure a covering /24 prefix exists."""
        try:
            import ipaddress as _ipaddress
            network = _ipaddress.ip_interface(cidr).network
            covering = (
                str(network.supernet(new_prefix=24))
                if network.prefixlen > 24
                else str(network)
            )
            ns = Namespace.objects.get(name="Global")
            Prefix.objects.get_or_create(
                prefix=covering,
                namespace=ns,
                defaults={"status": active_status},
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Nautobot object helpers
    # ------------------------------------------------------------------

    def _get_or_create_manufacturer(self, name, dry_run):
        if dry_run:
            return None
        obj, _ = Manufacturer.objects.get_or_create(name=name)
        return obj

    def _get_or_create_device_type(self, manufacturer, model, dry_run):
        if dry_run:
            return None
        obj, _ = DeviceType.objects.get_or_create(
            model=model,
            manufacturer=manufacturer,
        )
        return obj

    def _get_or_create_role(self, name, dry_run):
        if dry_run:
            return None
        obj, created = Role.objects.get_or_create(name=name)
        if created:
            from django.contrib.contenttypes.models import ContentType
            ct = ContentType.objects.get_for_model(Device)
            obj.content_types.add(ct)
        return obj

    def _get_or_create_platform(self, name, dry_run):
        if dry_run:
            return None
        if not name:
            return None
        obj, _ = Platform.objects.get_or_create(name=name)
        return obj

    def _get_or_create_location(self, site_path, dry_run):
        """Create Location hierarchy from NetBrain site path."""
        if dry_run:
            return None

        segments = _parse_site_path(site_path)
        if not segments:
            # Fallback to a default location
            segments = ["Unassigned"]

        # Skip "My Network" prefix -- it's a NetBrain structural root
        if segments and segments[0] == "My Network":
            segments = segments[1:]
        if not segments:
            segments = ["Unassigned"]

        # Ensure LocationTypes exist
        region_type, _ = LocationType.objects.get_or_create(
            name="Region",
            defaults={"nestable": True},
        )
        site_type, _ = LocationType.objects.get_or_create(
            name="Site",
            defaults={"nestable": False},
        )
        # Site type must be allowed as child of Region
        if not site_type.parent:
            site_type.parent = region_type
            site_type.validated_save()

        # Build hierarchy: all but last = Region chain, last = Site
        parent = None
        for seg in segments[:-1]:
            loc, _ = Location.objects.get_or_create(
                name=seg,
                location_type=region_type,
                defaults={
                    "status": Status.objects.get(name="Active"),
                    "parent": parent,
                },
            )
            parent = loc

        # Last segment is the Site
        site_name = segments[-1]
        location, _ = Location.objects.get_or_create(
            name=site_name,
            location_type=site_type,
            defaults={
                "status": Status.objects.get(name="Active"),
                "parent": parent,
            },
        )
        return location


register_jobs(NetBrainDeviceSync)
