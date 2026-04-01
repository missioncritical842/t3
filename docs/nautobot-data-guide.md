# Nautobot Data Guide — What You're Looking At

This guide explains what each section of the Nautobot UI contains, where the data came from, and how everything connects.

---

## The Big Picture

Nautobot is a **network source of truth**. Multiple systems feed data into it, each contributing different facts about the same devices:

```
NetBrain (live network discovery)  ──┐
Netdata Chassis (purchase records)  ──┼──> Nautobot Device
Netdata Inventory (CMDB records)   ──┤    (single object with
Aruba Central (cloud management)   ──┤     observations from
Meraki Dashboard (cloud management)──┘     each source)
```

Each source writes its raw data into a **namespaced observations** custom field on the device. A separate **rollup job** reads all observations and picks the best value for each canonical Nautobot field.

---

## Devices (Devices → Devices)

**Current count: ~1,700 devices**

Each device has:
- **Name** — the hostname (e.g., `rwanus0300-05A-001`)
- **Status** — Active, Offline, Staged
- **Role** — what it does (Router, Cisco IOS Switch, Arista Switch, Palo Alto Firewall, F5 Load Balancer, etc.)
- **Device Type** — the hardware model (e.g., `DCS-7280SR3-48YC8`, `PA-5260`, `MX450`)
- **Manufacturer** — who made it (Cisco, Arista, Palo Alto Networks, Meraki, F5, Aruba, etc.)
- **Platform** — the OS/driver
- **Location** — where it lives (see Locations below)
- **Serial Number** — hardware serial
- **Primary IP** — management IP address (populated by rollup)

### Where device data comes from

| Source | What it contributes | Observation namespace |
|---|---|---|
| **Netdata Chassis** (342 devices) | Serial, model, vendor, purchase date, Crest site ID | `observations["netdata_chassis"]` |
| **Netdata Device Inventory** (1,777 devices) | Serial, model, vendor, IP, status, device category, Crest site ID | `observations["netdata_device_inventory"]` |
| **Netdata PAN-OS** | Palo Alto Panorama + PA-Series firewalls | `observations["netdata_panos"]` |
| **Netdata NetOps** | OS upgrade tracking data | `observations["netdata_netops_upgrade"]` |
| **NetBrain** (~620 non-WAP devices) | Live discovery: hostname, mgmtIP, interfaces, BGP, site path, software version | `observations["netbrain"]` |
| **Aruba Central** | Aruba switches and APs from cloud management | `observations["aruba_central"]` |
| **Meraki** (via SSoT plugin) | Meraki devices from dashboard API | (managed by SSoT, not observations) |

### The observations custom field

Click any device → scroll to **Custom Fields** → look for **observations**. You'll see a JSON blob like:

```json
{
  "netdata_chassis": {
    "schema_version": 1,
    "data": {
      "remote": {
        "Host Name": "rwanus0300-05A-001",
        "Serial Number": "Q2EW-XXXX-XXXX",
        "Vendor": "Meraki",
        "Model": "MX84",
        "Purchase Date": "2023-01-15",
        "Crest ID": "1000300",
        "Status": "Active"
      }
    }
  },
  "netdata_device_inventory": {
    "schema_version": 1,
    "data": {
      "remote": {
        "Host Name": "rwanus0300-05A-001",
        "Serial Number": "Q2EW-XXXX-XXXX",
        "Category": "Router",
        "IP Address": "10.x.x.x",
        ...full CMDB record...
      }
    }
  },
  "netbrain": {
    "schema_version": 1,
    "meta": {
      "fetched_at": "2026-03-31T...",
      "source": "netbrain_import_demo"
    },
    "data": {
      "remote": {
        "name": "rwanus0300-05A-001",
        "mgmtIP": "10.x.x.x",
        "vendor": "Cisco",
        "model": "MX84",
        "subTypeName": "Cisco Meraki Firewall",
        "ver": "wired-18-2-11",
        "site": "My Network\\CRBGF Branch Offices\\1000300-Houston-TX",
        ...60+ fields from NetBrain API...
      }
    }
  }
}
```

