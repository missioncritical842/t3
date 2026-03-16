"""Nautobot REST API client.

Async client for Nautobot 3.x REST API with token authentication.
Wraps the most commonly used DCIM, IPAM, Circuits, and Tenancy endpoints.
Also supports GraphQL queries.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class NautobotClient:
    """Async client for the Nautobot REST API."""

    def __init__(
        self,
        url: str | None = None,
        token: str | None = None,
    ) -> None:
        self.url = (url or os.getenv("NAUTOBOT_URL", "")).rstrip("/")
        self.token = token or os.getenv("NAUTOBOT_TOKEN", "")
        self._http = httpx.AsyncClient(
            base_url=self.url,
            headers={
                "Authorization": f"Token {self.token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=30.0,
        )

    # ── helpers ────────────────────────────────────────────────────────

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        resp = await self._http.get(f"/api/{path}", params=params)
        resp.raise_for_status()
        return resp.json()

    async def _post(self, path: str, json: Any = None) -> dict[str, Any]:
        resp = await self._http.post(f"/api/{path}", json=json)
        resp.raise_for_status()
        return resp.json()

    async def _patch(self, path: str, json: Any = None) -> dict[str, Any]:
        resp = await self._http.patch(f"/api/{path}", json=json)
        resp.raise_for_status()
        return resp.json()

    async def _delete(self, path: str) -> int:
        resp = await self._http.delete(f"/api/{path}")
        resp.raise_for_status()
        return resp.status_code

    async def _get_list(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """GET a paginated list endpoint."""
        p = dict(params or {})
        p["limit"] = limit
        p["offset"] = offset
        return await self._get(path, params=p)

    # ── status ─────────────────────────────────────────────────────────

    async def get_status(self) -> dict[str, Any]:
        return await self._get("status/")

    # ── DCIM ───────────────────────────────────────────────────────────

    async def get_devices(self, limit: int = 50, offset: int = 0, **filters: Any) -> dict[str, Any]:
        return await self._get_list("dcim/devices/", params=filters, limit=limit, offset=offset)

    async def get_device(self, device_id: str) -> dict[str, Any]:
        return await self._get(f"dcim/devices/{device_id}/")

    async def get_interfaces(self, limit: int = 50, offset: int = 0, **filters: Any) -> dict[str, Any]:
        return await self._get_list("dcim/interfaces/", params=filters, limit=limit, offset=offset)

    async def get_interface(self, interface_id: str) -> dict[str, Any]:
        return await self._get(f"dcim/interfaces/{interface_id}/")

    async def get_device_types(self, limit: int = 50, offset: int = 0, **filters: Any) -> dict[str, Any]:
        return await self._get_list("dcim/device-types/", params=filters, limit=limit, offset=offset)

    async def get_locations(self, limit: int = 50, offset: int = 0, **filters: Any) -> dict[str, Any]:
        return await self._get_list("dcim/locations/", params=filters, limit=limit, offset=offset)

    async def get_location(self, location_id: str) -> dict[str, Any]:
        return await self._get(f"dcim/locations/{location_id}/")

    async def get_racks(self, limit: int = 50, offset: int = 0, **filters: Any) -> dict[str, Any]:
        return await self._get_list("dcim/racks/", params=filters, limit=limit, offset=offset)

    async def get_cables(self, limit: int = 50, offset: int = 0, **filters: Any) -> dict[str, Any]:
        return await self._get_list("dcim/cables/", params=filters, limit=limit, offset=offset)

    async def get_platforms(self, limit: int = 50, offset: int = 0, **filters: Any) -> dict[str, Any]:
        return await self._get_list("dcim/platforms/", params=filters, limit=limit, offset=offset)

    async def get_manufacturers(self, limit: int = 50, offset: int = 0, **filters: Any) -> dict[str, Any]:
        return await self._get_list("dcim/manufacturers/", params=filters, limit=limit, offset=offset)

    async def get_controllers(self, limit: int = 50, offset: int = 0, **filters: Any) -> dict[str, Any]:
        return await self._get_list("dcim/controllers/", params=filters, limit=limit, offset=offset)

    # ── DCIM write ─────────────────────────────────────────────────────

    async def create_device(self, data: dict[str, Any]) -> dict[str, Any]:
        return await self._post("dcim/devices/", json=data)

    async def update_device(self, device_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return await self._patch(f"dcim/devices/{device_id}/", json=data)

    async def delete_device(self, device_id: str) -> int:
        return await self._delete(f"dcim/devices/{device_id}/")

    async def create_interface(self, data: dict[str, Any]) -> dict[str, Any]:
        return await self._post("dcim/interfaces/", json=data)

    async def update_interface(self, interface_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return await self._patch(f"dcim/interfaces/{interface_id}/", json=data)

    async def delete_interface(self, interface_id: str) -> int:
        return await self._delete(f"dcim/interfaces/{interface_id}/")

    async def create_location(self, data: dict[str, Any]) -> dict[str, Any]:
        return await self._post("dcim/locations/", json=data)

    async def update_location(self, location_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return await self._patch(f"dcim/locations/{location_id}/", json=data)

    async def delete_location(self, location_id: str) -> int:
        return await self._delete(f"dcim/locations/{location_id}/")

    async def create_cable(self, data: dict[str, Any]) -> dict[str, Any]:
        return await self._post("dcim/cables/", json=data)

    async def delete_cable(self, cable_id: str) -> int:
        return await self._delete(f"dcim/cables/{cable_id}/")

    async def create_rack(self, data: dict[str, Any]) -> dict[str, Any]:
        return await self._post("dcim/racks/", json=data)

    async def update_rack(self, rack_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return await self._patch(f"dcim/racks/{rack_id}/", json=data)

    async def delete_rack(self, rack_id: str) -> int:
        return await self._delete(f"dcim/racks/{rack_id}/")

    # ── IPAM ───────────────────────────────────────────────────────────

    async def get_ip_addresses(self, limit: int = 50, offset: int = 0, **filters: Any) -> dict[str, Any]:
        return await self._get_list("ipam/ip-addresses/", params=filters, limit=limit, offset=offset)

    async def get_ip_address(self, ip_id: str) -> dict[str, Any]:
        return await self._get(f"ipam/ip-addresses/{ip_id}/")

    async def get_prefixes(self, limit: int = 50, offset: int = 0, **filters: Any) -> dict[str, Any]:
        return await self._get_list("ipam/prefixes/", params=filters, limit=limit, offset=offset)

    async def get_prefix(self, prefix_id: str) -> dict[str, Any]:
        return await self._get(f"ipam/prefixes/{prefix_id}/")

    async def get_vlans(self, limit: int = 50, offset: int = 0, **filters: Any) -> dict[str, Any]:
        return await self._get_list("ipam/vlans/", params=filters, limit=limit, offset=offset)

    async def get_vrfs(self, limit: int = 50, offset: int = 0, **filters: Any) -> dict[str, Any]:
        return await self._get_list("ipam/vrfs/", params=filters, limit=limit, offset=offset)

    async def get_namespaces(self, limit: int = 50, offset: int = 0, **filters: Any) -> dict[str, Any]:
        return await self._get_list("ipam/namespaces/", params=filters, limit=limit, offset=offset)

    # ── IPAM write ─────────────────────────────────────────────────────

    async def create_ip_address(self, data: dict[str, Any]) -> dict[str, Any]:
        return await self._post("ipam/ip-addresses/", json=data)

    async def update_ip_address(self, ip_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return await self._patch(f"ipam/ip-addresses/{ip_id}/", json=data)

    async def delete_ip_address(self, ip_id: str) -> int:
        return await self._delete(f"ipam/ip-addresses/{ip_id}/")

    async def create_prefix(self, data: dict[str, Any]) -> dict[str, Any]:
        return await self._post("ipam/prefixes/", json=data)

    async def update_prefix(self, prefix_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return await self._patch(f"ipam/prefixes/{prefix_id}/", json=data)

    async def delete_prefix(self, prefix_id: str) -> int:
        return await self._delete(f"ipam/prefixes/{prefix_id}/")

    async def create_vlan(self, data: dict[str, Any]) -> dict[str, Any]:
        return await self._post("ipam/vlans/", json=data)

    async def update_vlan(self, vlan_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return await self._patch(f"ipam/vlans/{vlan_id}/", json=data)

    async def delete_vlan(self, vlan_id: str) -> int:
        return await self._delete(f"ipam/vlans/{vlan_id}/")

    async def create_vrf(self, data: dict[str, Any]) -> dict[str, Any]:
        return await self._post("ipam/vrfs/", json=data)

    async def update_vrf(self, vrf_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return await self._patch(f"ipam/vrfs/{vrf_id}/", json=data)

    async def delete_vrf(self, vrf_id: str) -> int:
        return await self._delete(f"ipam/vrfs/{vrf_id}/")

    # ── Circuits ───────────────────────────────────────────────────────

    async def get_circuits(self, limit: int = 50, offset: int = 0, **filters: Any) -> dict[str, Any]:
        return await self._get_list("circuits/circuits/", params=filters, limit=limit, offset=offset)

    async def get_providers(self, limit: int = 50, offset: int = 0, **filters: Any) -> dict[str, Any]:
        return await self._get_list("circuits/providers/", params=filters, limit=limit, offset=offset)

    # ── Circuits write ─────────────────────────────────────────────────

    async def create_circuit(self, data: dict[str, Any]) -> dict[str, Any]:
        return await self._post("circuits/circuits/", json=data)

    async def update_circuit(self, circuit_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return await self._patch(f"circuits/circuits/{circuit_id}/", json=data)

    async def delete_circuit(self, circuit_id: str) -> int:
        return await self._delete(f"circuits/circuits/{circuit_id}/")

    async def create_provider(self, data: dict[str, Any]) -> dict[str, Any]:
        return await self._post("circuits/providers/", json=data)

    async def update_provider(self, provider_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return await self._patch(f"circuits/providers/{provider_id}/", json=data)

    async def delete_provider(self, provider_id: str) -> int:
        return await self._delete(f"circuits/providers/{provider_id}/")

    # ── Tenancy ────────────────────────────────────────────────────────

    async def get_tenants(self, limit: int = 50, offset: int = 0, **filters: Any) -> dict[str, Any]:
        return await self._get_list("tenancy/tenants/", params=filters, limit=limit, offset=offset)

    # ── Virtualization ─────────────────────────────────────────────────

    async def get_virtual_machines(self, limit: int = 50, offset: int = 0, **filters: Any) -> dict[str, Any]:
        return await self._get_list("virtualization/virtual-machines/", params=filters, limit=limit, offset=offset)

    async def get_clusters(self, limit: int = 50, offset: int = 0, **filters: Any) -> dict[str, Any]:
        return await self._get_list("virtualization/clusters/", params=filters, limit=limit, offset=offset)

    # ── Tenancy write ──────────────────────────────────────────────────

    async def create_tenant(self, data: dict[str, Any]) -> dict[str, Any]:
        return await self._post("tenancy/tenants/", json=data)

    async def update_tenant(self, tenant_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return await self._patch(f"tenancy/tenants/{tenant_id}/", json=data)

    async def delete_tenant(self, tenant_id: str) -> int:
        return await self._delete(f"tenancy/tenants/{tenant_id}/")

    # ── Virtualization write ───────────────────────────────────────────

    async def create_virtual_machine(self, data: dict[str, Any]) -> dict[str, Any]:
        return await self._post("virtualization/virtual-machines/", json=data)

    async def update_virtual_machine(self, vm_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return await self._patch(f"virtualization/virtual-machines/{vm_id}/", json=data)

    async def delete_virtual_machine(self, vm_id: str) -> int:
        return await self._delete(f"virtualization/virtual-machines/{vm_id}/")

    # ── Jobs ───────────────────────────────────────────────────────────

    async def get_jobs(self, limit: int = 50, offset: int = 0, **filters: Any) -> dict[str, Any]:
        return await self._get_list("extras/jobs/", params=filters, limit=limit, offset=offset)

    async def get_job(self, job_id: str) -> dict[str, Any]:
        return await self._get(f"extras/jobs/{job_id}/")

    async def run_job(self, job_id: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._post(f"extras/jobs/{job_id}/run/", json=data or {})

    async def get_job_results(self, limit: int = 50, offset: int = 0, **filters: Any) -> dict[str, Any]:
        return await self._get_list("extras/job-results/", params=filters, limit=limit, offset=offset)

    async def get_job_result(self, result_id: str) -> dict[str, Any]:
        return await self._get(f"extras/job-results/{result_id}/")

    # ── GraphQL ────────────────────────────────────────────────────────

    async def graphql(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"query": query}
        if variables:
            body["variables"] = variables
        return await self._post("graphql/", json=body)

    # ── lifecycle ──────────────────────────────────────────────────────

    async def close(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "NautobotClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()
