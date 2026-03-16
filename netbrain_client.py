"""NetBrain REST API client.

Handles authentication (login/logout), session management, and
wraps the most commonly used NetBrain REST API endpoints.

Reference: https://github.com/NetBrainAPI/NetBrain-REST-API-R11.1b
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

API_BASE = "/ServicesAPI/API/V1"


class NetBrainClient:
    """Async client for the NetBrain REST API."""

    def __init__(
        self,
        host: str | None = None,
        username: str | None = None,
        password: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> None:
        self.host = (host or os.getenv("NETBRAIN_HOST", "")).rstrip("/")
        self.username = username or os.getenv("NETBRAIN_USERNAME", "")
        self.password = password or os.getenv("NETBRAIN_PASSWORD", "")
        self.client_id = client_id or os.getenv("NETBRAIN_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("NETBRAIN_CLIENT_SECRET", "")
        self.token: str | None = None
        self._http = httpx.AsyncClient(base_url=self.host, verify=False, timeout=30.0)

    # ── helpers ────────────────────────────────────────────────────────

    def _url(self, path: str) -> str:
        return f"{API_BASE}{path}"

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.token:
            h["Token"] = self.token
        return h

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        resp = await self._http.request(
            method, self._url(path), headers=self._headers(), **kwargs
        )
        resp.raise_for_status()
        return resp.json()

    # ── auth ───────────────────────────────────────────────────────────

    async def login(self) -> str:
        """Authenticate and obtain a session token."""
        body = {
            "username": self.username,
            "password": self.password,
            "authentication_id": self.client_id,
            "client_secret": self.client_secret,
        }
        data = await self._request("POST", "/Session", json=body)
        self.token = data.get("token", "")
        logger.info("Logged in to NetBrain as %s", self.username)
        return self.token

    async def logout(self) -> dict[str, Any]:
        """End the current session."""
        data = await self._request("DELETE", "/Session")
        self.token = None
        logger.info("Logged out of NetBrain")
        return data

    async def ensure_session(self) -> None:
        """Login if we don't already have a token."""
        if not self.token:
            await self.login()

    # ── domain ─────────────────────────────────────────────────────────

    async def get_accessible_tenants(self) -> list[dict[str, Any]]:
        await self.ensure_session()
        data = await self._request("GET", "/CMDB/Tenants")
        return data.get("tenants", data.get("data", []))

    async def get_accessible_domains(self, tenant_id: str) -> list[dict[str, Any]]:
        await self.ensure_session()
        data = await self._request(
            "GET", "/CMDB/Domains", params={"tenantId": tenant_id}
        )
        return data.get("domains", data.get("data", []))

    async def set_current_domain(
        self, tenant_id: str, domain_id: str
    ) -> dict[str, Any]:
        await self.ensure_session()
        body = {"tenantId": tenant_id, "domainId": domain_id}
        return await self._request("PUT", "/Session/CurrentDomain", json=body)

    # ── devices ────────────────────────────────────────────────────────

    async def get_devices(
        self,
        hostname: str | None = None,
        ip: str | None = None,
        site_path: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Search / list devices."""
        await self.ensure_session()
        params: dict[str, Any] = {"skip": skip, "limit": limit}
        if hostname:
            params["hostname"] = hostname
        if ip:
            params["ip"] = ip
        if site_path:
            params["sitePath"] = site_path
        data = await self._request("GET", "/CMDB/Devices", params=params)
        return data.get("devices", data.get("data", []))

    async def get_device_attributes(
        self, hostname: str
    ) -> dict[str, Any]:
        """Get attributes for a single device."""
        await self.ensure_session()
        data = await self._request(
            "GET", "/CMDB/Devices/Attributes", params={"hostname": hostname}
        )
        return data.get("attributes", data)

    async def get_device_config(self, hostname: str) -> dict[str, Any]:
        """Get the running/startup config of a device."""
        await self.ensure_session()
        data = await self._request(
            "GET", "/CMDB/DataEngine/DeviceData/Configuration",
            params={"hostname": hostname},
        )
        return data

    # ── interfaces ─────────────────────────────────────────────────────

    async def get_interfaces(self, hostname: str) -> list[dict[str, Any]]:
        """List all interfaces of a device."""
        await self.ensure_session()
        data = await self._request(
            "GET", "/CMDB/Interfaces", params={"hostname": hostname}
        )
        return data.get("interfaces", data.get("data", []))

    async def get_interface_attributes(
        self, hostname: str, interface_name: str
    ) -> dict[str, Any]:
        await self.ensure_session()
        data = await self._request(
            "GET",
            "/CMDB/Interfaces/Attributes",
            params={"hostname": hostname, "interfaceName": interface_name},
        )
        return data.get("attributes", data)

    # ── topology / path ────────────────────────────────────────────────

    async def calculate_path(
        self, source_ip: str, destination_ip: str, protocol: int = 4
    ) -> dict[str, Any]:
        """Trigger a path calculation between two IPs."""
        await self.ensure_session()
        body = {
            "sourceIP": source_ip,
            "destinationIP": destination_ip,
            "protocol": protocol,
        }
        return await self._request("POST", "/CMDB/Path", json=body)

    async def get_path_result(self, task_id: str) -> dict[str, Any]:
        """Retrieve the result of a path calculation."""
        await self.ensure_session()
        return await self._request(
            "GET", "/CMDB/Path/Result", params={"taskID": task_id}
        )

    # ── sites ──────────────────────────────────────────────────────────

    async def get_sites(self) -> list[dict[str, Any]]:
        await self.ensure_session()
        data = await self._request("GET", "/CMDB/Sites")
        return data.get("sites", data.get("data", []))

    async def get_site_devices(self, site_path: str) -> list[dict[str, Any]]:
        await self.ensure_session()
        data = await self._request(
            "GET", "/CMDB/Sites/Devices", params={"sitePath": site_path}
        )
        return data.get("devices", data.get("data", []))

    # ── misc ───────────────────────────────────────────────────────────

    async def get_product_version(self) -> dict[str, Any]:
        data = await self._request("GET", "/System/ProductVersion")
        return data

    async def search(self, keyword: str) -> list[dict[str, Any]]:
        """Global search across all object types."""
        await self.ensure_session()
        data = await self._request(
            "GET", "/CMDB/Search", params={"keyword": keyword}
        )
        return data.get("results", data.get("data", []))

    # ── context manager ────────────────────────────────────────────────

    async def close(self) -> None:
        if self.token:
            try:
                await self.logout()
            except Exception:
                pass
        await self._http.aclose()

    async def __aenter__(self) -> "NetBrainClient":
        await self.ensure_session()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()
