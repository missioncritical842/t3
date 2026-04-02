# NetData → Nautobot Migration Plan

## Executive Summary

**NetData is an aggregator, not a source.** Almost all its data originates from other systems (ServiceNow, Meraki, HPNA, BlueCat, MyData, Sakon, etc.). The migration strategy is to pull from the **original sources** wherever possible, using NetData CSVs only as a bridge for data that doesn't have a direct API integration yet.

There are **12 integrations** feeding into Nautobot. Getting them all to coexist — writing observations without clobbering each other — is the primary challenge. Fine-tuning field resolution and user experience comes after all sources are importing successfully.

**Per Joshua (April 2026):** Contacts will be manually managed. Purchase/asset data is future scope. The priority is getting 11 inbound sources + 1 outbound (ServiceNow) working together.

---

## How NetData's Data Is Structured (Inferred Backend)

Based on the 24 screenshots and CSV exports, NetData's backend database likely has these core tables:

### Primary Tables

```
┌─────────────────────┐     ┌──────────────────────┐
│  Device              │────▶│  Site (Crest ID)      │
│  - hostname (PK)     │     │  - location_id (PK)   │
│  - mgmt_ip           │     │  - mydata_property_id  │
│  - vendor             │     │  - region              │
│  - model              │     │  - country/state/city  │
│  - serial             │     │  - address             │
│  - category           │     │  - lat/lng             │
│  - status             │     │  - building_status     │
│  - site_id (FK)       │     │  - primary_use         │
│  - confirmed          │     │  - capacity/headcount  │
│  - monitoring_type    │     │  - site_category       │
│  - is_external        │     └──────────────────────┘
│  - network_flags      │
└─────────────────────┘
         │
         │ 1:1 relations (stored as sub-records or joined tables)
         ▼
┌─────────────────────┐     ┌──────────────────────┐
│  SNOW Record         │     │  HPNA Record          │
│  - sys_id (PK)       │     │  - hpna_support       │
│  - device_type       │     │  - access_type        │
│  - sys_class_name    │     │  - software_version   │
│  - install_status    │     │  - hpna_access        │
│  - operational_status│     │  - twin_ip            │
│  - support_group     │     │  - twin_hostname      │
│  - discovery_source  │     │  - twin_primary       │
│  - monitoring_type   │     │  - mgmt_interface     │
└─────────────────────┘     └──────────────────────┘

┌─────────────────────┐
│  Meraki Record       │
│  - serial            │
│  - mac               │
│  - wan1_ip/wan2_ip   │
│  - lan_ip            │
│  - network_id        │
│  - lat/lng           │
│  - address           │
│  - model             │
│  - claimed_at        │
│  - public_ip         │
└─────────────────────┘
```

### Other Tables

```
┌─────────────────────┐     ┌──────────────────────┐
│  Circuit             │────▶│  Site (via Crest ID)   │
│  - circuit_id (PK)   │     └──────────────────────┘
│  - location_id (FK)  │
│  - carrier           │     ┌──────────────────────┐
│  - type              │────▶│  Device (local)       │
│  - bandwidth         │     │  Device (remote)      │
│  - status            │     │  Port (local)         │
│  - local_device (FK) │     │  Port (remote)        │
│  - local_port        │     └──────────────────────┘
│  - remote_device (FK)│
│  - remote_port       │
│  - description       │
└─────────────────────┘

┌─────────────────────┐     ┌──────────────────────┐
│  Subnet              │────▶│  Site (via Location ID)│
│  - network_ip (PK)   │     └──────────────────────┘
│  - zone_name         │
│  - usage_type        │
│  - source (bluecat)  │
│  - location_id (FK)  │
│  - valid             │
│  - floor             │
└─────────────────────┘

┌─────────────────────┐     ┌──────────────────────┐
│  BGP                 │────▶│  Device (FK)          │
│  - asn (PK)          │     │  Site (FK)            │
│  - type (public/priv)│     └──────────────────────┘
│  - use               │
│  - device (FK)       │
│  - site (FK)         │
│  - last_seen         │
│  - expires_at        │
└─────────────────────┘

┌─────────────────────┐     ┌──────────────────────┐
│  Chassis             │────▶│  Site (via Crest ID)   │
│  - hostname          │     └──────────────────────┘
│  - serial (PK)       │
│  - vendor/model      │
│  - category          │
│  - purchase_date     │
│  - eol/eos/eosale    │
│  - sw_version        │
│  - sw_status         │
│  - sw_recommendation │
└─────────────────────┘

┌─────────────────────┐
│  Contact             │
│  - name              │
│  - email             │
│  - phone             │
│  - user_group        │
└─────────────────────┘

┌─────────────────────┐
│  Exception           │
│  - device (FK)       │
│  - details           │
│  - group_name        │
│  - category          │
│  - created_at        │
└─────────────────────┘

┌─────────────────────┐
│  Device Event        │
│  - device (FK)       │
│  - description       │
│  - created_by        │
│  - created_at        │
└─────────────────────┘

┌─────────────────────┐
│  Port Connection     │
│  - mac_address       │
│  - ip_address        │
│  - hostname          │
│  - port_name         │
│  - switch_wap (FK)   │
│  - vendor            │
│  - dhcp_subnet       │
│  - speed/duplex      │
└─────────────────────┘
```

