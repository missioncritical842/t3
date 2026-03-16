"""MCP Server for Nautobot network source of truth.

Exposes Nautobot REST API and GraphQL as MCP tools.

Run:
    uv run nautobot_server.py            # stdio transport
    uv run nautobot_server.py --http     # streamable-http transport
"""

from __future__ import annotations

import json
import logging
import sys

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from nautobot_client import NautobotClient

# ── bootstrap ──────────────────────────────────────────────────────────

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("nautobot-mcp")

mcp = FastMCP(
    "nautobot",
    instructions="MCP server for Nautobot — a network source of truth. Query devices, interfaces, IP addresses, prefixes, VLANs, circuits, locations, and more. Supports GraphQL.",
)

_client: NautobotClient | None = None


def _get_client() -> NautobotClient:
    global _client
    if _client is None:
        _client = NautobotClient()
    return _client


def _fmt(obj: object) -> str:
    return json.dumps(obj, indent=2, default=str)


# ── status ─────────────────────────────────────────────────────────────


@mcp.tool()
async def nautobot_get_status() -> str:
    """Get Nautobot instance status including version and installed apps."""
    return _fmt(await _get_client().get_status())


# ── devices ────────────────────────────────────────────────────────────


@mcp.tool()
async def nautobot_get_devices(
    name: str = "",
    location: str = "",
    role: str = "",
    platform: str = "",
    status: str = "",
    manufacturer: str = "",
    model: str = "",
    q: str = "",
    limit: int = 50,
    offset: int = 0,
) -> str:
    """List or search devices in Nautobot.

    Args:
        name: Filter by exact device name
        location: Filter by location name
        role: Filter by role name
        platform: Filter by platform name
        status: Filter by status (e.g. Active, Planned, Staged)
        manufacturer: Filter by manufacturer name
        model: Filter by device type model
        q: General search query across device fields
        limit: Max results to return (default 50)
        offset: Pagination offset
    """
    filters = {}
    if name:
        filters["name"] = name
    if location:
        filters["location"] = location
    if role:
        filters["role"] = role
    if platform:
        filters["platform"] = platform
    if status:
        filters["status"] = status
    if manufacturer:
        filters["manufacturer"] = manufacturer
    if model:
        filters["model"] = model
    if q:
        filters["q"] = q
    return _fmt(await _get_client().get_devices(limit=limit, offset=offset, **filters))


@mcp.tool()
async def nautobot_get_device(device_id: str) -> str:
    """Get full details for a single device by its UUID.

    Args:
        device_id: The device UUID
    """
    return _fmt(await _get_client().get_device(device_id))


# ── interfaces ─────────────────────────────────────────────────────────


@mcp.tool()
async def nautobot_get_interfaces(
    device: str = "",
    name: str = "",
    type: str = "",
    enabled: str = "",
    q: str = "",
    limit: int = 50,
    offset: int = 0,
) -> str:
    """List or search interfaces.

    Args:
        device: Filter by device name
        name: Filter by interface name
        type: Filter by interface type (e.g. 1000base-t, virtual, lag)
        enabled: Filter by enabled status (true/false)
        q: General search query
        limit: Max results (default 50)
        offset: Pagination offset
    """
    filters = {}
    if device:
        filters["device"] = device
    if name:
        filters["name"] = name
    if type:
        filters["type"] = type
    if enabled:
        filters["enabled"] = enabled
    if q:
        filters["q"] = q
    return _fmt(await _get_client().get_interfaces(limit=limit, offset=offset, **filters))


@mcp.tool()
async def nautobot_get_interface(interface_id: str) -> str:
    """Get full details for a single interface by UUID.

    Args:
        interface_id: The interface UUID
    """
    return _fmt(await _get_client().get_interface(interface_id))


# ── locations ──────────────────────────────────────────────────────────


@mcp.tool()
async def nautobot_get_locations(
    name: str = "",
    location_type: str = "",
    parent: str = "",
    status: str = "",
    q: str = "",
    limit: int = 50,
    offset: int = 0,
) -> str:
    """List or search locations (sites, buildings, floors, etc.).

    Args:
        name: Filter by location name
        location_type: Filter by location type name
        parent: Filter by parent location name
        status: Filter by status
        q: General search query
        limit: Max results (default 50)
        offset: Pagination offset
    """
    filters = {}
    if name:
        filters["name"] = name
    if location_type:
        filters["location_type"] = location_type
    if parent:
        filters["parent"] = parent
    if status:
        filters["status"] = status
    if q:
        filters["q"] = q
    return _fmt(await _get_client().get_locations(limit=limit, offset=offset, **filters))


