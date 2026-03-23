"""NetBrain: Import Single Device.

Fast import of one device by hostname. No inventory scan — just fetches
attributes for the specified device and creates it in Nautobot.
Perfect for demos and testing.
"""

from __future__ import annotations

import json
import os
import time

import requests
import urllib3

from nautobot.apps.jobs import Job, StringVar, register_jobs
from nautobot.dcim.models import Device, DeviceType, Manufacturer, Platform
from nautobot.extras.models import Role, Status

from .netbrain_utils import (
    _fake_hostname,
    _fake_serial,
    _sanitize_device_attrs,
    _sanitize_json_tree,
    _utc_now_iso,
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

V1 = "/ServicesAPI/API/V1"
OBS_NAMESPACE = "netbrain"
OBS_CF_KEY = "observations"

VENDOR_MAP = {
    "arista networks": "Arista",
    "cisco systems": "Cisco",
    "f5, inc": "F5", "f5, inc.": "F5", "f5 networks": "F5",
    "palo alto networks": "Palo Alto Networks",
}


class NetBrainSingleImport(Job):
    """Import a single device from NetBrain by hostname. Fast — no inventory scan."""

    class Meta:
        name = "NetBrain: Single Device Import"
        description = "Import one device by hostname. Takes seconds, not minutes."
        commit_default = False
        has_sensitive_variables = True

    hostname = StringVar(
        label="NetBrain Hostname",
        description="Exact device hostname from NetBrain (e.g. from a previous import log)",
        default="",
    )
    host = StringVar(default="https://10.134.98.133", label="NetBrain Host")
    username = StringVar(default="nautobotapi", label="Username")
    password = StringVar(default="", required=False, label="Password",
                         description="Leave blank to use stored credentials")
    client_id = StringVar(default="", required=False, label="Client ID",
                          description="Leave blank to use stored credentials")
    client_secret = StringVar(default="", required=False, label="Client Secret",
                              description="Leave blank to use stored credentials")

    def run(self, hostname="", host="", username="", password="",
            client_id="", client_secret="", **kwargs):

        hostname = (hostname or "").strip()
        if not hostname:
            self.logger.error("No hostname provided")
            return "FAILED: no hostname"

        host = (host or "").rstrip("/")
        stored = self._load_creds()
        username = (username or "").strip() or os.environ.get("NETBRAIN_USERNAME", "") or stored.get("username", "nautobotapi")
        password = (password or "").strip() or os.environ.get("NETBRAIN_PASSWORD", "") or stored.get("password", "")
        client_id = (client_id or "").strip() or os.environ.get("NETBRAIN_CLIENT_ID", "") or stored.get("client_id", "")
        client_secret = (client_secret or "").strip() or os.environ.get("NETBRAIN_CLIENT_SECRET", "") or stored.get("client_secret", "")

        self.logger.info("Single device import: %s", hostname)

        # Login
        token = self._login(host, username, password, client_id, client_secret)
        if not token:
            return "FAILED: login"
        headers = {"Token": token, "Content-Type": "application/json"}

        try:
            self._set_domain(host, headers)

            # Fetch attributes — one API call
            r = requests.get(f"{host}{V1}/CMDB/Devices/Attributes",
                             params={"hostname": hostname},
                             headers=headers, verify=False, timeout=30)
            if r.status_code != 200:
                self.logger.error("Failed to fetch: HTTP %s", r.status_code)
                return "FAILED: fetch"

            raw_attrs = r.json().get("attributes", {})
            if not raw_attrs:
                self.logger.error("No attributes returned for '%s'", hostname)
                return "FAILED: no attrs"

            sub_type = raw_attrs.get("subTypeName", "Unknown")
            self.logger.info("Found: %s (%s)", hostname, sub_type)

            # Build observation
            obs_payload = {
                "schema_version": 1,
                "meta": {"fetched_at": _utc_now_iso(), "source": "netbrain_single_import", "nb_hostname": hostname},
                "data": {"remote": raw_attrs},
            }
            obs_payload = _sanitize_json_tree(obs_payload, skip_keys=frozenset({
                "schema_version", "source", "vendor", "model", "subTypeName", "driverName", "ver", "os",
            }))

            # Fake identity
            serial = (raw_attrs.get("sn") or "").strip()
            name = (raw_attrs.get("name") or "").strip()
            display_name = _fake_hostname(name) if name else "device-single"
            display_serial = _fake_serial(serial) if serial else ""
            vendor = VENDOR_MAP.get((raw_attrs.get("vendor") or "").strip().lower(), (raw_attrs.get("vendor") or "Unknown").strip()) or "Unknown"
            model = (raw_attrs.get("model") or "Unknown").strip() or "Unknown"
            driver = (raw_attrs.get("driverName") or "").strip()

            self.logger.info("Creating: %s (%s) vendor=%s model=%s", display_name, sub_type, vendor, model)

            # Create Nautobot objects
            active = Status.objects.get(name="Active")
            mfr, _ = Manufacturer.objects.get_or_create(name=vendor)
            dtype, _ = DeviceType.objects.get_or_create(model=model, manufacturer=mfr)
            role, rc = Role.objects.get_or_create(name=sub_type)
            if rc:
                from django.contrib.contenttypes.models import ContentType
                role.content_types.add(ContentType.objects.get_for_model(Device))
            platform = None
            if driver:
                platform, _ = Platform.objects.get_or_create(name=driver)

            location = self._get_fallback_location(active)

            device = Device(
                name=display_name,
                serial=display_serial,
                device_type=dtype,
                platform=platform,
                role=role,
                status=active,
                location=location,
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

            self.logger.info("CREATED: %s", display_name)
            return "SUCCESS"

        finally:
            requests.delete(f"{host}{V1}/Session", headers=headers, verify=False, timeout=10)
            self.logger.info("Logged out.")

    def _load_creds(self):
        try:
            from nautobot.extras.models import ConfigContext
            ctx = ConfigContext.objects.filter(name="NetBrain Credentials").first()
            if ctx and ctx.data:
                return ctx.data
        except Exception:
            pass
        return {}

    def _login(self, host, username, password, client_id, client_secret):
        body = {"username": username, "password": password}
        if client_id:
            body["authentication_id"] = client_id
        if client_secret:
            body["client_secret"] = client_secret
        try:
            r = requests.post(f"{host}{V1}/Session", json=body,
                              headers={"Content-Type": "application/json"},
                              verify=False, timeout=60)
            if r.status_code == 200:
                token = r.json().get("token", "")
                if token:
                    self.logger.info("Login OK")
                    return token
        except Exception as exc:
            self.logger.error("Login: %s", exc)
        return None

    def _set_domain(self, host, headers):
        try:
            r = requests.get(f"{host}{V1}/CMDB/Tenants", headers=headers, verify=False, timeout=30)
            if r.status_code != 200:
                return
            tid = r.json().get("tenants", [{}])[0].get("tenantId", "")
            r2 = requests.get(f"{host}{V1}/CMDB/Domains", params={"tenantId": tid},
                              headers=headers, verify=False, timeout=30)
            if r2.status_code != 200:
                return
            did = r2.json().get("domains", [{}])[0].get("domainId", "")
            requests.put(f"{host}{V1}/Session/CurrentDomain",
                         json={"tenantId": tid, "domainId": did},
                         headers=headers, verify=False, timeout=30)
        except Exception:
            pass

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


register_jobs(NetBrainSingleImport)