### Key Relationships

The **Crest ID** (Location ID) is the master foreign key that ties everything together:
- Device → Site (by location_id)
- Circuit → Site (by location_id)
- Subnet → Site (by location_id)
- BGP → Site (by site)
- Chassis → Site (by location_id)
- Contact → Site (via on-call assignments)

Within a Device, there are **sub-records** for each integrated system:
- SNOW record (ServiceNow CMDB data)
- HPNA record (HP Network Automation data) — for Cisco/traditional devices
- Meraki record (Meraki Dashboard data) — for Meraki devices
- Exceptions (sync failure log)
- Device Events (audit log)

---

## Mapping to Nautobot's Data Model

### Nautobot Core Models

| Nautobot Model | Required Fields | Key Relationships |
|---|---|---|
| **Location** | name, location_type, status | parent (self-referential hierarchy) |
| **LocationType** | name | parent (hierarchy: Country→State→City→Site) |
| **Device** | name, device_type, role, status, location | device_type→DeviceType, location→Location, platform→Platform, tenant→Tenant |
| **DeviceType** | model, manufacturer | manufacturer→Manufacturer |
| **Manufacturer** | name | — |
| **Platform** | name | manufacturer (optional) |
| **Role** | name | content_types (what models it applies to) |
| **Interface** | name, type, status, device | device→Device |
| **IPAddress** | address, status | — (linked to interfaces via IPAddressToInterface) |
| **Prefix** | prefix, namespace, status | namespace→Namespace, location→Location (optional) |
| **Circuit** | cid, provider, circuit_type, status | provider→Provider, circuit_type→CircuitType |
| **CircuitTermination** | circuit, term_side | circuit→Circuit, location→Location |
| **Cable** | — | termination_a, termination_b (generic FK to interface/port) |
| **Contact** | name | — (linked via ContactAssociation) |
| **ContactAssociation** | contact, associated_object | contact→Contact, role→Role |
| **Controller** | name, location, controller_type | external_integration→ExternalIntegration |
| **SoftwareVersion** | version, platform | platform→Platform |
| **Tag** | name | — (M2M on any model) |
| **CustomField** | key, type | content_types (which models it applies to) |

### Where NetData's Data Fits

