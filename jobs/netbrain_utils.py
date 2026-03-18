"""
jobs/netbrain_utils.py

Shared utilities for NetBrain import/sync jobs.

Provides
--------
_sanitize_enabled()             Check NAUTOBOT_FAKER env var
_fake_hostname / _fake_ip_cidr / _fake_serial / etc.   Deterministic fakers
_fake_address()                 Deterministic fake street address
_sanitize_json_tree()           Recursive JSON value faking
_sanitize_device_attrs()        Fake sensitive device fields
_sanitize_interface_attrs()     Fake sensitive interface fields
_sanitize_log_value()           Safe log masking (always active)
_parse_site_path()              Parse NetBrain site path to segments
_utc_now_iso()                  Timezone-aware UTC ISO timestamp
_normalize_ip()                 Parse IP string to CIDR notation
"""

from __future__ import annotations

import datetime
import hashlib
import ipaddress
import os
import random
import re
from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# Deterministic fake-data helpers  (stdlib only -- no external packages)
# Set NAUTOBOT_FAKER=1 (any non-empty value) to enable sanitization.
# Same real value always produces the same fake value across all jobs,
# so relational integrity (device -> interface -> IP) is preserved.
# ---------------------------------------------------------------------------

_FAKER_ENV = "NAUTOBOT_FAKER"

_ADJECTIVES = [
    "amber", "arctic", "azure", "blue", "bold", "bright", "calm", "cedar",
    "clear", "coral", "crisp", "dark", "delta", "dense", "echo", "elder",
    "fixed", "fleet", "frost", "gold", "green", "grey", "iron", "jade",
    "keen", "lake", "lime", "lunar", "maple", "mist", "noble", "north",
    "olive", "opal", "pine", "polar", "prime", "rapid", "red", "ridge",
    "rocky", "royal", "sage", "salt", "sharp", "silver", "sky", "slate",
    "solar", "solid", "stone", "storm", "swift", "teal", "terra", "titan",
    "ultra", "upper", "urban", "vega", "vivid", "west", "white", "wide",
]
_NOUNS = [
    "arch", "bay", "beam", "blade", "branch", "bridge", "cache", "chain",
    "cliff", "cloud", "cluster", "coast", "core", "crest", "cross", "dawn",
    "deck", "dome", "drop", "edge", "field", "flare", "flux", "forge",
    "fork", "frame", "gate", "grid", "grove", "guard", "helm", "hill",
    "hub", "isle", "jump", "keep", "knot", "lane", "leaf", "ledge",
    "link", "mesh", "moor", "node", "path", "peak", "pier", "pipe",
    "plane", "port", "post", "rack", "rail", "reef", "ring", "rise",
    "rock", "root", "route", "run", "shelf", "span", "spine", "stack",
    "stem", "step", "sway", "tide", "tower", "track", "trail", "trunk",
    "vault", "wall", "wave", "well", "wire", "yard", "zone",
]
_FIRST_NAMES = [
    "Aaron", "Alice", "Amy", "Andrew", "Anna", "Benjamin", "Brian", "Carlos",
    "Carol", "Charles", "Chris", "Dana", "Daniel", "David", "Diana", "Elena",
    "Emily", "Eric", "Ethan", "Grace", "Hannah", "Henry", "Isabel", "Jack",
    "James", "Jane", "Jason", "Jennifer", "Jessica", "John", "Jordan",
    "Jose", "Julia", "Karen", "Kevin", "Laura", "Lena", "Leo", "Linda",
    "Lisa", "Lucas", "Marcus", "Maria", "Mark", "Mary", "Matthew", "Maya",
    "Michael", "Michelle", "Miguel", "Nathan", "Nicole", "Noah", "Oliver",
    "Patricia", "Paul", "Peter", "Rachel", "Rebecca", "Richard", "Robert",
    "Ryan", "Sandra", "Sarah", "Scott", "Sophia", "Steven", "Susan",
    "Thomas", "Tyler", "Victor", "Victoria", "William",
]
_LAST_NAMES = [
    "Adams", "Allen", "Anderson", "Baker", "Brown", "Campbell", "Carter",
    "Chen", "Clark", "Collins", "Cook", "Cooper", "Davis", "Edwards",
    "Evans", "Fisher", "Garcia", "Gonzalez", "Green", "Hall", "Harris",
    "Hernandez", "Hill", "Jackson", "Johnson", "Jones", "Kim", "King",
    "Lee", "Lewis", "Lopez", "Martin", "Martinez", "Miller", "Mitchell",
    "Moore", "Morgan", "Nelson", "Parker", "Patel", "Perez", "Phillips",
    "Roberts", "Robinson", "Rodriguez", "Scott", "Smith", "Taylor",
    "Thomas", "Thompson", "Torres", "Turner", "Walker", "White",
    "Williams", "Wilson", "Wright", "Young",
]
_STREETS = [
    "Main St", "Oak Ave", "Elm St", "Park Blvd", "Cedar Rd", "Maple Dr",
    "Ridge Way", "Valley Ln", "Hill Rd", "Lake Dr", "River Rd", "Forest Ave",
]
_CITIES = [
    "Springfield", "Riverdale", "Lakewood", "Fairview", "Hillcrest", "Oakdale",
    "Maplewood", "Clearwater", "Sunrise", "Westfield", "Greenville", "Newport",
]
_US_STATES = [
    "AL", "AZ", "CA", "CO", "FL", "GA", "IL", "MA", "MI", "MN",
    "MO", "NC", "NJ", "NV", "NY", "OH", "OR", "PA", "TN", "TX", "UT", "VA", "WA", "WI",
]