**Key concept:** The raw data from each source is preserved exactly as received. Nothing is overwritten. Multiple sources can disagree — the rollup job resolves conflicts.

### Other device custom fields

| Custom Field | What it means |
|---|---|
| `system_of_record` | Which system "owns" this device record (e.g., "NetBrain") |
| `last_synced_from_sor` | When the device was last updated from its source |
| `netdata_purchase_date` | Purchase date from chassis CSV |
| `current_software_version` | Software version (from rollup) |
| `current_software_install_date` | When the software was installed |
| `previous_software_version` | Previous software version before upgrade |

---

## Locations (Organization → Locations)

**Current count: ~496 locations**

Locations use a 4-level hierarchy imported from the MyData/JM instance:

```
Country (8)
  └── State (48)
       └── City (121)
            └── Site (166+)
```

**Examples:**
- United States of America → Texas → Houston → Houston Campus - Life Building
- Ireland → Dublin → Dublin → 1 Hume Street
- United States of America → Virginia → Ashburn → AM5 Data Center

### Location fields

| Field | What it means |
|---|---|
| **Name** | Site name (e.g., "Houston Campus - Life Building") |
| **Location Type** | Country, State, City, or Site |
| **Parent** | The location above it in the hierarchy |
| **Physical Address** | Street address (e.g., "10111 Richmond Ave, Houston, TX") |
| **Latitude / Longitude** | GPS coordinates |
| **Facility** | Crest ID / facility code (e.g., "1000186") — used to match devices from netdata |

### Facility code aliases

Some locations have an additional "alias" location with just the Crest ID as the name (e.g., `1000278`). These exist because the netdata CSVs reference sites by facility code, not by name. The alias maps `1000278` → `Chicago-500 West Madison Street`.

### Special locations