```
NetData Site Inventory          →  Location (type: Site)
  ├─ Region/Country/State/City  →  Location hierarchy (Country→State→City→Site)
  ├─ Building Status            →  Location.status (Active/Planned/Retired)
  ├─ Capacity/Headcount         →  Location custom fields
  ├─ Primary Use                →  Location custom field or tag
  ├─ Site Category (BT 2.0)     →  Location tag
  └─ MyData PropertyId          →  Location custom field

NetData Device Inventory        →  Device
  ├─ Hostname                   →  Device.name
  ├─ Serial Number              →  Device.serial
  ├─ Vendor + Model             →  Device.device_type → DeviceType → Manufacturer
  ├─ Category                   →  Device.role
  ├─ Management IP              →  Device.primary_ip4 → IPAddress
  ├─ Status                     →  Device.status
  ├─ Platform/OS                →  Device.platform
  ├─ Site (Crest ID)            →  Device.location → Location
  └─ Full raw record            →  Device.custom_fields["observations"]["netdata_device_inventory"]

NetData SNOW Data               →  Device custom fields
  ├─ Sys ID                     →  cf_snow_sys_id
  ├─ CI Class                   →  cf_snow_sys_class_name
  ├─ Install/Operational Status →  cf_snow_* fields (or observations)
  ├─ Support Group              →  ContactAssociation (team→device)
  ├─ Discovery Source           →  cf_snow_discovery_source
  └─ Full raw record            →  observations["snow"]

NetData HPNA Data               →  Device custom fields + relationships
  ├─ Software Version           →  Device.software_version → SoftwareVersion
  ├─ Twin IP / Twin Hostname    →  DeviceRedundancyGroup (HA pairs)
  ├─ HPNA Access flags          →  cf_hpna_access or tags
  ├─ Access Type (good/failed)  →  Device tag or cf
  └─ Full raw record            →  observations["hpna"]

NetData Meraki Data             →  observations["meraki"] (or via Meraki SSoT)
  ├─ Network ID                 →  Controller relationship
  ├─ Firmware Version           →  Device.software_version
  ├─ LAN IP / WAN IPs           →  IPAddress objects
  ├─ MAC Address                →  Interface.mac_address
  ├─ License Status             →  cf_meraki_license_status
  └─ Full raw record            →  observations["meraki"]

NetData Circuit Inventory       →  Circuit + CircuitTermination
  ├─ Circuit ID                 →  Circuit.cid
  ├─ Carrier                    →  Circuit.provider → Provider
  ├─ Type (MPLS/Internet)       →  Circuit.circuit_type → CircuitType
  ├─ Bandwidth                  →  Circuit.commit_rate
  ├─ Status                     →  Circuit.status
  ├─ Local Device + Port        →  CircuitTermination (A-side) → Interface
  ├─ Remote Device + Port       →  CircuitTermination (Z-side) → Interface
  └─ Site (Crest ID)            →  CircuitTermination.location

NetData Subnet Inventory        →  Prefix
  ├─ Network IP + Mask          →  Prefix.prefix
  ├─ Zone Name                  →  Prefix.namespace (Internal / DMZ 1)
  ├─ Usage Type                 →  Prefix.role or tag
  ├─ Location ID                →  Prefix.location (optional)
  ├─ Valid flag                 →  Filter: only import Valid=TRUE
  └─ Source (bluecat)           →  cf_source or tag

NetData BGP Inventory           →  BGPRoutingInstance + AutonomousSystem
  ├─ ASN                        →  AutonomousSystem.asn
  ├─ Type (public/private)      →  AutonomousSystem type
  ├─ Device                     →  BGPRoutingInstance.device
  └─ Full record                →  observations["netdata_bgp"]

NetData Chassis Inventory       →  Device (merged) + lifecycle data
  ├─ Purchase Date              →  cf_netdata_purchase_date
  ├─ EOL/EOS/End of Sale        →  HardwareLCM records
  ├─ SW Version / Status        →  SoftwareVersion + cf_sw_status
  ├─ SW Recommendation          →  cf_sw_recommendation
  └─ Full record                →  observations["netdata_chassis"]

NetData Contacts                →  Contact + ContactAssociation
  ├─ Name / Email / Phone       →  Contact fields
  ├─ User Group                 →  Team
  └─ Site assignment            →  ContactAssociation → Location

NetData Exceptions              →  No direct Nautobot equivalent
  └─ Store as                   →  observations["netdata_exceptions"] on Device
                                   OR Job log entries
                                   OR custom model via plugin

NetData Device Events           →  No direct Nautobot equivalent
  └─ Store as                   →  ObjectChange (Nautobot's built-in audit log)
                                   OR observations["netdata_events"] on Device

NetData Port Connections        →  Cable + Interface
  ├─ Switch/WAP                 →  Interface (source)
  ├─ MAC/IP/Hostname            →  Device (endpoint) + Interface
  ├─ Port Name                  →  Interface.name
  └─ Speed/Duplex               →  Interface.speed / Interface.duplex
```