def _sanitize_enabled() -> bool:
    """Return True if NAUTOBOT_FAKER env var is set to any non-empty value."""
    return bool(os.environ.get(_FAKER_ENV))


def _rng(real_value: str) -> random.Random:
    """Seeded Random instance derived from MD5 of real value."""
    seed = int(
        hashlib.md5(real_value.encode(), usedforsecurity=False).hexdigest(), 16
    )
    return random.Random(seed)


# ---------------------------------------------------------------------------
# Individual fakers -- value-seeded for determinism
# ---------------------------------------------------------------------------

def _fake_hostname(real_name: str) -> str:
    """Deterministic readable hostname: {adj}-{noun}-{hex4}"""
    rng = _rng(real_name)
    adj = rng.choice(_ADJECTIVES)
    noun = rng.choice(_NOUNS)
    suffix = hashlib.md5(real_name.encode(), usedforsecurity=False).hexdigest()[:4]
    return f"{adj}-{noun}-{suffix}"


def _fake_ip_cidr(real_cidr: str) -> str:
    """Deterministic fake IP preserving prefix length."""
    iface = ipaddress.ip_interface(real_cidr)
    prefix_len = iface.network.prefixlen
    digest = hashlib.md5(real_cidr.encode(), usedforsecurity=False).digest()
    octets = [b ^ digest[i] for i, b in enumerate(iface.ip.packed)]
    if octets[0] in (0, 127):
        octets[0] = (octets[0] ^ 0x80) or 1
    if octets[3] in (0, 255):
        octets[3] = (digest[4] % 253) + 1
    return f"{ipaddress.ip_address(bytes(octets))}/{prefix_len}"


def _fake_ip(real_ip: str) -> str:
    """Deterministic fake IP without prefix."""
    return _fake_ip_cidr(f"{real_ip}/32").split("/")[0]


def _fake_serial(real_serial: str) -> str:
    """Deterministic serial: SN-{12 uppercase hex chars}"""
    h = hashlib.md5(real_serial.encode(), usedforsecurity=False).hexdigest().upper()
    return f"SN-{h[:12]}"


def _fake_name(real_name: str) -> str:
    """Deterministic full name: '{First} {Last}'"""
    rng = _rng(real_name)
    return f"{rng.choice(_FIRST_NAMES)} {rng.choice(_LAST_NAMES)}"