@mcp.tool()
async def nautobot_get_location(location_id: str) -> str:
    """Get full details for a single location by UUID.

    Args:
        location_id: The location UUID
    """
    return _fmt(await _get_client().get_location(location_id))


# ── IP addresses ───────────────────────────────────────────────────────


@mcp.tool()
async def nautobot_get_ip_addresses(
    address: str = "",
    device: str = "",
    interface: str = "",
    status: str = "",
    parent: str = "",
    namespace: str = "",
    q: str = "",
    limit: int = 50,
    offset: int = 0,
) -> str:
    """List or search IP addresses.

    Args:
        address: Filter by IP address (e.g. 10.0.0.1/24)
        device: Filter by device name
        interface: Filter by interface name
        status: Filter by status
        parent: Filter by parent prefix
        namespace: Filter by namespace
        q: General search query
        limit: Max results (default 50)
        offset: Pagination offset
    """
    filters = {}
    if address:
        filters["address"] = address
    if device:
        filters["device"] = device
    if interface:
        filters["interface"] = interface
    if status:
        filters["status"] = status
    if parent:
        filters["parent"] = parent
    if namespace:
        filters["namespace"] = namespace
    if q:
        filters["q"] = q
    return _fmt(await _get_client().get_ip_addresses(limit=limit, offset=offset, **filters))


@mcp.tool()
async def nautobot_get_ip_address(ip_id: str) -> str:
    """Get full details for a single IP address by UUID.

    Args:
        ip_id: The IP address UUID
    """
    return _fmt(await _get_client().get_ip_address(ip_id))


# ── prefixes ───────────────────────────────────────────────────────────


@mcp.tool()
async def nautobot_get_prefixes(
    prefix: str = "",
    namespace: str = "",
    status: str = "",
    location: str = "",
    vlan_id: str = "",
    q: str = "",
    limit: int = 50,
    offset: int = 0,
) -> str:
    """List or search IP prefixes/subnets.

    Args:
        prefix: Filter by prefix (e.g. 10.0.0.0/24)
        namespace: Filter by namespace
        status: Filter by status
        location: Filter by location name
        vlan_id: Filter by VLAN ID
        q: General search query
        limit: Max results (default 50)
        offset: Pagination offset
    """
    filters = {}
    if prefix:
        filters["prefix"] = prefix
    if namespace:
        filters["namespace"] = namespace
    if status:
        filters["status"] = status
    if location:
        filters["location"] = location
    if vlan_id:
        filters["vlan_id"] = vlan_id
    if q:
        filters["q"] = q
    return _fmt(await _get_client().get_prefixes(limit=limit, offset=offset, **filters))


@mcp.tool()
async def nautobot_get_prefix(prefix_id: str) -> str:
    """Get full details for a single prefix by UUID.

    Args:
        prefix_id: The prefix UUID
    """
    return _fmt(await _get_client().get_prefix(prefix_id))


# ── VLANs ──────────────────────────────────────────────────────────────


@mcp.tool()
async def nautobot_get_vlans(
    vid: str = "",
    name: str = "",
    status: str = "",
    location: str = "",
    q: str = "",
    limit: int = 50,
    offset: int = 0,
) -> str:
    """List or search VLANs.

    Args:
        vid: Filter by VLAN ID number
        name: Filter by VLAN name
        status: Filter by status
        location: Filter by location name
        q: General search query
        limit: Max results (default 50)
        offset: Pagination offset
    """
    filters = {}
    if vid:
        filters["vid"] = vid
    if name:
        filters["name"] = name
    if status:
        filters["status"] = status
    if location:
        filters["location"] = location
    if q:
        filters["q"] = q
    return _fmt(await _get_client().get_vlans(limit=limit, offset=offset, **filters))


# ── VRFs ───────────────────────────────────────────────────────────────