---

## Data Source Authority — Who Creates vs Who Supplements

### Creators (build the device object)

| Device Type | Creator | Why |
|---|---|---|
| **Meraki devices** | **Meraki SSoT** | Cloud management platform is authoritative for claimed/licensed devices |
| **Aruba switches/APs** | **Aruba Central** | Cloud management platform |
| **SilverPeak WAN Opt** | **Aruba Orchestrator** | SD-WAN management platform |
| **Cisco/Arista/Palo Alto/F5** | **Device Inventory CSV** | No cloud platform — CMDB is the business-approved record |
| **IP Phones** | **NetBrain** | Only source that discovers them |
| **Devices not in CMDB** | **NetBrain** | Proof they exist on the network — flag for CMDB review |

### Supplementers (add observations only, never create)

| Source | Adds to | Unique data it provides |
|---|---|---|
| **NetBrain** | ALL devices it discovers | Live interfaces, IPs, BGP, routing protocols, site topology |
| **HPNA** | Cisco/Arista/traditional | HA pairs (only source), live SW version, SSH/SNMP reachability, compliance |
| **Chassis CSV** | Devices with purchase records | Purchase date, EOL/EOS dates, procurement refs |
| **PAN-OS CSV** | Palo Alto firewalls | Panorama management data |
| **NetOps Upgrade CSV** | Devices needing upgrades | SW upgrade tracking |
| **ServiceNow** (future) | All CMDB-tracked devices | Sys ID, CI class, support groups, ownership |
| **Device Inventory CSV** | Devices created by cloud platforms | CMDB fields for devices Meraki/Aruba already created |

### Standalone (not device-related)

| Source | Creates | Notes |
|---|---|---|
| **MyData/CBRE** | Location objects | Authoritative for physical locations |
| **BlueCat** | Prefix objects | Authoritative for IP subnets |
| **Sakon** | Circuit objects | Authoritative for WAN circuits (carrier, billing, status) |
| **Contact CSVs** | Contact objects | Manually managed per location — not a priority |
| **Model EOL CSV** | HardwareLCM records | Hardware lifecycle notices |

### What's NOT an integration (per Joshua)

| Data | Status | Plan |
|---|---|---|
| **Contacts/on-call** | Manually updated per location | Future fine-tuning, not an integration |
| **Purchase/asset data** | Not yet discussed | Future scope |
| **Device Events/Exceptions** | NetData-internal | Not reproducible, won't be migrated |

---

## Recommended Import Sequence

Order matters — parent objects must exist before children. Here's the recommended sequence:

### Phase 0: Foundation (one-time setup)
1. **LocationTypes**: Create Country → State → City → Site → Controller hierarchy
2. **Statuses**: Ensure Active, Planned, Offline, Staged, Retired exist
3. **Namespaces**: Create Internal, DMZ 1 for IPAM

### Phase 1: Locations (from MyData + NetData Sites)
1. **Locations**: Import from `netdata_site` + MyData property data
   - Build hierarchy: Country → State → City → Site
   - Set facility codes, lat/lng, addresses, capacity
   - Create Crest ID alias locations for backward compatibility
   - Observation: `observations["netdata_site"]`

### Phase 2: Device Identity (from multiple sources)
Import order for devices, each adding its observation namespace:

1. **NetData Chassis** (`netdata_chassis`)
   - Creates Device with serial, vendor, model, purchase date
   - Observation: `observations["netdata_chassis"]`
   - Also creates: Manufacturer, DeviceType, Role

2. **NetData Device Inventory** (`netdata_device-inventory`)
   - Matches existing or creates new Device
   - Adds IP, category, status, CMDB data
   - Observation: `observations["netdata_device_inventory"]`

3. **NetData PAN-OS** (`netdata_panos-device`)
   - Matches/creates Palo Alto devices
   - Observation: `observations["netdata_panos"]`

4. **NetData NetOps Upgrade** (`netdata_netops-os-upgrade`)
   - Matches existing devices, adds upgrade tracking
   - Observation: `observations["netdata_netops_upgrade"]`