def _fake_mac(real_mac: str) -> str:
    """Deterministic fake MAC address."""
    digest = hashlib.md5(real_mac.encode(), usedforsecurity=False).hexdigest()
    return ":".join(digest[i:i + 2] for i in range(0, 12, 2))


def _fake_str(real_str: str) -> str:
    """Generic deterministic string: 'Adj Noun' (title case)."""
    rng = _rng(real_str)
    return f"{rng.choice(_ADJECTIVES).title()} {rng.choice(_NOUNS).title()}"


def _fake_site_segment(real_segment: str) -> str:
    """Deterministic fake for a single site path segment."""
    rng = _rng(real_segment)
    return f"{rng.choice(_ADJECTIVES).title()}-{rng.choice(_NOUNS).title()}"


def _fake_description(real_descr: str) -> str:
    """Deterministic fake for a description field."""
    if not real_descr or not real_descr.strip():
        return real_descr
    return _fake_str(real_descr)


def _fake_address(real_addr: str) -> str:
    """Deterministic fake US street address in 'NNNN Street, ZIPCODE/City/ST/USA' format."""
    if not real_addr or not real_addr.strip():
        return real_addr
    rng = _rng(real_addr)
    number = rng.randint(100, 99999)
    street = rng.choice(_STREETS)
    zipcode = rng.randint(10000, 99999)
    city = rng.choice(_CITIES)
    state = rng.choice(_US_STATES)
    return f"{number} {street}, {zipcode}/{city}/{state}/USA"


# ---------------------------------------------------------------------------
# Safe log masking (always active, even when faker is OFF)
# ---------------------------------------------------------------------------

_LOG_IP_RE = re.compile(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}")
_LOG_SERIAL_RE = re.compile(r"(?i)\b[A-Z0-9]{8,}\b")


def _sanitize_log_value(key: str, value: Any) -> str:
    """Return a safe string for logging — masks IPs, serials, hostnames even when faker is OFF."""
    if value is None:
        return "None"
    s = str(value)
    nk = _norm_key(key)
    if nk in _KEY_IP or nk in {"mgmtip", "ip", "ipaddress", "neighborip"}:
        return _LOG_IP_RE.sub("x.x.x.x", s)
    if nk in _KEY_SERIAL or nk in {"sn", "serial", "serialnumber", "module_serial"}:
        return f"SN-xxxx"
    if nk in _KEY_HOSTNAME or nk in {"name", "hostname", "snmpname", "devicename"}:
        if len(s) > 3:
            return s[:3] + "***"
        return "***"
    if nk in {"macaddr", "vdc_mac"}:
        return "xx:xx:xx:xx:xx:xx"
    if nk in {"loc", "geolocation", "site"}:
        return "<masked-location>"
    if nk in {"contact"}:
        return "<masked-contact>"
    # Fall through: mask any embedded IPs
    return _LOG_IP_RE.sub("x.x.x.x", s)


# ---------------------------------------------------------------------------
# Field-level sanitization for NetBrain objects
# ---------------------------------------------------------------------------

# Device fields that need faking
_DEVICE_FAKE_FIELDS = {
    "name": _fake_hostname,
    "mgmtIP": _fake_ip,
    "sn": _fake_serial,
    "module_serial": _fake_serial,
    "assetTag": _fake_str,
    "contact": _fake_name,
    "descr": _fake_description,
    "snmpName": _fake_hostname,
    "geolocation": _fake_str,
    "loc": _fake_address,
    "VDC_MAC": _fake_mac,
    # NOTE: bgpNeighbor is a list of dicts (not a string) — handled in
    # _sanitize_device_attrs via _sanitize_json_tree.
}