@mcp.tool()
async def nautobot_get_vrfs(
    name: str = "",
    namespace: str = "",
    q: str = "",
    limit: int = 50,
    offset: int = 0,
) -> str:
    """List or search VRFs.

    Args:
        name: Filter by VRF name
        namespace: Filter by namespace
        q: General search query
        limit: Max results (default 50)
        offset: Pagination offset
    """
    filters = {}
    if name:
        filters["name"] = name
    if namespace:
        filters["namespace"] = namespace
    if q:
        filters["q"] = q
    return _fmt(await _get_client().get_vrfs(limit=limit, offset=offset, **filters))


# ── circuits ───────────────────────────────────────────────────────────


@mcp.tool()
async def nautobot_get_circuits(
    cid: str = "",
    provider: str = "",
    circuit_type: str = "",
    status: str = "",
    q: str = "",
    limit: int = 50,
    offset: int = 0,
) -> str:
    """List or search circuits.

    Args:
        cid: Filter by circuit ID
        provider: Filter by provider name
        circuit_type: Filter by circuit type
        status: Filter by status
        q: General search query
        limit: Max results (default 50)
        offset: Pagination offset
    """
    filters = {}
    if cid:
        filters["cid"] = cid
    if provider:
        filters["provider"] = provider
    if circuit_type:
        filters["circuit_type"] = circuit_type
    if status:
        filters["status"] = status
    if q:
        filters["q"] = q
    return _fmt(await _get_client().get_circuits(limit=limit, offset=offset, **filters))


@mcp.tool()
async def nautobot_get_providers(
    name: str = "",
    q: str = "",
    limit: int = 50,
    offset: int = 0,
) -> str:
    """List or search circuit providers.

    Args:
        name: Filter by provider name
        q: General search query
        limit: Max results (default 50)
        offset: Pagination offset
    """
    filters = {}
    if name:
        filters["name"] = name
    if q:
        filters["q"] = q
    return _fmt(await _get_client().get_providers(limit=limit, offset=offset, **filters))


# ── racks ──────────────────────────────────────────────────────────────


@mcp.tool()
async def nautobot_get_racks(
    name: str = "",
    location: str = "",
    status: str = "",
    q: str = "",
    limit: int = 50,
    offset: int = 0,
) -> str:
    """List or search racks.

    Args:
        name: Filter by rack name
        location: Filter by location name
        status: Filter by status
        q: General search query
        limit: Max results (default 50)
        offset: Pagination offset
    """
    filters = {}
    if name:
        filters["name"] = name
    if location:
        filters["location"] = location
    if status:
        filters["status"] = status
    if q:
        filters["q"] = q
    return _fmt(await _get_client().get_racks(limit=limit, offset=offset, **filters))


# ── cables ─────────────────────────────────────────────────────────────


@mcp.tool()
async def nautobot_get_cables(
    device: str = "",
    status: str = "",
    q: str = "",
    limit: int = 50,
    offset: int = 0,
) -> str:
    """List or search cables/connections.

    Args:
        device: Filter by device name
        status: Filter by status
        q: General search query
        limit: Max results (default 50)
        offset: Pagination offset
    """
    filters = {}
    if device:
        filters["device"] = device
    if status:
        filters["status"] = status
    if q:
        filters["q"] = q
    return _fmt(await _get_client().get_cables(limit=limit, offset=offset, **filters))


# ── platforms / manufacturers ──────────────────────────────────────────


@mcp.tool()
async def nautobot_get_platforms(limit: int = 50, offset: int = 0) -> str:
    """List all platforms (OS types).

    Args:
        limit: Max results (default 50)
        offset: Pagination offset
    """
    return _fmt(await _get_client().get_platforms(limit=limit, offset=offset))


@mcp.tool()
async def nautobot_get_manufacturers(limit: int = 50, offset: int = 0) -> str:
    """List all device manufacturers.

    Args:
        limit: Max results (default 50)
        offset: Pagination offset
    """
    return _fmt(await _get_client().get_manufacturers(limit=limit, offset=offset))


@mcp.tool()
async def nautobot_get_device_types(
    manufacturer: str = "",
    model: str = "",
    q: str = "",
    limit: int = 50,
    offset: int = 0,
) -> str:
    """List or search device types (hardware models).

    Args:
        manufacturer: Filter by manufacturer name
        model: Filter by model name
        q: General search query
        limit: Max results (default 50)
        offset: Pagination offset
    """
    filters = {}
    if manufacturer:
        filters["manufacturer"] = manufacturer
    if model:
        filters["model"] = model
    if q:
        filters["q"] = q
    return _fmt(await _get_client().get_device_types(limit=limit, offset=offset, **filters))


