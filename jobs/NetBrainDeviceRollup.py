"""NetBrain Observations Rollup.

Reads observations["netbrain"]["data"]["remote"] from each Device and
rolls up into proper Nautobot fields:
  - Management IP -> IPAddress + primary_ip4
  - Site path -> Location hierarchy
  - Software version -> Device.software_version (if available)
  - Tags from assignTags
  - system_of_record / last_synced_from_sor custom fields

Does NOT re-fetch from NetBrain API. Works entirely from stored observations.
"""

from __future__ import annotations

import json

from nautobot.apps.jobs import BooleanVar, Job, StringVar, register_jobs
from nautobot.dcim.models import (
    Device,
    Interface,
    Location,
    LocationType,
)
from nautobot.extras.models import Status, Tag
from nautobot.ipam.models import IPAddress, IPAddressToInterface, Namespace, Prefix

from .netbrain_utils import (
    _guess_interface_type,
    _map_intf_status,
    _nb_ip_to_cidr,
    _normalize_ip,
    _parse_site_path,
    _utc_now_iso,
)

OBS_CF_KEY = "observations"
OBS_NAMESPACE = "netbrain"


class NetBrainDeviceRollup(Job):
    """Roll up NetBrain observations into Nautobot device fields."""

    class Meta:
        name = "NetBrain: Device Rollup"
        description = (
            "Reads stored NetBrain observations from each device and rolls up "
            "management IPs, locations, tags, and software versions. "
            "Does not contact NetBrain API."
        )
        commit_default = False
        has_sensitive_variables = False

    dry_run = BooleanVar(
        label="Dry Run", default=True, required=False,
        description="Log what would change without writing.",
    )
    rollup_ips = BooleanVar(
        label="Roll Up Management IPs", default=True, required=False,
        description="Create mgmt IP and set as primary_ip4.",
    )
    rollup_locations = BooleanVar(
        label="Roll Up Locations", default=True, required=False,
        description="Create Location hierarchy from site path and reassign device.",
    )
    rollup_tags = BooleanVar(
        label="Roll Up Tags", default=True, required=False,
        description="Apply assignTags from NetBrain as Nautobot Tags.",
    )

    def run(self, dry_run=True, rollup_ips=True, rollup_locations=True,
            rollup_tags=True, **kwargs):

        self.logger.info("=" * 60)
        self.logger.info("NetBrain Device Rollup")
        self.logger.info("  dry_run: %s", dry_run)
        self.logger.info("  rollup_ips: %s", rollup_ips)
        self.logger.info("  rollup_locations: %s", rollup_locations)
        self.logger.info("  rollup_tags: %s", rollup_tags)
        self.logger.info("=" * 60)

        stats = {
            "devices_processed": 0,
            "ips_created": 0,
            "ips_assigned": 0,
            "locations_created": 0,
            "locations_reassigned": 0,
            "tags_added": 0,
            "skipped": 0,
            "errors": 0,
        }

        active = Status.objects.get(name="Active")

        # Find all devices with NetBrain observations
        devices = Device.objects.all()
        self.logger.info("Checking %d devices for NetBrain observations...", devices.count())

        for device in devices:
            cf = device._custom_field_data or {}
            obs = cf.get(OBS_CF_KEY)
            if not isinstance(obs, dict):
                continue
            nb_obs = obs.get(OBS_NAMESPACE)
            if not nb_obs or not isinstance(nb_obs, dict):
                continue

            remote = nb_obs.get("data", {}).get("remote", {})
            if not remote:
                continue

            stats["devices_processed"] += 1
            changed = False

            try:
                # --- Management IP ---
                if rollup_ips:
                    mgmt_ip = (remote.get("mgmtIP") or "").strip()
                    if mgmt_ip:
                        if dry_run:
                            self.logger.info("  [DRY-RUN] %s: would assign mgmt IP %s",
                                             device.name, mgmt_ip)
                        else:
                            ip_changed = self._rollup_mgmt_ip(device, mgmt_ip, active, stats)
                            if ip_changed:
                                changed = True

                # --- Location ---
                if rollup_locations:
                    site_path = (remote.get("site") or "").strip()
                    if site_path:
                        if dry_run:
                            self.logger.info("  [DRY-RUN] %s: would set location from '%s'",
                                             device.name, site_path)
                        else:
                            loc_changed = self._rollup_location(device, site_path, active, stats)
                            if loc_changed:
                                changed = True

                # --- Tags ---
                if rollup_tags:
                    tags = remote.get("assignTags", [])
                    if isinstance(tags, list) and tags:
                        if dry_run:
                            self.logger.info("  [DRY-RUN] %s: would add tags %s",
                                             device.name, tags)
                        else:
                            for tag_name in tags:
                                tag, _ = Tag.objects.get_or_create(name=tag_name)
                                if tag not in device.tags.all():
                                    device.tags.add(tag)
                                    stats["tags_added"] += 1

                if changed:
                    device.validated_save()

            except Exception as exc:
                self.logger.error("  Error on %s: %s", device.name, exc)
                stats["errors"] += 1

        self.logger.info("=" * 60)
        self.logger.info("ROLLUP COMPLETE")
        for k, v in stats.items():
            self.logger.info("  %s: %d", k, v)
        self.logger.info("=" * 60)
        return json.dumps(stats)

    # ------------------------------------------------------------------
    # Rollup helpers
    # ------------------------------------------------------------------

    def _rollup_mgmt_ip(self, device, ip_str, active_status, stats):
        """Create mgmt IP, assign to mgmt interface, set as primary_ip4."""
        cidr = _normalize_ip(ip_str)
        if not cidr:
            return False

        # Ensure covering prefix
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

        ip_obj, created = IPAddress.objects.get_or_create(
            address=cidr, defaults={"status": active_status})
        if created:
            stats["ips_created"] += 1

        # Get or create mgmt interface
        mgmt_name = "mgmt0"
        mgmt_intf, _ = Interface.objects.get_or_create(
            device=device, name=mgmt_name,
            defaults={"type": "virtual", "status": active_status})

        IPAddressToInterface.objects.get_or_create(
            ip_address=ip_obj, interface=mgmt_intf)

        changed = False
        if device.primary_ip4 != ip_obj:
            device.primary_ip4 = ip_obj
            stats["ips_assigned"] += 1
            changed = True

        return changed

    def _rollup_location(self, device, site_path, active_status, stats):
        """Create location hierarchy from site path and reassign device."""
        segments = _parse_site_path(site_path)
        if not segments:
            return False
        if segments[0] == "My Network":
            segments = segments[1:]
        if not segments:
            return False

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

        changed = False
        if device.location != location:
            device.location = location
            stats["locations_reassigned"] += 1
            changed = True

        return changed


register_jobs(NetBrainDeviceRollup)