# Device fields that are safe to keep real (structural/classification)
_DEVICE_SAFE_FIELDS = frozenset({
    "vendor", "model", "subTypeName", "driverName", "ver", "os",
    "layer", "oid", "mem", "mgmtIntf", "policyGroup",
    "fDiscoveryTime", "lDiscoveryTime",
    "assignTags",
    # All boolean flags
    "hasBGPConfig", "hasBPEConfig", "hasBridgeGroupConfig",
    "hasEIGRPConfig", "hasIPsecVPNConfig", "hasIPv6Config",
    "hasISISConfig", "hasLISPConfig", "hasMCLAGConfig",
    "hasMulticastConfig", "hasNATConfig", "hasOMPConfig",
    "hasOSPFConfig", "hasOTVConfig", "hasPassiveARPLearningConfig",
    "hasQoSConfig", "hasRISEConfig", "hasVPLSConfig", "hasVXLANConfig",
    "isCluster", "isHA", "isMeshAP", "isSdwan", "isTransparent",
    # Structural
    "APMeshRole", "BPE", "OTV", "VPLS", "VXLAN", "Table",
    "_nb_features", "ap_mode", "cluster", "l3vniVrf",
    "vADCid", "vADCs",
    # R12.3 live discovery — structural fields
    "hasSRTunnelConfig", "application", "zone",
})

# Interface fields that need faking
_INTF_FAKE_FIELDS = {
    "name": _fake_hostname,
    "macAddr": _fake_mac,
    "descr": _fake_description,
    "zone": _fake_str,  # security zone names can reveal policy
}

# Interface fields that are safe to keep real (structural/classification)
# R12.3 live discovery additions:
#   vlansFrwdFabric, MTU, COSConfig, COSDefaultValue — structural
#   ESILAG, MCLAG — structural
#   BPEIntf, BPENumber, BPENumberPortChannel, VPLSPEIntf — structural
#   QinQProperties — structural
#   bgID, bgVlans — structural
#   contextIntfName, contextName — structural
#   realIntf, realName — structural
#   tunnelMode — structural
#   isFailover, isL2Overlay, isLocalIntf, isNatIntf, isBPE, isTransparent — structural booleans


def _sanitize_device_attrs(attrs: dict) -> dict:
    """Apply fakers to sensitive device attribute fields. Returns a new dict."""
    out = {}
    for key, val in attrs.items():
        if not val or (isinstance(val, str) and not val.strip()):
            out[key] = val
            continue
        faker = _DEVICE_FAKE_FIELDS.get(key)
        if faker and isinstance(val, str):
            out[key] = faker(val)
        elif key == "site" and isinstance(val, str):
            out[key] = _fake_site_path(val)
        elif key == "bgpNeighbor" and isinstance(val, list):
            # bgpNeighbor is a list of dicts with localAsNum, neighborIp,
            # remoteAsNum — sanitize the whole tree
            out[key] = _sanitize_json_tree(val, seed_prefix="bgpNeighbor")
        elif key == "VDC_MAC" and isinstance(val, str):
            out[key] = _fake_mac(val)
        else:
            out[key] = val
    return out


def _sanitize_interface_attrs(attrs: dict) -> dict:
    """Apply fakers to sensitive interface attribute fields. Returns a new dict."""
    out = {}
    for key, val in attrs.items():
        if not val or (isinstance(val, str) and not val.strip()):
            out[key] = val
            continue
        faker = _INTF_FAKE_FIELDS.get(key)
        if faker and isinstance(val, str):
            out[key] = faker(val)
        elif key == "ips" and isinstance(val, list):
            out[key] = [_sanitize_ip_entry(ip) for ip in val]
        elif key == "ipv6s" and isinstance(val, list):
            out[key] = [_sanitize_ip_entry(ip) for ip in val]
        elif key == "publicIps" and isinstance(val, (list, str)):
            if isinstance(val, list):
                out[key] = [_sanitize_ip_entry(ip) for ip in val]
            elif val.strip():
                out[key] = _fake_ip(val)
            else:
                out[key] = val
        elif key == "zone" and isinstance(val, str):
            out[key] = _fake_str(val)
        else:
            out[key] = val
    return out


def _sanitize_ip_entry(ip_entry: Any) -> Any:
    """Fake an IP entry dict from NetBrain (has 'ip', 'ipLoc', 'maskLen')."""
    if not isinstance(ip_entry, dict):
        return ip_entry
    out = dict(ip_entry)
    ip_loc = ip_entry.get("ipLoc", "")
    if ip_loc:
        fake_cidr = _fake_ip_cidr(ip_loc)
        out["ipLoc"] = fake_cidr
        try:
            out["ip"] = int(ipaddress.ip_address(fake_cidr.split("/")[0]))
        except Exception:
            pass
    return out