5. **NetBrain** (our import job)
   - Matches by hostname/serial, adds live discovery data
   - Observation: `observations["netbrain"]`

6. **Aruba Central** (existing job)
   - Matches/creates Aruba devices
   - Observation: `observations["aruba_central"]`

7. **Meraki SSoT** (built-in plugin)
   - Matches/creates Meraki devices via SSoT framework

### Phase 3: Rollup (normalize canonical fields)
Single rollup job reads all observation namespaces and writes canonical fields:

| Canonical Field | Source Priority (highest first) |
|---|---|
| **Device.name** | HPNA > NetBrain > Device Inventory > Chassis |
| **Device.serial** | Chassis > Device Inventory > NetBrain |
| **Device.primary_ip4** | NetBrain (live) > HPNA > Device Inventory |
| **Device.software_version** | HPNA (authoritative) > NetBrain > Chassis |
| **Device.status** | Device Inventory (CMDB) > NetBrain (reachability) |
| **Device.location** | Device Inventory (Crest ID) > NetBrain (site path) |
| **Device.platform** | NetBrain (driverName) > Device Inventory (category) |
| **Device.role** | Device Inventory (category) > NetBrain (subTypeName) |

### Phase 4: Network Data
1. **Circuits** (`sakon_circuits` — authoritative source is Sakon TEM platform)
   - Creates Provider, CircuitType, Circuit, CircuitTermination
   - Links terminations to Locations and optionally to Interfaces
   - Note: `netdata_circuit` may be a view of the same Sakon data enriched with local/remote device+port info

2. **Subnets** (`netdata_subnet-inventory`)
   - Creates Prefix in correct Namespace (Internal/DMZ 1)
   - Links to Location where applicable

3. **BGP** (`netdata_bgp`)
   - Creates AutonomousSystem, BGPRoutingInstance
   - Links to Device

### Phase 5: People & Lifecycle
1. **Contacts** (`netdata_network-on-call-contact`, `netdata_uccc-contact`)
   - Creates Contact, Team, ContactAssociation
   - Links contacts to Locations

2. **Hardware Lifecycle** (`netdata_model-eol`)
   - Creates HardwareLCM records
   - Links to DeviceType

### Phase 6: HA Pairs (from HPNA data)
- Read HPNA twin_ip/twin_hostname from observations
- Create DeviceRedundancyGroup for each HA pair
- Assign primary/secondary based on twin_primary flag

---

## Preserving the NetData User Experience

What a NetData user expects and how to deliver it in Nautobot:

### "Show me everything about this device"
**NetData:** Click device → see 6 tabs of data from different systems
**Nautobot:** Device detail page with:
- Standard fields (name, serial, model, status, location, IP, software version)
- `observations` custom field showing raw data from every source
- Related objects panel: interfaces, IPs, circuits, contacts
- Custom fields for SNOW/HPNA/Meraki-specific data
- Tags for system flags (HPNA=yes, Spectrum=yes, SNOW=yes, etc.)

### "Show me everything about this site"
**NetData:** Click Crest ID → see site detail with tabs for devices, subnets, circuits, documents
**Nautobot:** Location detail page with:
- Address, lat/lng, capacity, headcount in custom fields
- Devices tab: all devices at this location
- Prefixes tab: all subnets assigned to this location
- Circuits tab: all circuit terminations at this location
- Contacts: ContactAssociations linking on-call people to this site
- Tags: site category (BT 2.0, Thick Branch, etc.)

### "Show me which devices are out of compliance"
**NetData:** Reports → Network Exceptions (HPNA policy violations)
**Nautobot:** Dynamic Group or saved filter:
- Tag: `hpna-exception` on non-compliant devices
- Or: custom field `cf_compliance_status` = "violation"
- Or: Job that checks observations and generates a report

### "Show me devices by region"
**NetData:** Home page → Devices per Region table
**Nautobot:** Location hierarchy filtering:
- Filter devices by Location (Region level)
- Dashboard widget showing device counts per region