# ── tenancy ────────────────────────────────────────────────────────────


@mcp.tool()
async def nautobot_get_tenants(
    name: str = "",
    q: str = "",
    limit: int = 50,
    offset: int = 0,
) -> str:
    """List or search tenants.

    Args:
        name: Filter by tenant name
        q: General search query
        limit: Max results (default 50)
        offset: Pagination offset
    """
    filters = {}
    if name:
        filters["name"] = name
    if q:
        filters["q"] = q
    return _fmt(await _get_client().get_tenants(limit=limit, offset=offset, **filters))


# ── virtualization ─────────────────────────────────────────────────────


@mcp.tool()
async def nautobot_get_virtual_machines(
    name: str = "",
    cluster: str = "",
    status: str = "",
    q: str = "",
    limit: int = 50,
    offset: int = 0,
) -> str:
    """List or search virtual machines.

    Args:
        name: Filter by VM name
        cluster: Filter by cluster name
        status: Filter by status
        q: General search query
        limit: Max results (default 50)
        offset: Pagination offset
    """
    filters = {}
    if name:
        filters["name"] = name
    if cluster:
        filters["cluster"] = cluster
    if status:
        filters["status"] = status
    if q:
        filters["q"] = q
    return _fmt(await _get_client().get_virtual_machines(limit=limit, offset=offset, **filters))


# ══════════════════════════════════════════════════════════════════════
# WRITE OPERATIONS (create / update / delete)
# ══════════════════════════════════════════════════════════════════════

# ── device write ───────────────────────────────────────────────────────


@mcp.tool()
async def nautobot_create_device(
    name: str,
    device_type: str,
    role: str,
    location: str,
    status: str,
    extra_fields: str = "",
) -> str:
    """Create a new device in Nautobot.

    Args:
        name: Device name/hostname
        device_type: UUID or name of the device type (hardware model)
        role: UUID or name of the device role
        location: UUID or name of the location
        status: Status name (e.g. Active, Planned, Staged)
        extra_fields: Optional JSON string of additional fields (e.g. '{"serial": "ABC123", "platform": "ios"}')
    """
    data: dict = {
        "name": name,
        "device_type": device_type,
        "role": role,
        "location": location,
        "status": status,
    }
    if extra_fields:
        data.update(json.loads(extra_fields))
    return _fmt(await _get_client().create_device(data))


@mcp.tool()
async def nautobot_update_device(device_id: str, fields: str) -> str:
    """Update an existing device.

    Args:
        device_id: The device UUID
        fields: JSON string of fields to update (e.g. '{"name": "new-name", "status": "Active"}')
    """
    return _fmt(await _get_client().update_device(device_id, json.loads(fields)))


@mcp.tool()
async def nautobot_delete_device(device_id: str) -> str:
    """Delete a device by UUID. This is irreversible.

    Args:
        device_id: The device UUID to delete
    """
    code = await _get_client().delete_device(device_id)
    return f"Deleted. HTTP {code}"


# ── interface write ────────────────────────────────────────────────────


@mcp.tool()
async def nautobot_create_interface(
    device: str,
    name: str,
    type: str,
    status: str,
    extra_fields: str = "",
) -> str:
    """Create a new interface on a device.

    Args:
        device: UUID or name of the parent device
        name: Interface name (e.g. GigabitEthernet0/0, eth0)
        type: Interface type (e.g. 1000base-t, virtual, lag, 10gbase-x-sfpp)
        status: Status name (e.g. Active, Planned)
        extra_fields: Optional JSON string of additional fields (e.g. '{"enabled": true, "mtu": 9000}')
    """
    data: dict = {"device": device, "name": name, "type": type, "status": status}
    if extra_fields:
        data.update(json.loads(extra_fields))
    return _fmt(await _get_client().create_interface(data))


@mcp.tool()
async def nautobot_update_interface(interface_id: str, fields: str) -> str:
    """Update an existing interface.

    Args:
        interface_id: The interface UUID
        fields: JSON string of fields to update (e.g. '{"enabled": false, "description": "uplink"}')
    """
    return _fmt(await _get_client().update_interface(interface_id, json.loads(fields)))


