# Netdata — What It Is and What's In It

---

## What Is Netdata?

Netdata is **not a product or application** — it's the name for Corebridge's internal **network data warehouse**. It's a collection of CSV exports from multiple enterprise systems, consolidated into one place for network operations. Think of it as the client's master spreadsheet of everything they know about their network — pulled from ServiceNow, asset management, Meraki, facilities databases, and manual tracking.

Before Nautobot, Netdata CSVs were the primary way Corebridge tracked:
- What devices they own
- Where devices are deployed
- What circuits connect their buildings
- Who's on-call at each site
- What subnets exist on their network
- What software is running and what needs upgrading
- Hardware end-of-life dates

**The migration project** is moving from "CSVs in a shared drive" to "Nautobot as the live source of truth" — with Netdata CSVs being one of several data feeds into Nautobot.

---

## The 7 Sections of a Netdata Device Record

In the original Netdata system, each device is a rich record with 7 categories of information. Here's what each contains:

### 1. Device Details

The core identity of the device. This is what you'd see on the "overview" tab.

| Field | Example | What it tells you |
|---|---|---|
| Host Name | `wwapus25sg-001a-OC1` | The device's network hostname |
| Management IP | `10.194.58.220` | How to reach the device for management |
| Device Type | `Wireless Access Point` | What function it serves |
| Vendor | `Meraki` | Who manufactured it |
| Model | `MR42` | Specific hardware model |
| Serial Number | `Q2ED-SENE-4R3L` | Unique hardware identifier |
| Status | `Active` | Is it currently deployed and working? |
| Support Group | `Network Operations` | Who's responsible for it |
| Approval Group | `Network Operations-Mgr` | Who approves changes |
| Monitoring Type | `Full` | Is it fully monitored, partially, or not at all? |
| Sys ID | `Sa2C5ege938dc...` | ServiceNow's unique ID for this device |
| Category | `Infrastructure Services` | High-level classification |
| Install Status | `In use` | Deployment state |
| Network Flags | `wireless` | Tags like wireless, wired, vpn |
| Confirmed | `true` | Has someone physically verified this device exists? |

### 2. Location

Where the device physically sits. This is property/facilities data, often from CBRE's MyData system.

| Field | Example | What it tells you |
|---|---|---|
| World Region | `Americas` | Global region |
| Region | `AMER-E` | Regional subdivision |
| Country | `United States of America` | Country |
| State | `Vermont` | State/province |
| City | `Stowe` | City |
| Address | `69 Hourglass Road` | Street address |
| Postal Code | `05672` | ZIP code |
| Latitude / Longitude | `44.527 / -72.778` | GPS coordinates |
| Building Status | `Active` | Is the building operational? |
| Primary Use | `Special Purpose` | Office, Data Center, Warehouse, etc. |
| Facility Name | `Stowe - 69 Hourglass Road` | Human-readable name |
| Capacity | `50` | Max occupancy |
| Headcount | `30` | Current occupancy |
| CBRE_myData_PropertyId | `416817` | Links to CBRE's property database |

The location hierarchy is: **World Region → Region → Subregion → Country → State → City → Address/Facility**

### 3. Meraki

Meraki-specific data from the Meraki Dashboard cloud. Only populated for Meraki devices (APs, switches, firewalls).

| Field | Example | What it tells you |
|---|---|---|
| Network ID | (Meraki GUID) | Which Meraki network it's in |
| Organization ID | (Meraki GUID) | Which Meraki org it belongs to |
| Network Name | `1000300-Houston-Branch` | Human-readable network name |
| Firmware Version | `wireless-30-7` | Current firmware |
| LAN IP | `10.x.x.x` | Local network IP |
| MAC Address | `aa:bb:cc:dd:ee:ff` | Hardware MAC |
| Public IP | `203.x.x.x` | WAN/public IP |
| Product Type | `wireless` | wireless, switch, appliance, camera, sensor |
| Last Reported At | `2026-03-15T10:00:00Z` | Last cloud check-in |
| License Status | `licensed` | Is the license valid? |
| License Expiration | `2027-01-01` | When does the license expire? |

### 4. ServiceNow (SNOW)

Data from the ServiceNow CMDB (Configuration Management Database). ServiceNow is the IT service management platform.