### "Which systems know about this device?"
**NetData:** Boolean columns: HPNA ✓, Spectrum ✓, SNOW ✓, Meraki ✓
**Nautobot:** Tags on each device:
- `source:hpna`, `source:spectrum`, `source:snow`, `source:meraki`, `source:netbrain`
- Or: check which namespaces exist in `observations` JSON

### "Show me HA pairs"
**NetData:** HPNA tab → Twin IP, Twin Hostname, Twin Primary
**Nautobot:** DeviceRedundancyGroup:
- Group name: hostname pair (e.g., "rwanus0733-01a")
- Priority: primary=1, secondary=2
- Both devices linked to the group

---

## Custom Fields Needed

Beyond what already exists, these custom fields should be created:

### On Device
| Field | Type | Grouping | Source |
|---|---|---|---|
| `snow_sys_id` | Text | ServiceNow | SNOW Sys ID |
| `snow_sys_class_name` | Text | ServiceNow | SNOW CI Class |
| `snow_install_status` | Text | ServiceNow | Install Status |
| `snow_operational_status` | Text | ServiceNow | Operational Status |
| `snow_discovery_source` | Text | ServiceNow | Discovery Source |
| `snow_confirmed` | Boolean | ServiceNow | Physical confirmation |
| `snow_monitoring_type` | Text | ServiceNow | Full/Partial/None/Out-of-Scope |
| `hpna_access_type` | Text | HPNA | good/failed/unknown |
| `hpna_access_details` | Text | HPNA | ICMP/SSH/TELNET/SNMP flags |
| `sw_status` | Text | Software Tracking | current/outdated/critical |
| `sw_recommendation` | Text | Software Tracking | upgrade/maintain/replace |
| `is_external` | Boolean | Device Details | Externally managed flag |
| `network_flags` | Text | Device Details | smanage, wireless, etc. |

### On Location
| Field | Type | Grouping | Source |
|---|---|---|---|
| `mydata_property_id` | Integer | MyData | CBRE PropertyId |
| `mydata_primary_use` | Text | MyData | Office/Data Center/etc. |
| `mydata_building_status` | Text | MyData | Active/Vacant/etc. |
| `mydata_capacity` | Integer | MyData | Max occupancy |
| `mydata_headcount` | Integer | MyData | Current occupancy |
| `site_category` | Text | NetData | BT 2018/BT 2.0/Thick Branch |
| `hrc_status` | Text | NetData | High Risk Country flag |

---

## Observation Namespace Registry

Every data source gets a namespace. This is the complete registry:

| Namespace | Source | Written by | On Model |
|---|---|---|---|
| `netdata_chassis` | Chassis CSV | Observations Device Rollup (Phase 1) | Device |
| `netdata_device_inventory` | Device Inventory CSV | Observations Device Rollup (Phase 1b) | Device |
| `netdata_panos` | PAN-OS CSV | Observations Device Rollup (Phase 1c) | Device |
| `netdata_netops_upgrade` | NetOps CSV | Observations Device Rollup (Phase 1d) | Device |
| `netbrain` | NetBrain API | NetBrain Import Demo | Device |
| `aruba_central` | Aruba Central API | Aruba Central Device Import | Device |
| `aruba_orchestrator` | Aruba Orchestrator API | Aruba Orchestrator Import | Device |
| `netdata_circuit` | Circuit CSV | Netdata Circuit Import | Circuit |
| `sakon` | Sakon TEM CSV | Sakon Circuit Rollup | Circuit |
| `netdata_network_on_call` | On-Call CSV | Netdata Contact Import | Contact |
| `netdata_uccc` | UCCC CSV | Netdata Contact Import | Contact |
| `netdata_bgp` | BGP CSV | Netdata BGP Import | Device |
| `netdata_subnet` | Subnet CSV | Netdata Subnet Import | Prefix |
| `netdata_contacts` | Contact Rollup | Netdata Contact Rollup | Location |
| `netdata_did_mappings` | DID CSV | Netdata Contact Rollup | Location |
| `netdata_toll_free` | Toll-Free CSV | Netdata Contact Rollup | Location |
| `mydata_property` | MyData API | MyData Property Import | Location |
| `netdata_site` | Site CSV | MyData Location Rollup | Location |