@mcp.tool()
async def nautobot_delete_interface(interface_id: str) -> str:
    """Delete an interface by UUID. This is irreversible.

    Args:
        interface_id: The interface UUID to delete
    """
    code = await _get_client().delete_interface(interface_id)
    return f"Deleted. HTTP {code}"


# ── location write ─────────────────────────────────────────────────────


@mcp.tool()
async def nautobot_create_location(
    name: str,
    location_type: str,
    status: str,
    extra_fields: str = "",
) -> str:
    """Create a new location (site, building, floor, etc.).

    Args:
        name: Location name
        location_type: UUID or name of the location type
        status: Status name (e.g. Active, Planned)
        extra_fields: Optional JSON string of additional fields (e.g. '{"parent": "<uuid>", "description": "Main DC"}')
    """
    data: dict = {"name": name, "location_type": location_type, "status": status}
    if extra_fields:
        data.update(json.loads(extra_fields))
    return _fmt(await _get_client().create_location(data))


@mcp.tool()
async def nautobot_update_location(location_id: str, fields: str) -> str:
    """Update an existing location.

    Args:
        location_id: The location UUID
        fields: JSON string of fields to update
    """
    return _fmt(await _get_client().update_location(location_id, json.loads(fields)))


@mcp.tool()
async def nautobot_delete_location(location_id: str) -> str:
    """Delete a location by UUID. This is irreversible.

    Args:
        location_id: The location UUID to delete
    """
    code = await _get_client().delete_location(location_id)
    return f"Deleted. HTTP {code}"


# ── cable write ────────────────────────────────────────────────────────


@mcp.tool()
async def nautobot_create_cable(
    termination_a_type: str,
    termination_a_id: str,
    termination_b_type: str,
    termination_b_id: str,
    status: str,
    extra_fields: str = "",
) -> str:
    """Create a cable connecting two endpoints.

    Args:
        termination_a_type: Object type for side A (e.g. dcim.interface, dcim.frontport)
        termination_a_id: UUID of the side A endpoint
        termination_b_type: Object type for side B (e.g. dcim.interface, dcim.frontport)
        termination_b_id: UUID of the side B endpoint
        status: Status name (e.g. Connected, Planned)
        extra_fields: Optional JSON string of additional fields (e.g. '{"label": "patch-42", "type": "cat6"}')
    """
    data: dict = {
        "termination_a_type": termination_a_type,
        "termination_a_id": termination_a_id,
        "termination_b_type": termination_b_type,
        "termination_b_id": termination_b_id,
        "status": status,
    }
    if extra_fields:
        data.update(json.loads(extra_fields))
    return _fmt(await _get_client().create_cable(data))


@mcp.tool()
async def nautobot_delete_cable(cable_id: str) -> str:
    """Delete a cable by UUID.

    Args:
        cable_id: The cable UUID to delete
    """
    code = await _get_client().delete_cable(cable_id)
    return f"Deleted. HTTP {code}"


# ── rack write ─────────────────────────────────────────────────────────


@mcp.tool()
async def nautobot_create_rack(
    name: str,
    location: str,
    status: str,
    extra_fields: str = "",
) -> str:
    """Create a new rack.

    Args:
        name: Rack name
        location: UUID or name of the location
        status: Status name (e.g. Active, Planned)
        extra_fields: Optional JSON string of additional fields (e.g. '{"u_height": 42, "rack_group": "<uuid>"}')
    """
    data: dict = {"name": name, "location": location, "status": status}
    if extra_fields:
        data.update(json.loads(extra_fields))
    return _fmt(await _get_client().create_rack(data))


@mcp.tool()
async def nautobot_update_rack(rack_id: str, fields: str) -> str:
    """Update an existing rack.

    Args:
        rack_id: The rack UUID
        fields: JSON string of fields to update
    """
    return _fmt(await _get_client().update_rack(rack_id, json.loads(fields)))


@mcp.tool()
async def nautobot_delete_rack(rack_id: str) -> str:
    """Delete a rack by UUID.

    Args:
        rack_id: The rack UUID to delete
    """
    code = await _get_client().delete_rack(rack_id)
    return f"Deleted. HTTP {code}"


# ── IP address write ──────────────────────────────────────────────────


