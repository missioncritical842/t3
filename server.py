"""MCP Server for NetBrain network management.

Exposes NetBrain REST API operations as MCP tools that can be
consumed by Claude Desktop, Claude Code, or any MCP-compatible client.

Run:
    uv run server.py            # stdio transport (default)
    uv run server.py --http     # streamable-http transport
"""

from __future__ import annotations

import json
import logging
import sys

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from netbrain_client import NetBrainClient

# ── bootstrap ──────────────────────────────────────────────────────────

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("netbrain-mcp")

mcp = FastMCP(
    "netbrain",
    instructions="MCP server that exposes NetBrain network management tools",
)

# Lazy-initialised client (created on first use so env vars are loaded).
_client: NetBrainClient | None = None


def _get_client() -> NetBrainClient:
    global _client
    if _client is None:
        _client = NetBrainClient()
    return _client


def _fmt(obj: object) -> str:
    """Pretty-print any JSON-serialisable object."""
    return json.dumps(obj, indent=2, default=str)


# ── tools ──────────────────────────────────────────────────────────────


@mcp.tool()
async def netbrain_login() -> str:
    """Authenticate to NetBrain and start a session. Call this first."""
    client = _get_client()
    token = await client.login()
    return f"Logged in successfully. Token starts with: {token[:8]}…"


@mcp.tool()
async def netbrain_logout() -> str:
    """End the current NetBrain session."""
    client = _get_client()
    await client.logout()
    return "Logged out."


@mcp.tool()
async def netbrain_get_version() -> str:
    """Get the NetBrain product version."""
    client = _get_client()
    data = await client.get_product_version()
    return _fmt(data)


# ── tenant / domain ───────────────────────────────────────────────────


@mcp.tool()
async def netbrain_list_tenants() -> str:
    """List all accessible tenants."""
    client = _get_client()
    tenants = await client.get_accessible_tenants()
    return _fmt(tenants)


@mcp.tool()
async def netbrain_list_domains(tenant_id: str) -> str:
    """List domains for a tenant.

    Args:
        tenant_id: The tenant UUID to list domains for
    """
    client = _get_client()
    domains = await client.get_accessible_domains(tenant_id)
    return _fmt(domains)


@mcp.tool()
async def netbrain_set_domain(tenant_id: str, domain_id: str) -> str:
    """Set the working domain for the current session.

    Args:
        tenant_id: The tenant UUID
        domain_id: The domain UUID to work in
    """
    client = _get_client()
    result = await client.set_current_domain(tenant_id, domain_id)
    return _fmt(result)


# ── devices ────────────────────────────────────────────────────────────


@mcp.tool()
async def netbrain_search_devices(
    hostname: str = "",
    ip: str = "",
    site_path: str = "",
    skip: int = 0,
    limit: int = 50,
) -> str:
    """Search or list devices in NetBrain.

    Args:
        hostname: Filter by hostname (partial match)
        ip: Filter by IP address
        site_path: Filter by site path
        skip: Number of records to skip (pagination)
        limit: Max records to return (default 50)
    """
    client = _get_client()
    devices = await client.get_devices(
        hostname=hostname or None,
        ip=ip or None,
        site_path=site_path or None,
        skip=skip,
        limit=limit,
    )
    return _fmt(devices)


@mcp.tool()
async def netbrain_get_device_attributes(hostname: str) -> str:
    """Get detailed attributes for a specific device.

    Args:
        hostname: The device hostname
    """
    client = _get_client()
    attrs = await client.get_device_attributes(hostname)
    return _fmt(attrs)


@mcp.tool()
async def netbrain_get_device_config(hostname: str) -> str:
    """Get the running/startup configuration of a device.

    Args:
        hostname: The device hostname
    """
    client = _get_client()
    config = await client.get_device_config(hostname)
    return _fmt(config)


# ── interfaces ─────────────────────────────────────────────────────────


@mcp.tool()
async def netbrain_get_interfaces(hostname: str) -> str:
    """List all interfaces of a device.

    Args:
        hostname: The device hostname
    """
    client = _get_client()
    interfaces = await client.get_interfaces(hostname)
    return _fmt(interfaces)


@mcp.tool()
async def netbrain_get_interface_attributes(
    hostname: str, interface_name: str
) -> str:
    """Get attributes for a specific interface on a device.

    Args:
        hostname: The device hostname
        interface_name: The interface name (e.g. GigabitEthernet0/0)
    """
    client = _get_client()
    attrs = await client.get_interface_attributes(hostname, interface_name)
    return _fmt(attrs)


# ── topology / path ────────────────────────────────────────────────────


@mcp.tool()
async def netbrain_calculate_path(
    source_ip: str, destination_ip: str, protocol: int = 4
) -> str:
    """Calculate the network path between two IP addresses.

    Args:
        source_ip: Source IP address
        destination_ip: Destination IP address
        protocol: IP protocol number (default 4)
    """
    client = _get_client()
    result = await client.calculate_path(source_ip, destination_ip, protocol)
    return _fmt(result)


@mcp.tool()
async def netbrain_get_path_result(task_id: str) -> str:
    """Get the result of a previously triggered path calculation.

    Args:
        task_id: The task ID returned by calculate_path
    """
    client = _get_client()
    result = await client.get_path_result(task_id)
    return _fmt(result)


# ── sites ──────────────────────────────────────────────────────────────


@mcp.tool()
async def netbrain_list_sites() -> str:
    """List all sites in NetBrain."""
    client = _get_client()
    sites = await client.get_sites()
    return _fmt(sites)


@mcp.tool()
async def netbrain_get_site_devices(site_path: str) -> str:
    """List all devices in a specific site.

    Args:
        site_path: The site path (e.g. 'My Network/Site1')
    """
    client = _get_client()
    devices = await client.get_site_devices(site_path)
    return _fmt(devices)


# ── search ─────────────────────────────────────────────────────────────


@mcp.tool()
async def netbrain_search(keyword: str) -> str:
    """Global search across NetBrain objects (devices, interfaces, sites, etc.).

    Args:
        keyword: The search term
    """
    client = _get_client()
    results = await client.search(keyword)
    return _fmt(results)


# ── entry point ────────────────────────────────────────────────────────


def main() -> None:
    transport = "stdio"
    if "--http" in sys.argv:
        transport = "streamable-http"
    logger.info("Starting NetBrain MCP server (transport=%s)", transport)
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
