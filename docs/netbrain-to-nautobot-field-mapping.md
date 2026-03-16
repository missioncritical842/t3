# NetBrain → Nautobot Field Mapping

Reference for syncing data from NetBrain into Nautobot. Fields are categorized as
**standard** (maps directly to a built-in Nautobot field) or **custom** (requires a
Nautobot Custom Field or config context).

> **Key use case from Joshua:** Extract interface descriptions from NetBrain to link
> circuits to locations. See [Interface Description → Circuit Linking](#interface-description--circuit-linking).

---

## Devices

| NetBrain Field | Type | Nautobot Field | Nautobot Model | Mapping Type | Notes |
|---|---|---|---|---|---|
| `name` (hostname) | string | `name` | Device | **Standard** | Primary device identifier |
| `mgmtIP` | string | `primary_ip4` / `primary_ip6` | Device → IPAddress | **Standard** | Create IPAddress, assign as primary |
| `mgmtIntf` | string | — | — | **Custom** | `cf_netbrain_mgmt_intf` — no native equivalent |
| `vendor` | string | `device_type.manufacturer.name` | Manufacturer | **Standard** | Match/create Manufacturer by name |
| `model` | string | `device_type.model` | DeviceType | **Standard** | Match/create DeviceType under Manufacturer |
| `ver` | string | `software_version` | SoftwareVersion | **Standard** | Nautobot 3.x has native software tracking |
| `sn` | string | `serial` | Device | **Standard** | Direct 1:1 |
| `site` | string | `location` | Location | **Standard** | Map NetBrain site hierarchy → Nautobot Location tree |
| `loc` | string | `location` (or parent) | Location | **Standard** | Physical location — may map to parent Location |
| `contact` | string | `associated_contacts` | Contact | **Standard** | Nautobot 3.x Contact model |
| `descr` | string | `comments` | Device | **Standard** | Or use `cf_netbrain_description` if comments is reserved |
| `assetTag` | string | `asset_tag` | Device | **Standard** | Direct 1:1 |
| `subTypeName` | string | `role` | Role | **Standard** | Map NetBrain device sub-type to Nautobot Role |
| `layer` | string | — | — | **Custom** | `cf_network_layer` — no native field |
| `oid` | string | — | — | **Custom** | `cf_snmp_oid` — useful for automation |
| `driverName` | string | `platform` | Platform | **Standard** | Map NetBrain driver → Nautobot Platform |
| `fDiscoveryTime` | datetime | — | — | **Custom** | `cf_first_discovered` |
| `lDiscoveryTime` | datetime | — | — | **Custom** | `cf_last_discovered` |
| `assignTags` | string | `tags` | Tag | **Standard** | Parse and map to Nautobot Tags |
| `hasBGPConfig` | bool | — | — | **Custom** | `cf_has_bgp` or derive from BGP Routing Instance |
| `hasOSPFConfig` | bool | — | — | **Custom** | `cf_has_ospf` |
| `hasEIGRPConfig` | bool | — | — | **Custom** | `cf_has_eigrp` |
| `hasISISConfig` | bool | — | — | **Custom** | `cf_has_isis` |
| `hasMulticastConfig` | bool | — | — | **Custom** | `cf_has_multicast` |
| `mem` | string | — | — | **Custom** | `cf_memory` — not a native field |

### Device Mapping Summary

- **Standard fields:** 13 (name, mgmtIP, vendor, model, ver, sn, site, loc, contact, descr, assetTag, subTypeName, driverName, assignTags)
- **Custom fields needed:** 10+ (mgmtIntf, layer, oid, discovery times, routing protocol booleans, mem)

---

## Interfaces

| NetBrain Field | Type | Nautobot Field | Nautobot Model | Mapping Type | Notes |
|---|---|---|---|---|---|
| `name` | string | `name` | Interface | **Standard** | Direct 1:1 |
| `ips[].ip` | string | `ip_addresses` | IPAddress | **Standard** | Create IPAddress, assign to interface via IPAddressToInterface |
| `ips[].maskLen` | int | (part of address) | IPAddress | **Standard** | Combined as `ip/maskLen` in Nautobot `address` field |
| `ipv6s` | string | `ip_addresses` | IPAddress | **Standard** | IPv6 addresses on the interface |
| `macAddr` | string | `mac_address` | Interface | **Standard** | Direct 1:1 |
| `bandwidth` | int | — | — | **Custom** | `cf_bandwidth` — Nautobot doesn't track this natively |
| `speed` | string | — | — | **Custom** | `cf_speed` — or derive interface `type` from it |
| `duplex` | string | — | — | **Custom** | `cf_duplex` |
| `intfStatus` | string | `status` | Status | **Standard** | Map: "up" → Active, "down" → Failed, etc. |
| **`descr`** | **string** | **`description`** | **Interface** | **Standard** | **KEY FIELD — used to link circuits to locations** |
| `mibIndex` | int | — | — | **Custom** | `cf_mib_index` |
| `moduleSlot` | string | — | — | **Custom** | `cf_module_slot` |
| `moduleType` | string | — | — | **Custom** | `cf_module_type` |
| `routingProtocol` | string | — | — | **Custom** | `cf_routing_protocol` |
| `multicastMode` | string | — | — | **Custom** | `cf_multicast_mode` |
| `mplsVrf` | string | `vrfs` | VRF | **Standard** | Map to VRF by name |
| `inAclName` | string | — | — | **Custom** | `cf_inbound_acl` |
| `outAclName` | string | — | — | **Custom** | `cf_outbound_acl` |
| `mode` | string | `mode` | Interface | **Standard** | Map: access/trunk/tagged → Nautobot mode choices |
| `vlan` | string | `untagged_vlan` / `tagged_vlans` | VLAN | **Standard** | Depends on mode |
| `trunkNativeVlan` | string | `untagged_vlan` | VLAN | **Standard** | Native VLAN on trunks |
| `trunkEncapsulation` | string | — | — | **Custom** | `cf_trunk_encapsulation` |
| `ipUnnumberedIp` | string | — | — | **Custom** | `cf_ip_unnumbered` |

### Interface Mapping Summary

- **Standard fields:** 10 (name, IPs, macAddr, intfStatus, descr, mplsVrf, mode, vlan, trunkNativeVlan)
- **Custom fields needed:** 12+ (bandwidth, speed, duplex, mibIndex, moduleSlot/Type, ACLs, etc.)

---

## Sites → Locations

NetBrain uses a hierarchical site tree. Nautobot uses Location with LocationType hierarchy.

| NetBrain Concept | Nautobot Equivalent | Notes |
|---|---|---|
| Tenant | Tenant | Direct 1:1 — or map to top-level Location |
| Domain | — | NetBrain access scope — no Nautobot equivalent |
| Site (top-level) | Location (type: Region or Campus) | Map to parent Location |
| Site (leaf) | Location (type: Site) | Map to child Location |
| Site Path (e.g. `My Network/US/NYC`) | Location parent chain | Reconstruct hierarchy from path segments |
| Site Devices | Device.location | Assign device to the leaf Location |

### Recommended Nautobot LocationType Hierarchy

```
Region          ← NetBrain top-level site folders
  └─ Campus     ← NetBrain mid-level groupings
       └─ Site  ← NetBrain leaf sites (contain devices)
```

---

## Interface Description → Circuit Linking

**This is the primary use case Joshua highlighted.**

NetBrain interface descriptions often encode circuit and location information, e.g.:

```
GigabitEthernet0/0 — descr: "CKT:ACME-12345 TO:NYC-DC1 VIA:ATT"
```

### Extraction Strategy

1. **Pull** all interfaces + descriptions from NetBrain via `GET /CMDB/Interfaces/Attributes`
2. **Parse** the description using regex patterns to extract:
   - Circuit ID (`CKT:ACME-12345` → Circuit.cid)
   - Remote location (`TO:NYC-DC1` → Location.name)
   - Provider (`VIA:ATT` → Provider.name)
3. **Match or create** in Nautobot:
   - `Circuit` with the extracted CID, linked to a `Provider`
   - `CircuitTermination` connecting the circuit to the interface's device/location
4. **Link** the circuit termination to the device's `Location`

### Fields Involved

```
NetBrain Interface.descr
    ├─→ Nautobot Circuit.cid
    ├─→ Nautobot Circuit.provider
    ├─→ Nautobot CircuitTermination.location
    └─→ Nautobot CircuitTermination (linked to device)
```

> **Note:** The exact description format will vary by customer. You'll need to examine
> real interface descriptions once VPN is up to determine the parsing regex patterns.

---

## Topology / Path Data

NetBrain's path calculation has no direct Nautobot equivalent but can be stored.

| NetBrain Feature | Nautobot Equivalent | Notes |
|---|---|---|
| Calculate Path | — | No native path model; store results as config context or job output |
| Topology Map | Cables + Interfaces | Cable connections between interfaces represent physical topology |
| Connected Switch Ports | Cable terminations | Map to Cable objects connecting interfaces |
| Gateway Resolution | — | Can be stored as `cf_gateway` custom field on interface |

---

## Custom Fields to Create in Nautobot

Based on the mapping above, these custom fields should be created before running a sync:

### On Device

| Custom Field Slug | Type | Label |
|---|---|---|
| `cf_netbrain_mgmt_intf` | Text | NetBrain Mgmt Interface |
| `cf_network_layer` | Text | Network Layer |
| `cf_snmp_oid` | Text | SNMP OID |
| `cf_first_discovered` | DateTime | First Discovered |
| `cf_last_discovered` | DateTime | Last Discovered |
| `cf_has_bgp` | Boolean | Has BGP Config |
| `cf_has_ospf` | Boolean | Has OSPF Config |
| `cf_has_eigrp` | Boolean | Has EIGRP Config |
| `cf_has_isis` | Boolean | Has IS-IS Config |
| `cf_has_multicast` | Boolean | Has Multicast Config |
| `cf_memory` | Text | Memory |

### On Interface

| Custom Field Slug | Type | Label |
|---|---|---|
| `cf_bandwidth` | Integer | Bandwidth |
| `cf_speed` | Text | Speed |
| `cf_duplex` | Text | Duplex |
| `cf_mib_index` | Integer | MIB Index |
| `cf_module_slot` | Text | Module Slot |
| `cf_module_type` | Text | Module Type |
| `cf_routing_protocol` | Text | Routing Protocol |
| `cf_multicast_mode` | Text | Multicast Mode |
| `cf_inbound_acl` | Text | Inbound ACL |
| `cf_outbound_acl` | Text | Outbound ACL |
| `cf_trunk_encapsulation` | Text | Trunk Encapsulation |
| `cf_ip_unnumbered` | Text | IP Unnumbered |

---

## Sync Strategy (SSoT)

Nautobot has the **nautobot_ssot** app (v4.1.0) installed. The recommended approach:

1. **Build a SSoT adapter** for NetBrain as a data source
2. Use `cf_system_of_record` (already exists on devices) to track which system owns each record
3. Use `cf_last_synced_from_sor` (already exists) to track last sync time
4. Respect `NAUTOBOT_FAKER=1` env var — when set, fake sensitive data (circuit IDs, descriptions) but keep structural data (provider names, circuit types) real

### Existing Custom Fields (already in Nautobot)

- `cf_system_of_record` — set to `"NetBrain"` for synced devices
- `cf_last_synced_from_sor` — update on each sync run

---

## Sources

- [NetBrain REST API R11.1b — Device Attributes](https://github.com/NetBrainAPI/NetBrain-REST-API-R11.1b)
- [NetBrain REST API V8.03 — Interface Attributes](https://github.com/NetBrainAPI/NetBrain-REST-API-V8.03/blob/master/REST%20APIs%20Documentation/Device%20Interfaces%20Management/Get%20Interface%20Attributes%20API.md)
- Nautobot 3.0.6 GraphQL introspection (live from `netbrain.crbg.nautobot.cloud`)