@mcp.tool()
async def nautobot_create_ip_address(
    address: str,
    status: str,
    extra_fields: str = "",
) -> str:
    """Create a new IP address.

    Args:
        address: IP address with prefix length (e.g. 10.0.0.1/24)
        status: Status name (e.g. Active, Reserved, DHCP)
        extra_fields: Optional JSON string of additional fields (e.g. '{"namespace": "Global", "dns_name": "host.example.com"}')
    """
    data: dict = {"address": address, "status": status}
    if extra_fields:
        data.update(json.loads(extra_fields))
    return _fmt(await _get_client().create_ip_address(data))


@mcp.tool()
async def nautobot_update_ip_address(ip_id: str, fields: str) -> str:
    """Update an existing IP address.

    Args:
        ip_id: The IP address UUID
        fields: JSON string of fields to update
    """
    return _fmt(await _get_client().update_ip_address(ip_id, json.loads(fields)))


@mcp.tool()
async def nautobot_delete_ip_address(ip_id: str) -> str:
    """Delete an IP address by UUID.

    Args:
        ip_id: The IP address UUID to delete
    """
    code = await _get_client().delete_ip_address(ip_id)
    return f"Deleted. HTTP {code}"


# ── prefix write ───────────────────────────────────────────────────────


@mcp.tool()
async def nautobot_create_prefix(
    prefix: str,
    status: str,
    extra_fields: str = "",
) -> str:
    """Create a new IP prefix/subnet.

    Args:
        prefix: Network prefix (e.g. 10.0.0.0/24)
        status: Status name (e.g. Active, Reserved, Container)
        extra_fields: Optional JSON string of additional fields (e.g. '{"namespace": "Global", "location": "<uuid>"}')
    """
    data: dict = {"prefix": prefix, "status": status}
    if extra_fields:
        data.update(json.loads(extra_fields))
    return _fmt(await _get_client().create_prefix(data))


@mcp.tool()
async def nautobot_update_prefix(prefix_id: str, fields: str) -> str:
    """Update an existing prefix.

    Args:
        prefix_id: The prefix UUID
        fields: JSON string of fields to update
    """
    return _fmt(await _get_client().update_prefix(prefix_id, json.loads(fields)))


@mcp.tool()
async def nautobot_delete_prefix(prefix_id: str) -> str:
    """Delete a prefix by UUID.

    Args:
        prefix_id: The prefix UUID to delete
    """
    code = await _get_client().delete_prefix(prefix_id)
    return f"Deleted. HTTP {code}"


# ── VLAN write ─────────────────────────────────────────────────────────


@mcp.tool()
async def nautobot_create_vlan(
    vid: int,
    name: str,
    status: str,
    extra_fields: str = "",
) -> str:
    """Create a new VLAN.

    Args:
        vid: VLAN ID number (1-4094)
        name: VLAN name
        status: Status name (e.g. Active, Reserved)
        extra_fields: Optional JSON string of additional fields (e.g. '{"location": "<uuid>", "vlan_group": "<uuid>"}')
    """
    data: dict = {"vid": vid, "name": name, "status": status}
    if extra_fields:
        data.update(json.loads(extra_fields))
    return _fmt(await _get_client().create_vlan(data))


@mcp.tool()
async def nautobot_update_vlan(vlan_id: str, fields: str) -> str:
    """Update an existing VLAN.

    Args:
        vlan_id: The VLAN UUID
        fields: JSON string of fields to update
    """
    return _fmt(await _get_client().update_vlan(vlan_id, json.loads(fields)))


@mcp.tool()
async def nautobot_delete_vlan(vlan_id: str) -> str:
    """Delete a VLAN by UUID.

    Args:
        vlan_id: The VLAN UUID to delete
    """
    code = await _get_client().delete_vlan(vlan_id)
    return f"Deleted. HTTP {code}"


# ── VRF write ──────────────────────────────────────────────────────────


@mcp.tool()
async def nautobot_create_vrf(
    name: str,
    namespace: str,
    extra_fields: str = "",
) -> str:
    """Create a new VRF.

    Args:
        name: VRF name
        namespace: Namespace name or UUID
        extra_fields: Optional JSON string of additional fields (e.g. '{"rd": "65000:1", "description": "Customer VRF"}')
    """
    data: dict = {"name": name, "namespace": namespace}
    if extra_fields:
        data.update(json.loads(extra_fields))
    return _fmt(await _get_client().create_vrf(data))