# ---------------------------------------------------------------------------
# Recursive JSON sanitizer (for observation bundles)
# ---------------------------------------------------------------------------

_IP_RE = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?:/\d{1,2})?$")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")

# Key name patterns for type-aware faking
_KEY_HOSTNAME = frozenset({"hostname", "devicename", "host", "nodename", "device", "name"})
_KEY_SERIAL = frozenset({"serial", "serialnumber", "sn"})
_KEY_NAME = frozenset({"contactname", "fullname", "displayname"})
_KEY_IP = frozenset({"ip", "ipaddress", "mgmtip", "publicip"})


def _norm_key(key: str) -> str:
    """Lower-case and strip separators for key lookup."""
    return key.lower().replace(" ", "").replace("_", "").replace("-", "")


def _fake_scalar(value: Any, seed: str, key_hint: str = "") -> Any:
    """Deterministic fake for a single JSON leaf value."""
    if isinstance(value, bool) or value is None:
        return value

    nk = _norm_key(key_hint) if key_hint else ""
    rng = _rng(seed)

    if isinstance(value, int):
        if value == 0:
            return rng.randint(0, 9)
        mag = len(str(abs(value)))
        lo = 10 ** (mag - 1) if mag > 1 else 0
        hi = 10 ** mag - 1
        return rng.randint(lo, hi)

    if isinstance(value, float):
        return round(rng.uniform(0.0, max(abs(value) * 2.0, 100.0)), 6)

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return value
        if nk in _KEY_HOSTNAME:
            return _fake_hostname(stripped)
        if nk in _KEY_SERIAL:
            return _fake_serial(stripped)
        if nk in _KEY_NAME:
            return _fake_name(stripped)
        if nk in _KEY_IP:
            return _fake_ip(stripped)
        if _IP_RE.match(stripped):
            try:
                cidr = stripped if "/" in stripped else f"{stripped}/32"
                fake = _fake_ip_cidr(cidr)
                return fake if "/" in stripped else fake.split("/")[0]
            except Exception:
                pass
        if _ISO_DATE_RE.match(stripped):
            y, m, d = rng.randint(2020, 2035), rng.randint(1, 12), rng.randint(1, 28)
            return f"{y}-{m:02d}-{d:02d}{stripped[10:]}"
        return _fake_str(value)

    return value