| Field | Example | What it tells you |
|---|---|---|
| Sys ID | `Sa2C5ege938dc...` | ServiceNow's unique CI identifier |
| CI Class | `cmdb_ci_netgear` | What type of CI this is in SNOW |
| Install Status | `In use` | SNOW's view of deployment status |
| Operational Status | `Unknown` | SNOW's view of operational state |
| Support Group | `Network Operations` | Assigned support team |
| Owned By / Managed By | (person/team) | Ownership and management |
| Cost Center | (accounting code) | Financial tracking |
| Purchase Date | `2023-01-15` | When it was bought |
| Warranty Expiration | `2026-01-15` | When warranty ends |
| Discovery Source | `Network Scan` | How SNOW learned about it |
| First / Last Discovered | (timestamps) | Discovery history |

Common CI Classes: `cmdb_ci_netgear` (generic network), `cmdb_ci_wap_network` (WAPs), `cmdb_ci_ip_switch` (switches), `cmdb_ci_ip_router` (routers), `cmdb_ci_ip_firewall` (firewalls)

### 5. Lifecycle Management

Hardware and software lifecycle tracking — critical for planning replacements and upgrades.

| Field | Example | What it tells you |
|---|---|---|
| Purchase End of Life | `2099-12-31` | When hardware is fully EOL (far future = still active) |
| End of Support | `2099-12-31` | When vendor stops supporting it |
| End of Sale | `2025-12-31` | Last date to purchase new/spares |
| SW Version | `3.22+09` | Current software version |
| SW Status | `current` | Is the software up to date? |
| SW Recommendation | `upgrade` | What action is recommended? |
| Lease / Contract | (reference numbers) | Financial/contract tracking |
| PO Number / SOW Number | (reference numbers) | Procurement tracking |

Software Status values: `current` (good), `outdated` (plan upgrade), `critical` (immediate upgrade), `end-of-life` (replace urgently)

### 6. Circuits / Realty Data

Network circuits and their connection to physical facilities. Links the network to the buildings.

| Field | Example | What it tells you |
|---|---|---|
| Realty Data | `1000831` | Facility ID in the realty system |
| Circuit carrier / ID / type | AT&T / CKT-12345 / MPLS | Which circuit connects this site |
| Bandwidth | `100000 kbps` | Circuit speed |
| Building details | (address, lat/lng, capacity) | The physical facility this circuit terminates at |
| Primary Use | `Office` | What the building is used for |

This data answers: "What circuit connects building X to the network, and what's at that building?"

### 7. Site Planning

Capacity planning and site rollout data — used for network expansion projects.

| Field | Example | What it tells you |
|---|---|---|
| Device counts by type | Switches: 2, APs: 5, Firewalls: 1 | What's deployed at this site |
| Program | `Branch Refresh 2025` | Which deployment program |
| Phase | `Phase 2` | Rollout phase |
| Status | `Complete` | Deployment status |
| Target date | `2025-Q2` | When deployment is planned |

---

## The CSV Exports

Netdata's information is exported as CSV files and uploaded to Nautobot. Here are all the datasets:

### Device Data

| CSV Name | Rows | What's in it |
|---|---|---|
| `netdata_chassis` | ~342 | **Hardware purchases.** Serial, vendor, model, purchase date, Crest site ID. Mainly Meraki branch gear. Tells you what was bought and where it was sent. |
| `netdata_device-inventory` | ~1,777 | **Operational CMDB.** The broadest device list — serial, vendor, model, IP, category, status, Crest site ID. Every known device across all vendors and sites. The "master list." |
| `netdata_panos-device` | varies | **Palo Alto firewalls.** Panorama management servers and PA-Series firewalls specifically. |
| `netdata_netops-os-upgrade` | ~2,871 | **OS upgrade tracking.** Device IP, model, upgrade status, Crest ID. Tracks which devices need software upgrades and who's responsible. |
| `netdata_model-eol` | varies | **End-of-life dates.** Vendor, model, end-of-sale, end-of-support, end-of-security-patches dates. Used to plan hardware replacements. |

### Circuit Data

| CSV Name | Rows | What's in it |
|---|---|---|
| `netdata_circuit` | varies | **WAN circuits.** Carrier, circuit ID, type (MPLS/internet), bandwidth, Crest site, status, description. Every circuit connecting Corebridge's buildings. |

### Contact Data