@mcp.tool()
async def nautobot_update_vrf(vrf_id: str, fields: str) -> str:
    """Update an existing VRF.

    Args:
        vrf_id: The VRF UUID
        fields: JSON string of fields to update
    """
    return _fmt(await _get_client().update_vrf(vrf_id, json.loads(fields)))


@mcp.tool()
async def nautobot_delete_vrf(vrf_id: str) -> str:
    """Delete a VRF by UUID.

    Args:
        vrf_id: The VRF UUID to delete
    """
    code = await _get_client().delete_vrf(vrf_id)
    return f"Deleted. HTTP {code}"


# ── circuit write ──────────────────────────────────────────────────────


@mcp.tool()
async def nautobot_create_circuit(
    cid: str,
    provider: str,
    circuit_type: str,
    status: str,
    extra_fields: str = "",
) -> str:
    """Create a new circuit.

    Args:
        cid: Circuit ID
        provider: UUID or name of the provider
        circuit_type: UUID or name of the circuit type
        status: Status name (e.g. Active, Planned, Provisioning)
        extra_fields: Optional JSON string of additional fields (e.g. '{"commit_rate": 10000, "description": "MPLS link"}')
    """
    data: dict = {
        "cid": cid,
        "provider": provider,
        "circuit_type": circuit_type,
        "status": status,
    }
    if extra_fields:
        data.update(json.loads(extra_fields))
    return _fmt(await _get_client().create_circuit(data))


@mcp.tool()
async def nautobot_update_circuit(circuit_id: str, fields: str) -> str:
    """Update an existing circuit.

    Args:
        circuit_id: The circuit UUID
        fields: JSON string of fields to update
    """
    return _fmt(await _get_client().update_circuit(circuit_id, json.loads(fields)))


@mcp.tool()
async def nautobot_delete_circuit(circuit_id: str) -> str:
    """Delete a circuit by UUID.

    Args:
        circuit_id: The circuit UUID to delete
    """
    code = await _get_client().delete_circuit(circuit_id)
    return f"Deleted. HTTP {code}"


# ── provider write ─────────────────────────────────────────────────────


@mcp.tool()
async def nautobot_create_provider(
    name: str,
    extra_fields: str = "",
) -> str:
    """Create a new circuit provider.

    Args:
        name: Provider name
        extra_fields: Optional JSON string of additional fields (e.g. '{"asn": 65000, "account": "ACC-123"}')
    """
    data: dict = {"name": name}
    if extra_fields:
        data.update(json.loads(extra_fields))
    return _fmt(await _get_client().create_provider(data))


@mcp.tool()
async def nautobot_update_provider(provider_id: str, fields: str) -> str:
    """Update an existing provider.

    Args:
        provider_id: The provider UUID
        fields: JSON string of fields to update
    """
    return _fmt(await _get_client().update_provider(provider_id, json.loads(fields)))


@mcp.tool()
async def nautobot_delete_provider(provider_id: str) -> str:
    """Delete a provider by UUID.

    Args:
        provider_id: The provider UUID to delete
    """
    code = await _get_client().delete_provider(provider_id)
    return f"Deleted. HTTP {code}"


# ── tenant write ───────────────────────────────────────────────────────


@mcp.tool()
async def nautobot_create_tenant(
    name: str,
    extra_fields: str = "",
) -> str:
    """Create a new tenant.

    Args:
        name: Tenant name
        extra_fields: Optional JSON string of additional fields (e.g. '{"description": "Customer A", "tenant_group": "<uuid>"}')
    """
    data: dict = {"name": name}
    if extra_fields:
        data.update(json.loads(extra_fields))
    return _fmt(await _get_client().create_tenant(data))


@mcp.tool()
async def nautobot_update_tenant(tenant_id: str, fields: str) -> str:
    """Update an existing tenant.

    Args:
        tenant_id: The tenant UUID
        fields: JSON string of fields to update
    """
    return _fmt(await _get_client().update_tenant(tenant_id, json.loads(fields)))


@mcp.tool()
async def nautobot_delete_tenant(tenant_id: str) -> str:
    """Delete a tenant by UUID.

    Args:
        tenant_id: The tenant UUID to delete
    """
    code = await _get_client().delete_tenant(tenant_id)
    return f"Deleted. HTTP {code}"


