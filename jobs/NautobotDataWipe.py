"""Nautobot Data Wipe job.

Deletes existing Nautobot objects for a clean slate before importing
new data.  Respects foreign-key ordering and provides safety toggles
(confirm keyword, dry-run mode, keep-locations, keep-manufacturers).
"""

from __future__ import annotations

from nautobot.apps.jobs import BooleanVar, Job, StringVar, register_jobs
from nautobot.circuits.models import Circuit, CircuitTermination, Provider
from nautobot.dcim.models import (
    Cable,
    Device,
    DeviceType,
    Interface,
    Location,
    LocationType,
    Manufacturer,
    Platform,
)
from nautobot.extras.models import Role, Tag
from nautobot.ipam.models import (
    IPAddress,
    IPAddressToInterface,
    Prefix,
    VLAN,
    VRF,
)
from nautobot.tenancy.models import Tenant


# Names / prefixes that indicate system-managed objects we should never touch.
PROTECTED_PREFIXES = ("system",)


def _is_protected(name: str) -> bool:
    """Return True if *name* looks like a system-managed object."""
    lower = (name or "").strip().lower()
    return any(lower.startswith(p) for p in PROTECTED_PREFIXES)


class NautobotDataWipe(Job):
    """Delete Nautobot objects for a clean-slate import."""

    class Meta:
        name = "Nautobot: Data Wipe"
        description = (
            "Wipes existing data from the Nautobot instance for a clean slate "
            "before importing new data.  Deletes objects in FK-safe order.  "
            "Requires typing WIPE to proceed; supports dry-run mode."
        )
        commit_default = False
        has_sensitive_variables = False

    confirm = StringVar(
        label="Confirmation keyword",
        description='Type "WIPE" (all caps) to confirm you want to proceed.',
        default="",
        required=True,
    )
    dry_run = BooleanVar(
        label="Dry Run (no DB writes)",
        description="When ON, logs what would be deleted but writes nothing.",
        default=True,
        required=False,
    )
    keep_locations = BooleanVar(
        label="Keep Locations / LocationTypes",
        description="When ON, Location and LocationType objects are NOT deleted.",
        default=False,
        required=False,
    )
    keep_manufacturers = BooleanVar(
        label="Keep Manufacturers / DeviceTypes",
        description="When ON, Manufacturer and DeviceType objects are NOT deleted.",
        default=False,
        required=False,
    )

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _delete_queryset(self, qs, label, dry_run, *, skip_protected=False):
        """Log and optionally delete every object in *qs*.

        Returns the number of objects that were (or would be) deleted.
        """
        if skip_protected:
            # Filter out protected objects by name where the model has a 'name' field.
            names_to_skip = []
            filtered_pks = []
            for obj in qs.iterator():
                obj_name = getattr(obj, "name", "") or ""
                if _is_protected(obj_name):
                    names_to_skip.append(obj_name)
                else:
                    filtered_pks.append(obj.pk)
            if names_to_skip:
                self.logger.info(
                    "  Skipping %d protected %s object(s): %s",
                    len(names_to_skip),
                    label,
                    ", ".join(sorted(set(names_to_skip))),
                )
            qs = qs.filter(pk__in=filtered_pks)

        count = qs.count()
        if count == 0:
            self.logger.info("  %s: 0 objects — nothing to do.", label)
            return 0

        if dry_run:
            self.logger.info("  [DRY RUN] %s: would delete %d object(s).", label, count)
            return count

        self.logger.info("  %s: deleting %d object(s) ...", label, count)
        for obj in qs.iterator():
            try:
                if hasattr(obj, "validated_delete"):
                    obj.validated_delete()
                else:
                    obj.delete()
            except Exception as exc:
                self.logger.warning(
                    "    Failed to delete %s pk=%s: %s", label, obj.pk, exc
                )
        self.logger.info("  %s: done.", label)
        return count

    # ------------------------------------------------------------------
    # main
    # ------------------------------------------------------------------

    def run(self, confirm="", dry_run=True, keep_locations=False, keep_manufacturers=False, **kwargs):
        # --- Safety gate ---
        if confirm != "WIPE":
            self.logger.error(
                'Aborted — you must type "WIPE" in the confirmation field. '
                "Received: %r",
                confirm,
            )
            return "ABORTED"

        self.logger.info("=" * 60)
        self.logger.info("Nautobot Data Wipe")
        self.logger.info("  dry_run:            %s", dry_run)
        self.logger.info("  keep_locations:     %s", keep_locations)
        self.logger.info("  keep_manufacturers: %s", keep_manufacturers)
        self.logger.info("=" * 60)

        total = 0

        # 1. IPAddressToInterface assignments
        self.logger.info("--- IPAddressToInterface ---")
        total += self._delete_queryset(
            IPAddressToInterface.objects.all(),
            "IPAddressToInterface",
            dry_run,
        )

        # 2. IP Addresses
        self.logger.info("--- IPAddress ---")
        total += self._delete_queryset(
            IPAddress.objects.all(),
            "IPAddress",
            dry_run,
            skip_protected=True,
        )

        # 3. Interfaces
        self.logger.info("--- Interface ---")
        total += self._delete_queryset(
            Interface.objects.all(),
            "Interface",
            dry_run,
            skip_protected=True,
        )

        # 4. Devices
        self.logger.info("--- Device ---")
        total += self._delete_queryset(
            Device.objects.all(),
            "Device",
            dry_run,
            skip_protected=True,
        )

        # 5. Cables
        self.logger.info("--- Cable ---")
        total += self._delete_queryset(
            Cable.objects.all(),
            "Cable",
            dry_run,
        )

        # 6. CircuitTerminations
        self.logger.info("--- CircuitTermination ---")
        total += self._delete_queryset(
            CircuitTermination.objects.all(),
            "CircuitTermination",
            dry_run,
        )

        # 7. Circuits
        self.logger.info("--- Circuit ---")
        total += self._delete_queryset(
            Circuit.objects.all(),
            "Circuit",
            dry_run,
            skip_protected=True,
        )

        # 8. Prefixes (skip system-managed)
        self.logger.info("--- Prefix ---")
        total += self._delete_queryset(
            Prefix.objects.all(),
            "Prefix",
            dry_run,
            skip_protected=True,
        )

        # 9. VLANs
        self.logger.info("--- VLAN ---")
        total += self._delete_queryset(
            VLAN.objects.all(),
            "VLAN",
            dry_run,
            skip_protected=True,
        )

        # 10. VRFs
        self.logger.info("--- VRF ---")
        total += self._delete_queryset(
            VRF.objects.all(),
            "VRF",
            dry_run,
            skip_protected=True,
        )

        # 11. DeviceTypes / Manufacturers
        if keep_manufacturers:
            self.logger.info("--- DeviceType / Manufacturer: SKIPPED (keep_manufacturers=True) ---")
        else:
            self.logger.info("--- DeviceType ---")
            total += self._delete_queryset(
                DeviceType.objects.all(),
                "DeviceType",
                dry_run,
                skip_protected=True,
            )

            self.logger.info("--- Manufacturer ---")
            total += self._delete_queryset(
                Manufacturer.objects.all(),
                "Manufacturer",
                dry_run,
                skip_protected=True,
            )

        # 12. Platforms
        self.logger.info("--- Platform ---")
        total += self._delete_queryset(
            Platform.objects.all(),
            "Platform",
            dry_run,
            skip_protected=True,
        )

        # 13. Locations (leaf-first then parents) / LocationTypes
        if keep_locations:
            self.logger.info("--- Location / LocationType: SKIPPED (keep_locations=True) ---")
        else:
            self.logger.info("--- Location (leaf-first) ---")
            # Delete in waves: children before parents.  Locations with no
            # children (leaf nodes) are deleted first, then we repeat until
            # nothing remains.
            wave = 1
            max_waves = 10  # prevent infinite loop on undeletable locations
            prev_count = None
            while wave <= max_waves:
                # Leaf locations = those with no children pointing at them.
                # Exclude locations referenced by Controllers (protected FK)
                try:
                    from nautobot.dcim.models import Controller
                    controller_loc_ids = set(
                        Controller.objects.values_list("location_id", flat=True)
                    )
                except (ImportError, Exception):
                    controller_loc_ids = set()

                leaves = Location.objects.exclude(
                    pk__in=Location.objects.filter(
                        parent__isnull=False,
                    ).values_list("parent_id", flat=True),
                ).exclude(pk__in=controller_loc_ids)

                count = leaves.count()
                if count == 0:
                    break
                if count == prev_count:
                    self.logger.info("  Location wave %d: %d undeletable locations remain, stopping", wave, count)
                    break
                prev_count = count

                self.logger.info("  Location wave %d:", wave)
                deleted = self._delete_queryset(
                    leaves,
                    f"Location (wave {wave})",
                    dry_run,
                    skip_protected=True,
                )
                total += deleted
                wave += 1
                if dry_run:
                    break

            self.logger.info("--- LocationType ---")
            total += self._delete_queryset(
                LocationType.objects.all(),
                "LocationType",
                dry_run,
                skip_protected=True,
            )

        # 14. Providers
        self.logger.info("--- Provider ---")
        total += self._delete_queryset(
            Provider.objects.all(),
            "Provider",
            dry_run,
            skip_protected=True,
        )

        # 15. Tenants
        self.logger.info("--- Tenant ---")
        total += self._delete_queryset(
            Tenant.objects.all(),
            "Tenant",
            dry_run,
            skip_protected=True,
        )

        # 16. Tags (non-system only)
        self.logger.info("--- Tag (non-system) ---")
        total += self._delete_queryset(
            Tag.objects.all(),
            "Tag",
            dry_run,
            skip_protected=True,
        )

        # 17. Roles (device-related only)
        self.logger.info("--- Role (device-related) ---")
        device_roles = Role.objects.filter(
            content_types__model="device",
        )
        total += self._delete_queryset(
            device_roles,
            "Role (device)",
            dry_run,
            skip_protected=True,
        )

        # --- Summary ---
        self.logger.info("=" * 60)
        action = "would be deleted" if dry_run else "deleted"
        self.logger.info(
            "Finished — %d total object(s) %s.", total, action,
        )
        self.logger.info("=" * 60)
        return f"{'DRY RUN — ' if dry_run else ''}{total} objects {action}."


register_jobs(NautobotDataWipe)