| Location | Purpose |
|---|---|
| **Controllers** | Logical location for Meraki/Aruba controllers (protected — can't be deleted) |
| **Placeholder Site** | Temporary location for devices before rollup assigns their real site |

---

## Interfaces (Devices → Interfaces)

**Current count: ~1,689 interfaces**

Interfaces are created by the Meraki SSoT integration. NetBrain interface data is stored in observations but not yet rolled up into Nautobot Interface objects.

---

## IP Addresses (IPAM → IP Addresses)

**Current count: ~1,751 IP addresses**

Management IPs created during device import. Each device can have a `primary_ip4` pointing to its management address.

---

## Prefixes (IPAM → Prefixes)

**Current count: ~1,751 prefixes**

Covering /24 prefixes auto-created to satisfy Nautobot's IPAM hierarchy requirement. Each IP address needs a parent prefix.

---

## Circuits (Circuits → Circuits)

Imported from `netdata_circuit` CSV. Each circuit has:
- **CID** — Circuit identifier
- **Provider** — Carrier (AT&T, Verizon, etc.)
- **Type** — MPLS, Internet, etc.
- **Bandwidth** — Committed rate
- **Terminations** — A-end linked to a site Location

---

## Contacts (Organization → Contacts)

**Current count: 78 contacts**

Imported from two netdata CSVs:
- `netdata_network-on-call-contact` — network operations on-call contacts
- `netdata_uccc-contact` — UCCC team contacts

Each contact has name, email, phone, and team membership.

---

## Manufacturers & Device Types

**20 manufacturers, 149 device types**

Created automatically during device imports. Examples:
- Cisco → Nexus C93180YC-EX, N9K-C9364C, WS-C3850-12X48U, ...
- Arista → DCS-7280SR3-48YC8, DCS-7280SR3-48YC8-F, ...
- Palo Alto Networks → PA-5260
- F5 → BIG-IP vCMP Guest
- Meraki → MX450, MR44, MS250-24P, ...
- Aruba → 6500M, ap655, ...

---

## Roles

**34 roles**

Device roles map to the function/type of each device:
- Cisco IOS Switch, Cisco Nexus Switch, Cisco Router
- Arista Switch, Aruba Switch
- Palo Alto Firewall, Cisco Meraki Firewall
- F5 Load Balancer
- SilverPeak WAN Optimizer
- Cisco WLC, Aruba IAP, LWAP, Cisco Meraki AP
- IP Phone
- Network Device (default for uncategorized)

---

## Config Contexts (Extensibility → Config Contexts)

| Name | Purpose |
|---|---|
| **CSV Data Store** | Stores all netdata CSV blobs. Jobs read from here via `_load_csv_store()` |
| **NetBrain Credentials** | Stores NetBrain API credentials (username, password, client_id, client_secret) so jobs don't need manual credential entry |

---

## Controllers (Devices → Controllers)

| Controller | Purpose |
|---|---|
| CoreBridge QA Orchestrator USE1 | Aruba Orchestrator integration |
| Aruba Central US5 | Aruba Central cloud integration |

Controllers are linked to External Integrations (API endpoints + secrets) and manage device groups.

---

## Tags

| Tag | What it means |
|---|---|
| Tags from NetBrain's `assignTags` | Classification from network discovery |
| Tags from Meraki SSoT | Device categorization from Meraki |

---

## File Proxies (Extensibility → File Proxies)

Downloadable files generated by jobs:
- `netbrain_missing_devices_*.csv` — audit reports showing devices in NetBrain not in Nautobot

---

## How Data Flows

### Import phase (raw data in)
```
1. Netdata CSVs uploaded to CSV Data Store ConfigContext
2. Observations Device Rollup (Phase 1/1b/1c/1d) reads CSVs → creates Devices with observations
3. Netdata Circuit Import reads circuit CSV → creates Circuits
4. Netdata Contact Import reads contact CSVs → creates Contacts
5. Netdata BGP/Subnet imports read their CSVs → create BGP/prefix data
6. NetBrain Import Demo scans NetBrain API → adds observations["netbrain"] to matching devices
7. Meraki SSoT runs → creates/updates Meraki devices via built-in SSoT plugin
8. Aruba Central Import runs → adds observations["aruba_central"]
```

### Rollup phase (canonical fields out)
```
9. Observations Device Rollup (Phase 2) reads all observation namespaces:
   - Picks best management IP → sets Device.primary_ip4
   - Picks best software version → sets Device.software_version + CFs
   - Detects status mismatches between sources
10. Contact Rollup normalizes contact data
11. BGP Rollup processes BGP observations
12. Location Rollup (MyData) normalizes property/location data
```

### Nightly governance (proposed)
```
13. Device Name rollup — picks canonical hostname from multiple sources
14. Device Role rollup — infers role from signals across sources  
15. Device Status rollup — lifecycle-intent-based status (not transient reachability)
16. Device Platform rollup — normalizes OS/platform from observations
17. Software version rollup — tracks current vs previous versions
18. Hardware EoL rollup — lifecycle milestone tracking
```

---

## Key Concepts

### Why observations instead of direct field mapping?

1. **Non-destructive** — raw source data is never overwritten
2. **Multi-source** — the same device can have data from 5+ systems
3. **Conflict resolution** — rollup jobs decide which source wins for each field
4. **Auditability** — you can always see exactly what each system reported
5. **Re-runnable** — rollup can be re-run without re-fetching from source systems

### Why separate import and rollup?

- **Import is fast** — just identity + raw JSON dump, no complex logic
- **Rollup is controlled** — can be scheduled nightly, supports dry-run
- **Decoupled** — NetBrain API being down doesn't block rollup from existing data
- **Governance** — rollup rules can be reviewed and changed without re-importing