# ── virtual machine write ─────────────────────────────────────────────


@mcp.tool()
async def nautobot_create_virtual_machine(
    name: str,
    status: str,
    extra_fields: str = "",
) -> str:
    """Create a new virtual machine.

    Args:
        name: VM name
        status: Status name (e.g. Active, Planned)
        extra_fields: Optional JSON string of additional fields (e.g. '{"cluster": "<uuid>", "vcpus": 4, "memory": 8192}')
    """
    data: dict = {"name": name, "status": status}
    if extra_fields:
        data.update(json.loads(extra_fields))
    return _fmt(await _get_client().create_virtual_machine(data))


@mcp.tool()
async def nautobot_update_virtual_machine(vm_id: str, fields: str) -> str:
    """Update an existing virtual machine.

    Args:
        vm_id: The VM UUID
        fields: JSON string of fields to update
    """
    return _fmt(await _get_client().update_virtual_machine(vm_id, json.loads(fields)))


@mcp.tool()
async def nautobot_delete_virtual_machine(vm_id: str) -> str:
    """Delete a virtual machine by UUID.

    Args:
        vm_id: The VM UUID to delete
    """
    code = await _get_client().delete_virtual_machine(vm_id)
    return f"Deleted. HTTP {code}"


# ── jobs ───────────────────────────────────────────────────────────────


@mcp.tool()
async def nautobot_list_jobs(
    name: str = "",
    q: str = "",
    limit: int = 50,
    offset: int = 0,
) -> str:
    """List available Nautobot jobs.

    Args:
        name: Filter by job name
        q: General search query
        limit: Max results (default 50)
        offset: Pagination offset
    """
    filters = {}
    if name:
        filters["name"] = name
    if q:
        filters["q"] = q
    return _fmt(await _get_client().get_jobs(limit=limit, offset=offset, **filters))


@mcp.tool()
async def nautobot_get_job(job_id: str) -> str:
    """Get details for a specific job by UUID.

    Args:
        job_id: The job UUID
    """
    return _fmt(await _get_client().get_job(job_id))


@mcp.tool()
async def nautobot_run_job(job_id: str, data: str = "") -> str:
    """Trigger/run a Nautobot job.

    Args:
        job_id: The job UUID to run
        data: Optional JSON string of job input data/arguments (e.g. '{"dry_run": true}')
    """
    payload = json.loads(data) if data else {}
    return _fmt(await _get_client().run_job(job_id, payload))


@mcp.tool()
async def nautobot_get_job_results(
    job: str = "",
    status: str = "",
    limit: int = 50,
    offset: int = 0,
) -> str:
    """List job execution results.

    Args:
        job: Filter by job UUID
        status: Filter by result status (e.g. SUCCESS, FAILURE, PENDING)
        limit: Max results (default 50)
        offset: Pagination offset
    """
    filters = {}
    if job:
        filters["job"] = job
    if status:
        filters["status"] = status
    return _fmt(await _get_client().get_job_results(limit=limit, offset=offset, **filters))


@mcp.tool()
async def nautobot_get_job_result(result_id: str) -> str:
    """Get details for a specific job result.

    Args:
        result_id: The job result UUID
    """
    return _fmt(await _get_client().get_job_result(result_id))


# ── GraphQL ────────────────────────────────────────────────────────────


@mcp.tool()
async def nautobot_graphql(query: str, variables: str = "") -> str:
    """Run a GraphQL query against Nautobot.

    This is the most flexible way to query Nautobot — you can fetch exactly
    the fields you need across related objects in a single call.

    Args:
        query: The GraphQL query string
        variables: Optional JSON string of variables (e.g. '{"name": "router1"}')

    Example query:
        {
          devices(name: "router1") {
            name
            status { name }
            location { name }
            interfaces {
              name
              ip_addresses { address }
            }
          }
        }
    """
    vars_dict = None
    if variables:
        vars_dict = json.loads(variables)
    return _fmt(await _get_client().graphql(query, variables=vars_dict))


# ── entry point ────────────────────────────────────────────────────────


def main() -> None:
    transport = "stdio"
    if "--http" in sys.argv:
        transport = "streamable-http"
    logger.info("Starting Nautobot MCP server (transport=%s)", transport)
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