| CSV Name | Rows | What's in it |
|---|---|---|
| `netdata_network-on-call-contact` | varies | **On-call contacts.** Name, email, phone, user group. Who to call when something breaks. |
| `netdata_uccc-contact` | varies | **UCCC contacts.** Unified communications contact center team members. |
| `netdata_cisco-ms-teams-ext-did-mappings` | ~33,351 | **Phone/Teams mappings.** Name, extension, DID number, soft phone, desk phone. Maps people to phone numbers. |
| `netdata_toll-free-number` | ~2,292 | **Toll-free numbers.** Number assignments per site. |

### Network Data

| CSV Name | Rows | What's in it |
|---|---|---|
| `netdata_subnet-inventory` | varies | **IP subnets.** Network IP, wildcard mask, zone (Internal/DMZ), realty location, usage type. The complete IP address plan. |
| `netdata_bgp` | varies | **BGP peering.** ASN, peer IP, neighbor relationships. The routing infrastructure. |

### Site/Location Data

| CSV Name | Rows | What's in it |
|---|---|---|
| `netdata_site` | varies | **Site master list.** Crest ID, address, region, building status, capacity. The authoritative list of all Corebridge facilities. |
| `netdata_site-planning` | varies | **Site planning data.** Device counts, deployment program, phase, target dates. |

---

## How Netdata Data Gets Into Nautobot

### Step 1: Upload CSVs
Someone exports CSVs from the various source systems and uploads them to Nautobot using the **"Delimited Data Upload"** job. This stores the CSV text in a ConfigContext called **"CSV Data Store"**.

### Step 2: Run Import Jobs
Each CSV has a corresponding Nautobot job:

| CSV | Job | What it creates in Nautobot |
|---|---|---|
| `netdata_chassis` | Observations Device Rollup (Phase 1) | Device + `observations["netdata_chassis"]` |
| `netdata_device-inventory` | Observations Device Rollup (Phase 1b) | Device + `observations["netdata_device_inventory"]` |
| `netdata_panos-device` | Observations Device Rollup (Phase 1c) | Device + `observations["netdata_panos"]` |
| `netdata_netops-os-upgrade` | Observations Device Rollup (Phase 1d) | Device + `observations["netdata_netops_upgrade"]` |
| `netdata_model-eol` | Observations Device Rollup (Phase 3) | HardwareLCM records (lifecycle notices) |
| `netdata_circuit` | Netdata Circuit Import | Circuit + Provider + CircuitTermination |
| `netdata_network-on-call-contact` | Netdata Contact Import | Contact + Team |
| `netdata_uccc-contact` | Netdata Contact Import | Contact + Team |
| `netdata_subnet-inventory` | Netdata Subnet Import | Prefix (in Internal/DMZ namespace) |
| `netdata_bgp` | Netdata BGP Import | BGP observations on devices |

### Step 3: Rollup
The Observations Device Rollup (Phase 2) reads all observation namespaces and populates canonical Nautobot fields: management IP, software version, etc.

---

## How Netdata Relates to Other Systems

Netdata is **one of five data sources** feeding into Nautobot:

```
Netdata (CSVs from CMDB/asset mgmt)
   ├── What we bought (chassis)
   ├── What's deployed (inventory)
   ├── What circuits connect us (circuits)
   ├── Who to call (contacts)
   └── What IPs we use (subnets/BGP)

NetBrain (live network discovery)
   └── What's actually on the network right now

Meraki (cloud management)
   └── Meraki devices from the dashboard

Aruba Central (cloud management)
   └── Aruba switches and APs

MyData / CBRE (property database)
   └── Building/facility information
```

**Netdata knows what you bought and deployed. NetBrain knows what's actually running.** The overlap is where the most valuable insights come from — discrepancies between what's in the CMDB versus what's on the network.

---

## The Crest ID — The Key That Links Everything

The **Crest ID** (also called Realty Data ID) is the universal site identifier across all Netdata CSVs. It's a numeric code like `1000278` that uniquely identifies a physical facility.

Every CSV references sites by Crest ID:
- Device chassis: "this device was shipped to Crest ID 1000278"
- Device inventory: "this device is deployed at Crest ID 1000278"
- Circuits: "this circuit terminates at Crest ID 1000278"
- Contacts: "this person is on-call for Crest ID 1000278"
- Subnets: "this IP range is assigned to Crest ID 1000278"

In Nautobot, Crest IDs map to Location objects (either in the `facility` field or as alias locations with the Crest ID as the name).

Example: Crest ID `1000278` = Chicago - 500 West Madison Street