def _sanitize_json_tree(
    obj: Any,
    seed_prefix: str = "",
    skip_keys: frozenset = frozenset(),
    _key_hint: str = "",
) -> Any:
    """Recursively walk a JSON-like object and fake all leaf values."""
    if isinstance(obj, dict):
        return {
            k: (
                v if k in skip_keys
                else _sanitize_json_tree(
                    v,
                    seed_prefix=f"{seed_prefix}.{k}",
                    skip_keys=skip_keys,
                    _key_hint=k,
                )
            )
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [
            _sanitize_json_tree(
                item,
                seed_prefix=f"{seed_prefix}[{i}]",
                skip_keys=skip_keys,
                _key_hint="",
            )
            for i, item in enumerate(obj)
        ]
    return _fake_scalar(obj, seed=f"{seed_prefix}:{obj!r}", key_hint=_key_hint)


# ---------------------------------------------------------------------------
# Site path helpers
# ---------------------------------------------------------------------------

def _parse_site_path(site_str: str) -> list:
    """Parse a NetBrain site path like 'My Network\\AWS\\us-east-1' into segments."""
    if not site_str:
        return []
    return [s.strip() for s in site_str.replace("/", "\\").split("\\") if s.strip()]


def _fake_site_path(real_path: str) -> str:
    """Deterministic fake for a full site path, preserving structure."""
    segments = _parse_site_path(real_path)
    if not segments:
        return real_path
    # Keep "My Network" prefix unchanged (structural)
    faked = []
    for seg in segments:
        if seg == "My Network":
            faked.append(seg)
        else:
            faked.append(_fake_site_segment(seg))
    return "\\".join(faked)


# ---------------------------------------------------------------------------
# IP / timestamp helpers
# ---------------------------------------------------------------------------

def _utc_now_iso() -> str:
    """Return current UTC time as an ISO 8601 string (timezone-aware)."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _normalize_ip(ip_str: Any, default_prefix: int = 32) -> Optional[str]:
    """Normalize an IP string to CIDR notation. Returns None if unparseable."""
    if ip_str is None:
        return None
    s = str(ip_str).strip()
    if not s:
        return None
    try:
        if "/" in s:
            ipaddress.ip_interface(s)
            return s
        ipaddress.ip_address(s)
        return f"{s}/{int(default_prefix)}"
    except Exception:
        return None


def _nb_ip_to_cidr(ip_entry: dict) -> Optional[str]:
    """Convert a NetBrain IP entry {'ip': int, 'ipLoc': '10.x.x.x/25', 'maskLen': 25} to CIDR."""
    ip_loc = ip_entry.get("ipLoc", "")
    if ip_loc:
        return _normalize_ip(ip_loc)
    # Fallback: convert integer IP
    ip_int = ip_entry.get("ip")
    mask = ip_entry.get("maskLen", 32)
    if ip_int and isinstance(ip_int, int):
        try:
            addr = ipaddress.ip_address(ip_int)
            return f"{addr}/{mask}"
        except Exception:
            pass
    return None


# ---------------------------------------------------------------------------
# Interface type mapping
# ---------------------------------------------------------------------------

_SPEED_TYPE_MAP = {
    "100": "100base-tx",
    "1000": "1000base-t",
    "10000": "10gbase-t",
    "25000": "25gbase-x-sfp28",
    "40000": "40gbase-x-qsfpp",
    "100000": "100gbase-x-qsfp28",
}


def _guess_interface_type(intf_name: str, speed: str = "") -> str:
    """Guess Nautobot interface type from name and speed."""
    name_lower = intf_name.lower()
    if "loopback" in name_lower or "lo" == name_lower:
        return "virtual"
    if "vlan" in name_lower or "svi" in name_lower:
        return "virtual"
    if "tunnel" in name_lower or "gre" in name_lower:
        return "virtual"
    if "port-channel" in name_lower or "bond" in name_lower:
        return "lag"
    if "mgmt" in name_lower or "management" in name_lower:
        return "1000base-t"
    if "virtual" in name_lower or "eni-" in name_lower:
        return "virtual"
    # Try speed-based mapping
    if speed:
        speed_str = str(speed).strip()
        mapped = _SPEED_TYPE_MAP.get(speed_str)
        if mapped:
            return mapped
    # Name-based guesses
    if "tengig" in name_lower or "te" == name_lower[:2]:
        return "10gbase-t"
    if "gigabit" in name_lower or "gi" == name_lower[:2] or "ge" == name_lower[:2]:
        return "1000base-t"
    if "fastethernet" in name_lower or "fa" == name_lower[:2]:
        return "100base-tx"
    if "ethernet" in name_lower or "eth" == name_lower[:3]:
        return "1000base-t"
    if "hundredgig" in name_lower:
        return "100gbase-x-qsfp28"
    if "fortygig" in name_lower:
        return "40gbase-x-qsfpp"
    if "twentyfivegig" in name_lower:
        return "25gbase-x-sfp28"
    return "other"


# ---------------------------------------------------------------------------
# Status mapping
# ---------------------------------------------------------------------------

def _map_intf_status(nb_status: str) -> str:
    """Map NetBrain interface status to Nautobot status name."""
    s = (nb_status or "").strip().lower()
    if s in ("up", "active", "connected"):
        return "Active"
    if s in ("down", "inactive", "notconnect"):
        return "Failed"
    if s in ("admin down", "disabled", "shutdown"):
        return "Planned"
    return "Active"  # default
