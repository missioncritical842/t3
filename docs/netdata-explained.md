# NetData — What It Is and What's In It

---

## What Is NetData?

**NetData** (branded as "Corebridge NetDATA") is a **custom-built internal web application** developed by Corebridge (formerly AIG Life & Retirement). It is the company's primary network data management portal — a centralized UI for viewing, managing, and exporting network inventory data.

- **Current version:** v1.18.0
- **URL:** Internal (CRBG network)
- **Authentication:** CRBG LDAP
- **Copyright:** CRBG 2024

NetData is **not** a third-party product — it's a purpose-built application that aggregates data from multiple enterprise systems (ServiceNow, Meraki, HPNA, CBRE MyData, Palo Alto Panorama) into one unified view. It provides:
- A web UI where users can browse inventories, run reports, and manage network data
- CSV export capabilities for each inventory type
- Integration with ServiceNow CMDB (pushes data to SNOW)
- Integration with CBRE MyData (pulls property/facility data)
- Integration with HPNA (HP Network Automation) — recently migrated to cloud at `https://hpnaprod.crbgf.net`

**The migration project** is moving from NetData as the primary network inventory tool to **Nautobot as the live source of truth** — with NetData CSV exports being one of several data feeds into Nautobot alongside NetBrain, Meraki SSoT, and Aruba Central.

---

## NetData UI Structure

### Main Navigation

The NetData UI has three main navigation sections:

| Menu | Purpose |
|---|---|
| **Inventories** | All network data views (devices, circuits, subnets, etc.) — 13 inventory types |
| **Reports** | Tacacs Accounting, Site Upgrade Info, Netops OS Upgrade, Network Exceptions, Network Events, Metrics, Cisco MS Teams Ext DID Mappings |
| **Tools** | HPNA Script Runner (run scripts on devices via HP Network Automation), Network Path Trace |

Additionally: **Resources**, **Help**, **Quick Links** in the top bar. Export buttons (Excel and CSV download) are available on inventory list views.

### Home Page

The home page shows:
- **Devices per Region:** AMER-E (767), AMER-W (322), EMEA (22) = ~1,111 total devices
- **What's New** section with version release notes
- **Useful Information** linking to the Standard Operating Procedure guide and help documentation

### Inventories Menu

The **Inventories** dropdown is the heart of NetData. Each menu item is a full inventory view that can be browsed in the UI and exported to CSV:

| # | UI Menu Item | CSV Export Name | Rows | What It Contains | Nautobot Mapping |
|---|---|---|---|---|---|
| 1 | **Site Inventory** | `netdata_site` | varies | Master list of all Corebridge facilities — Crest ID, address, region, building status, capacity, headcount | Location objects |
| 2 | **Site Planning** | `netdata_site-planning` | varies | Deployment programs, device counts per site, rollout phases, target dates | Location custom fields / metadata |
| 3 | **Device Inventory** | `netdata_device-inventory` | ~1,777 | The "master list" — every known network device across all vendors and sites. Serial, vendor, model, IP, category, status, Crest ID | Device objects + `observations["netdata_device_inventory"]` |
| 4 | **Subnet Inventory** | `netdata_subnet-inventory` | varies | IP address plan — network IP, wildcard mask, zone (Internal/DMZ), realty location, usage type | Prefix objects in IPAM |
| 5 | **Port Connection Inventory** | *(no CSV import yet)* | — | Port-to-port physical connections | Would map to Cable objects |
| 6 | **Circuit Inventory** | `netdata_circuit` | varies | WAN circuits — carrier, circuit ID, type (MPLS/internet), bandwidth, Crest site, status | Circuit + Provider + CircuitTermination |
| 7 | **Chassis Inventory** | `netdata_chassis` | ~342 | Hardware purchases — serial, vendor, model, purchase date, Crest site ID. Mainly Meraki branch gear | Device objects + `observations["netdata_chassis"]` |
| 8 | **Network Module Management** | *(no CSV import yet)* | — | Module/line card tracking in chassis devices | Would map to Module/InventoryItem objects |
| 9 | **Toll Free Number** | `netdata_toll-free-number` | ~2,292 | Toll-free number assignments per site | Observations on Location objects |
| 10 | **BGP Inventory** | `netdata_bgp` | varies | BGP peering data — ASN, peer IP, neighbor relationships | BGP observations on Device objects |
| 11 | **DHCP Subnet Inventory** | *(possibly part of subnet inventory)* | — | DHCP scope/pool data | Would map to Prefix/IPAM objects |
| 12 | **Panos Device** | `netdata_panos-device` | varies | Palo Alto Panorama management servers and PA-Series firewalls | Device objects + `observations["netdata_panos"]` |
| 13 | **High Risk Country** | *(no CSV import yet)* | — | Geopolitical risk tracking for sites | Would map to Location metadata/tags |

### Not in the Inventories menu but also imported:

| CSV Name | Source | Rows | What It Contains |
|---|---|---|---|
| `netdata_network-on-call-contact` | Exported separately | varies | Network operations on-call contacts — name, email, phone, group |
| `netdata_uccc-contact` | Exported separately | varies | UCCC team contacts |
| `netdata_cisco-ms-teams-ext-did-mappings` | Exported separately | ~33,351 | Microsoft Teams / phone DID number mappings |
| `netdata_netops-os-upgrade` | Exported separately | ~2,871 | OS upgrade tracking — device IP, model, upgrade status |
| `netdata_model-eol` | Exported separately | varies | Hardware end-of-life dates by vendor/model |

---

## Device Inventory View

The Device Inventory list shows all 1,111 devices in a sortable, filterable table with these columns:

| Column | What it shows |
|---|---|
| **Site** | Crest ID (links to the site detail page) |
| **Host Name** | Device hostname (links to device detail) |
| **Management IP** | Primary management IP |
| **Vendor** | Manufacturer |
| **Model** | Hardware model |
| **Category** | Device category (switch, wireless, router, firewall, etc.) |
| **Status** | Active, Inactive, Retired |
| **Is External** | Whether device is externally managed |
| **Confirmed** | Physical inventory verification |
| **HPNA** | Checkbox — is this device in HP Network Automation? |
| **Spectrum** | Checkbox — is this device monitored by CA Spectrum? |
| **Prime** | Checkbox — is this device in Cisco Prime? |
| **SNOW** | Checkbox — is this device in ServiceNow CMDB? |
| **Meraki** | Checkbox — is this a Meraki-managed device? |

The boolean columns (HPNA, Spectrum, Prime, SNOW, Meraki) are a quick way to see **which external systems know about each device** — useful for finding gaps between systems.

---

## Site Detail Page

Clicking a Crest ID opens the **site-centric view** — everything about one physical location:

**Header:** Shows site name, Crest ID, and a summary bar:
- Non-Network Devices count
- Network Devices count
- Subnet Count
- Circuit Count

**Tabs:**
| Tab | What it shows |
|---|---|
| **Site Details** | Address, capacity, headcount, primary usage, embedded Google Map with pin |
| **Location** | Detailed geographic/facility information |
| **Ports** | Port connections at this site |
| **Network Devices** | All devices at this site |
| **Subnets** | IP subnets assigned to this site |
| **Circuits** | WAN circuits terminating at this site |
| **Documents** | Attached files and documentation |

Example: Crest 1000278 = Chicago, 500 West Madison Street, Suite 2850. Office with capacity 44, headcount 23, 7 network devices, 36 subnets, 2 circuits.

---

## Port Connection Inventory

The Port Connection Inventory tracks **what's plugged into each switch port** — endpoint-to-switchport mapping:

| Column | What it shows |
|---|---|
| **MAC Address** | Endpoint's MAC address |
| **IP Address** | Endpoint's IP |
| **Host Name** | Endpoint hostname |
| **Port Name** | Switch port (e.g., GigabitEthernet1/0/24) |
| **Port Description** | Interface description configured on the switch |
| **Vendor** | Switch vendor |
| **Fingerprint** | Device fingerprint/classification |
| **User Name** | Authenticated user (802.1X) |
| **DHCP** | DHCP enabled flag |
| **DHCP Subnet** | Which DHCP scope served this endpoint |
| **Switch/WAP** | Which switch or AP the endpoint connects to |
| **Negotiated Speed** | Link speed |
| **Negotiated Duplex** | Half/full duplex |
| **Configured...** | (additional configuration columns) |

This data would map to **Cable** objects and **Interface** connections in Nautobot. Currently no CSV import exists for this.

---

## Chassis Inventory View

**818 items** — hardware asset tracking with full lifecycle data. Larger than the 342-row CSV export (the CSV may be a filtered subset).

| Column | What it shows | Nautobot mapping |
|---|---|---|
| **Host Name** | Device hostname | Device.name |
| **Location ID** | Crest ID | Device.location |
| **Management IP** | Management IP | Device.primary_ip4 |
| **Serial Number** | Hardware serial | Device.serial |
| **Vendor** | Manufacturer (Meraki, Cisco) | Manufacturer |
| **Model** | Hardware model (MR42, MS250-48FP, MX84, WS-C3850, C9300-48P) | DeviceType |
| **Category** | wireless, switch, router | Role |
| **Purchase Date** | When hardware was bought | `netdata_purchase_date` custom field |
| **End of Life** | Full hardware EOL date | HardwareLCM.end_of_life |
| **End of Support** | Vendor support end date | HardwareLCM.end_of_support |
| **End of Sale** | Last purchasable date | HardwareLCM.end_of_sale |
| **Purchasable** | Can still be purchased? | Derived from End of Sale |
| **SW Version** | Current software/firmware | Device.software_version |
| **SW Status** | current, outdated, critical | Software compliance status |
| **SW Recommendation** | upgrade, maintain, replace | Action needed |
| **End of Support Quarter** | Planning quarter for replacement | Lifecycle planning |
| **Lease Comment** | Lease/contract notes | Asset management |

This is the **single view that combines hardware identity, lifecycle, and software compliance** — the key data for planning refreshes and upgrades.

---

## Circuit Inventory View

The Circuit Inventory shows 91 WAN circuits with these columns:

| Column | What it shows | Nautobot mapping |
|---|---|---|
| **Type** | Circuit classification (MPLS, Internet, etc.) | Circuit.circuit_type |
| **Location ID** | Crest ID of the site | CircuitTermination.location |
| **Carrier** | Service provider (Meraki, AT&T, etc.) | Circuit.provider |
| **Circuit ID** | Provider's reference number | Circuit.cid |
| **Interface Status** | Interface up/down | *(operational data)* |
| **Circuit Status** | Active, Decommissioned (shown in red) | Circuit.status |
| **Bandwidth (Mbps)** | Circuit speed | Circuit.commit_rate |
| **Type** | Additional type classification | Circuit.circuit_type |
| **Local Device** | Hostname of device at this end | CircuitTermination → Device |
| **Local Port** | Port on the local device | CircuitTermination → Interface |
| **Remote Device** | Hostname of device at far end | CircuitTermination (Z-side) → Device |
| **Remote Port** | Port on the remote device | CircuitTermination (Z-side) → Interface |
| **Description** | Free-text description | Circuit.description |

**Key finding:** The Circuit Inventory has **local/remote device and port** data that the current CSV import (`netdata_circuit`) doesn't capture. This would enable full **CircuitTermination → Interface** linking in Nautobot — connecting circuits to specific switch ports on specific devices.

---

## BGP Inventory View

21 BGP entries tracking autonomous system numbers and their device assignments:

| Column | What it shows | Nautobot mapping |
|---|---|---|
| **Number** | ASN (e.g., 22499, 12076) | BGPRoutingInstance.autonomous_system |
| **Type** | public or private | ASN type |
| **Use** | in use, reserved, etc. | Status |
| **Device** | Hostname assigned to this ASN | Device |
| **Site** | Crest ID (datacenter sites: 1003369, 1003371, 1003389, 1003390) | Location |
| **Info** | Additional notes | Description |
| **Last Seen** | Last verification date (April 2026 — actively refreshed) | Last synced |
| **Expires At** | Expiration date if applicable | Lifecycle |

All BGP entries are at **datacenter sites** (AM5, AM6, EMEA datacenters). Devices are routers: `rdcausamr5`, `rb2busamr6`, `rwhebusamr6`, etc.

---

## Subnet Inventory View

**5,373 subnets** — by far the largest inventory in NetData. IP address plan sourced from **BlueCat** IPAM.

| Column | What it shows | Nautobot mapping |
|---|---|---|
| **Valid** | Red X = summary/parent block (skip), Green check = actual subnet (import) | Filter — only import Valid=TRUE |
| **Network IP** | Subnet in CIDR (e.g., 10.194.64.0/18, 10.103.0.0/18) | Prefix.prefix |
| **Floor** | Building floor number | Location metadata |
| **Zone Name** | All "Internal" (also "DMZ 1" in other data) | Namespace (Internal / DMZ 1) |
| **Usage Type** | block, block/Wireless, block/VPN, block/waan, block/server, block/security | Prefix.role or tag |
| **Sources** | All "bluecat" — sourced from BlueCat IPAM | Data lineage |
| **Location ID** | Crest ID linking to site | Prefix → Location |
| **UDF** | User-defined fields | Custom fields |

Usage Type breakdown tells you **what the subnet is for**: wireless networks, VPN pools, WAN links, server farms, security zones, etc.

---

## Site Inventory View

**105 sites** — the master list of all Corebridge facilities. Last updated 9/18/2023.

| Column | What it shows | Nautobot mapping |
|---|---|---|
| **Location ID** | Crest ID (primary key) | Location.facility |
| **CBRE_myData_PropertyId** | MyData property link | Location custom field |
| **Region** | AMER-E, AMER-W, EMEA | Location (Region level) |
| **Country / State / City** | Geographic hierarchy | Location hierarchy |
| **Address** | Street address | Location.physical_address |
| **Postal Code** | ZIP code | Location.physical_address |
| **Building Status** | Active, Vacant | Location.status |
| **Headcount / Capacity** | Current vs max occupancy | Location custom fields |
| **HRC Status** | Non-HRC (High Risk Country flag) | Location tag/custom field |
| **Site Category** | BT 2018, BT 2.0, Vacant, Thick Branch | Location tag |
| **Support Maintenance** | Maintenance contract reference | Location custom field |

**Site Categories** are deployment tiers — they define the standard network design for that site:
- **BT 2018** — older branch technology standard
- **BT 2.0** — current branch technology standard
- **Thick Branch** — larger branch with more infrastructure
- **Vacant** — empty/unused site

---

## Reports Menu

| Report | What it provides | CSV mapping |
|---|---|---|
| **Tacacs Accounting** | TACACS+ authentication/authorization logs | *(no CSV)* |
| **Site Upgrade Info** | Site-level upgrade status and planning | Related to `netdata_site-planning` |
| **Netops OS Upgrade** | Device OS upgrade tracking | `netdata_netops-os-upgrade` CSV |
| **Network Exceptions** | HPNA policy violations — ~1,000+ compliance exceptions showing devices that don't meet standard config | *(no CSV)* |
| **Network Events** | Network events and incidents | *(no CSV)* |
| **Metrics** | Performance and operational metrics | *(no CSV)* |
| **Cisco MS Teams Ext DID Mappings** | Phone extension/DID number mappings | `netdata_cisco-ms-teams-ext-did-mappings` CSV |

---

## Tools Menu

| Tool | What it does |
|---|---|
| **HPNA Script Runner** | Execute scripts on network devices via HP Network Automation (HPNA). Cloud instance at `https://hpnaprod.crbgf.net` |
| **Network Path Trace** | Trace network paths between two endpoints. Similar to NetBrain's path calculation |

---

## Device Detail Page

When you click a hostname in the Device Inventory, you see the device detail page with **6 tabs**:

**Tabs:** Device Details | Location | ServiceNow | Meraki | Exceptions | Device Events

> Note: Joshua's documentation described 7 data sections including Lifecycle Management, Circuits/Realty, and Site Planning. In the actual UI these are accessed at the **site level** (nd4), not the device level. The device detail has 6 tabs focused on the device itself. Lifecycle data (EOL dates, software versions) comes from the `netdata_model-eol` and `netdata_netops-os-upgrade` CSVs rather than being visible on the device page.

### 1. Device Details

The core identity of the device.

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

### 2. Location Tab

Where the device physically sits. Property/facilities data pulled from CBRE's MyData system via the CBRE_myData_PropertyId link.

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
| Capacity / Headcount | `50 / 30` | Max occupancy vs current |
| CBRE_myData_PropertyId | `416817` | Links to CBRE's property database |

Location hierarchy: **World Region → Region → Subregion → Country → State → City → Address/Facility**

### 3. ServiceNow Tab

Data from the ServiceNow CMDB. Shows how ServiceNow classifies and tracks this device. Includes a thumbnail image of the device.

| Field | Example | What it tells you |
|---|---|---|
| Sys Id | `fbca71f747d9...` | ServiceNow's unique CI identifier |
| Management IP | `10.194.177.5` | IP as known to SNOW |
| Host Name / Serial / Vendor / Model | (matches Device Details) | SNOW's copy of identity fields |
| Device Type | `Wireless Access Point` | SNOW classification |
| Sys Class Name | `cmdb_ci_netgear` | SNOW CI class |
| Subcategory | `Network` | SNOW subcategory |
| Install Status | `Installed` | Deployment state in SNOW |
| Operational Status | `Operational` | Runtime state in SNOW |
| Discovery Source | `BH-ETL-NET` | How SNOW learned about this device |
| Support Group / Approval Group / Managed By | `Network Operations` | Ownership in SNOW |
| Monitoring Type | `Out-of-Scope` | Monitoring coverage |

### 4. Meraki Tab

Meraki-specific data from the Meraki Dashboard cloud. Only populated for Meraki devices.

| Field | Example | What it tells you |
|---|---|---|
| Network ID / Organization ID | (Meraki GUIDs) | Which Meraki network and org |
| Firmware Version | `wireless-30-7` | Current firmware |
| LAN IP / Public IP / MAC | (network addresses) | Network identity |
| Product Type | `wireless` | wireless, switch, appliance, camera, sensor |
| Last Reported At | `2026-03-15T10:00:00Z` | Last cloud check-in |
| License Status / Expiration | `licensed` / `2027-01-01` | License health |

### 5. Exceptions Tab

Tracks **sync failures** between NetData and ServiceNow. When NetData tries to push field updates to the SNOW CMDB and fails, the exception is logged here.

| Column | What it shows |
|---|---|
| **Exception Details** | What failed (e.g., "Attempt to update SNOW approvalGroup from 'null' to 'Network Operations-Mgr' failed") |
| **Notes** | Additional context |
| **Group Name** | Which group/category |
| **Category** | Exception category |
| **Created At** | When the exception occurred |
| **Updated At** | Last update |

This is valuable for **data quality monitoring** — shows where NetData and ServiceNow are out of sync.

### 6. Device Events Tab

A full **audit log** of everything that's happened to this device in NetData. Shows 153 events for this one device, including:

- "Attempting to synchronize device"
- "Normal sync process for wwapus0278-028a-001 / 10.194.177.107 completed"
- "Updated SNOW model from 'null' to 'MR42'"
- "Updated SNOW deviceType from 'null' to 'Wireless Access Point'"
- "Found multiple snow ci records matching managementIp: 10.194.177.10 or serialNumber: Q2KD-9445-UKQ1"

| Column | What it shows |
|---|---|
| **Description** | What happened |
| **Created By** | Who/what triggered it (admin, kkumarga, internal) |
| **Created At** | Timestamp (events go back to 2023) |

This audit trail shows the **full history of data synchronization** between NetData and external systems.

### Tabs Vary by Device Type

The device detail tabs change depending on the vendor/management system:

| Device Type | Tabs |
|---|---|
| **Meraki devices** (APs, switches, firewalls) | Device Details, Location, ServiceNow, **Meraki**, Exceptions, Device Events |
| **Cisco/traditional devices** (routers, switches) | Device Details, Location, ServiceNow, **HPNA**, Exceptions, Device Events |

The 4th tab is vendor-specific:
- **Meraki tab** — Meraki Dashboard data (WAN IPs, MAC, firmware, network ID, license)
- **HPNA tab** — HP Network Automation data (config management, script execution)

**HPNA tab fields** (only on non-Meraki devices):

| Field | Example | What it tells you |
|---|---|---|
| HPNA Support | yes | Can HPNA manage this device? |
| Access Type | good | HPNA reachability (good/failed/unknown) |
| Software Version | 17.09.05a | **Live software version** from HPNA — authoritative for Cisco/Arista |
| HPNA Access | ICMP 1, SSH 1, TELNET 0, SNMP 1.3.6.1.4.1.9.1.1707 | Protocol reachability: ping yes, SSH yes, Telnet no, SNMP OID |
| Twin IP | 10.184.182.2 | **HA pair** — the redundant peer's IP |
| Twin Primary | Yes | This device is the primary in the HA pair |
| Twin Hostname | rwanus0733-01a-002 | HA peer's hostname |
| Management Interface | Sdwan-system-vtf | Which interface HPNA manages through |
| Location Id | 1000733 | Crest ID |

The HPNA tab provides **live software version, HA pair information, and access verification** — data that neither NetBrain nor the CMDB has. This is especially valuable for:
- Software compliance tracking (exact running version)
- HA pair mapping (which devices are redundant peers)
- Reachability validation (can we SSH/SNMP to this device?)

Other differences for the Cisco ISR4451 router vs the Meraki WAP:
- Device Family: **Cisco IOS** (empty on Meraki)
- Device Type: **Router** (empty on Meraki)
- Sys Class Name: **cmdb_ci_ip_router** (vs cmdb_ci_netgear)
- Monitoring Type: **Full** (vs Out-of-Scope)
- Network Flags: **smanage** (vs empty)
- Status: **Installed** (vs Active)
- Confirmed: **false** (vs true)

### Lifecycle, Circuits, and Site Planning Data

These data categories from Joshua's documentation are accessed at the **site level** (Site Inventory → click a Crest ID), not the device level:

- **Lifecycle Management** (EOL dates, software versions) — comes from `netdata_model-eol` and `netdata_netops-os-upgrade` CSVs
- **Circuits / Realty Data** — visible on the site detail page Circuits tab (nd4) and Circuit Inventory (nd9)
- **Site Planning** (device counts, deployment programs) — visible on the site detail page and `netdata_site-planning` CSV

---

## Resources Menu

The Resources menu provides access to contact and scheduling data:

| Item | What it provides | CSV mapping |
|---|---|---|
| **Network On Call Contacts** | Network operations on-call contact list | `netdata_network-on-call-contact` |
| **Network On Call Schedule** | On-call rotation schedule | *(no CSV import yet)* |
| **UCCC Contacts** | Unified Communications contact center team | `netdata_uccc-contact` |
| **UCCC On Duty Schedule** | UCCC duty rotation schedule | *(no CSV import yet)* |

The contact lists are imported into Nautobot as Contact objects. The **schedules** (on-call rotations, duty schedules) don't have CSV imports yet — this is operational scheduling data that could be valuable for incident response workflows.

---

## Connected Systems (Quick Links)

NetData links directly to all integrated external systems:

| Quick Link | What it is |
|---|---|
| **BlueCat (Eric Dittman) - PROD** | BlueCat IPAM — source of all 5,373 subnets in Subnet Inventory |
| **HPNA - UAT** | HP Network Automation test instance |
| **HPNA - PROD** | HP Network Automation production — config management, script execution, compliance |
| **NetDATA - DEV** | NetData development environment |
| **NetDATA - PROD** | NetData production environment |
| **ServiceNow** | ServiceNow CMDB — bidirectional device sync |

NetData also has **Help** resources: page-level help, SOP documents, bug/feedback submission, and release notes.

---

## Integrations with Other Systems

NetData is an **aggregator** — almost all its data comes from other systems. It is NOT a primary data source. Understanding this is critical for the Nautobot migration: we should pull from the original sources wherever possible, not from NetData.

| System | Direction | What flows | Can Nautobot pull directly? |
|---|---|---|---|
| **ServiceNow CMDB** | Bidirectional (NetData ↔ SNOW) | Device records, vendor/model validation, CI status | Future — API access planned |
| **CBRE MyData** | MyData → NetData | Property/facility data, site information | ✅ MyData import jobs exist |
| **HPNA** (HP Network Automation) | HPNA → NetData | Live SW version, HA pairs, access flags, compliance | ❓ Need API access |
| **Meraki Dashboard** | Meraki → NetData | Meraki device data, firmware, licensing | ✅ Meraki SSoT plugin |
| **Palo Alto Panorama** | Panorama → NetData | PAN-OS firewall data | Via PAN-OS CSV |
| **BlueCat IPAM** | BlueCat → NetData | All 5,373 subnets | ⚠️ Partial integration |
| **Sakon** (TEM platform) | Sakon → NetData | Circuit data: carrier, circuit ID, bandwidth, status, billing | ✅ Sakon Circuit Rollup job |
| **CA Spectrum** | Spectrum → NetData | Device monitoring presence (boolean flag only) | ❓ Unknown |
| **Cisco Prime** | Prime → NetData | Device presence (boolean flag only) | ❓ Unknown |
| **LDAP (CRBG)** | LDAP → NetData | User authentication | N/A |

### Key insight: NetData is being replaced, not replicated
The Nautobot migration strategy is NOT to rebuild NetData's aggregation logic. Instead, Nautobot pulls directly from the **11 original sources** (Meraki, Aruba Central, Aruba Orchestrator, NetBrain, MyData, BlueCat, Sakon, HPNA, ServiceNow, Cisco ACI, Arista CloudVision) plus NetData CSVs as a bridge for data that doesn't have a direct integration yet.

### Important note from NetData home page:
> "Due to the ServiceNow CmdbIdentityNetdata Netgear API has not been updated yet on ServiceNow side, Netdata is currently unable to push any Managed By Group updates to the CMDB. Once ServiceNow has included the new field as an editable field for Netdata, The standard update will work. Data pulls from ServiceNow is not affected by this."

This tells us NetData has a **bidirectional relationship with ServiceNow** — it both reads from and writes to the CMDB.

---

## The Crest ID — The Universal Key

The **Crest ID** is the numeric facility code (like `1000278`) that uniquely identifies a physical site across all of NetData. Every inventory references sites by Crest ID:

- Device Inventory: "this device is at Crest ID 1000278"
- Circuit Inventory: "this circuit terminates at Crest ID 1000278"
- Chassis Inventory: "this hardware was shipped to Crest ID 1000278"
- Contacts: "this person is on-call for Crest ID 1000278"
- Subnets: "this IP range is at Crest ID 1000278"

In Nautobot, Crest IDs map to Location objects via the `facility` field. We also created alias locations with the Crest ID as the name so import jobs can find them.

Example: Crest ID `1000278` = Chicago - 500 West Madison Street

---

## What's Not Yet Imported Into Nautobot

These NetData inventories exist in the UI but don't have corresponding CSV imports yet:

| Inventory | Potential Nautobot Mapping | Priority |
|---|---|---|
| **Port Connection Inventory** | Cable objects (device-to-device connections) | High — physical topology |
| **Network Module Management** | Module / InventoryItem objects | Medium — hardware tracking |
| **DHCP Subnet Inventory** | IPAM Prefix objects with DHCP role | Medium — IP management |
| **High Risk Country** | Location tags or custom fields | Low — security metadata |

### Data that won't be migrated as integrations
Per Joshua (April 2026):
- **Contacts/on-call** — will be manually updated per location. Not a priority, not an integration.
- **Purchase/asset data** — not yet discussed. Future scope.
- **Device Events/Exceptions** — NetData-internal audit logs, not reproducible from external sources.

---

## The 12 Integrations (The Big Picture)

NetData is one of 12 data sources feeding into Nautobot. The project is getting all 12 to coexist without clobbering each other:

| # | Source | Direction | Status | What it provides |
|---|---|---|---|---|
| 1 | **Meraki SSoT** | In → Nautobot | ✅ Working | Meraki devices (APs, switches, firewalls) |
| 2 | **Aruba Central** | In → Nautobot | ✅ Working | Aruba switches and APs |
| 3 | **Aruba Orchestrator** | In → Nautobot | ✅ Working | SilverPeak WAN optimizers |
| 4 | **NetBrain** | In → Nautobot | ✅ Working | Live network discovery (~1,042 devices) |
| 5 | **MyData/CBRE** | In → Nautobot | ✅ Working | Physical locations/properties |
| 6 | **BlueCat** | In → Nautobot | ⚠️ Partial | Subnets/IPAM |
| 7 | **HPNA** | In → Nautobot | ❓ Need API access | HA pairs, SW versions, compliance |
| 8 | **Sakon** | In → Nautobot | ✅ Working | Circuits (carrier, billing, status) |
| 9 | **NetData CSVs** | In → Nautobot | ✅ Working | Bridge data until direct integrations replace it |
| 10 | **Cisco ACI** | In → Nautobot | ❓ Unknown | ACI fabric data |
| 11 | **Arista CloudVision** | In → Nautobot | ⚠️ Partial | Arista device management |
| 12 | **ServiceNow** | Out ← Nautobot | ❓ Future | Push canonical data back to CMDB |

**Phase 1** (current): Get all sources importing with observations. **Phase 2** (next): Fine-tune rollup rules so sources don't clobber each other. **Phase 3** (future): Contacts, asset tracking, compliance reporting.

---

## Screenshots Collected

| # | Screenshot | What it shows | Status |
|---|---|---|---|
| nd1 | Home page | Version (v1.18.0), What's New, Devices per Region, HPNA migration note | ✅ Documented |
| nd2 | Inventories menu | All 13 inventory types in dropdown | ✅ Documented |
| nd3 | Device Inventory list | Columns, 1111 devices, boolean system flags (HPNA/Spectrum/Prime/SNOW/Meraki) | ✅ Documented |
| nd4 | Site Detail (Crest 1000278) | Chicago office, tabs, summary counts, Google Map, address, capacity | ✅ Documented |
| nd5 | Port Connection Inventory | Column headers (MAC, IP, Port, Vendor, DHCP, Speed, Duplex), empty data | ✅ Documented |
| nd6 | Reports menu | 7 report types including Tacacs, OS Upgrade, Network Events, Metrics | ✅ Documented |
| nd7 | Tools menu | HPNA Script Runner, Network Path Trace, Excel/CSV export buttons | ✅ Documented |
| nd8 | Device detail (wwapus0278-028a-001) | 6 tabs: Device Details, Location, ServiceNow, Meraki, Exceptions, Device Events | ✅ Documented |
| nd9 | Circuit Inventory | 91 circuits with carrier, circuit ID, status, bandwidth, local/remote device+port, description | ✅ Documented |
| nd10 | Device detail — Location tab | Full facility data from MyData: region, country, city, address, lat/lng, building status, capacity, headcount | ✅ Documented |
| nd11 | Device detail — ServiceNow tab | CMDB data: Sys ID, device type, install/operational status, discovery source, support group, monitoring type, device image | ✅ Documented |
| nd12 | Device detail — Meraki tab | Meraki Dashboard data: WAN IPs, serial, MAC, lat/lng, address, LAN IP, network ID, model, claimed at | ✅ Documented |
| nd13 | Device detail — Exceptions tab | ServiceNow sync failures: 4 exceptions showing failed CMDB field updates with timestamps | ✅ Documented |
| nd14 | Device detail — Device Events tab | Full audit log (153 events): sync attempts, SNOW updates, duplicate CI detection, created by/timestamps | ✅ Documented |
| nd15 | BGP Inventory | 21 BGP entries: ASN, type (public), device, site, last seen, expires at | ✅ Documented |
| nd16 | Subnet Inventory | 5,373 subnets: Valid flag, Network IP, Zone (Internal), Usage Type, Source (bluecat), Location ID | ✅ Documented |
| nd17 | Site Inventory | 105 sites: Crest ID, MyData PropertyId, Region, Address, Building Status, Capacity, HRC Status, Site Category | ✅ Documented |
| nd18 | Non-Meraki device detail (Cisco ISR4451) | Different tabs: HPNA instead of Meraki. Cisco IOS family, cmdb_ci_ip_router, Full monitoring | ✅ Documented |
| nd19 | Resources menu | Network On Call Contacts/Schedule, UCCC Contacts/On Duty Schedule | ✅ Documented |
| nd20 | Chassis Inventory | 818 items: hostname, serial, vendor, model, category, purchase date, EOL/EOS/EOS dates, SW version/status/recommendation | ✅ Documented |
| nd21 | Network Exceptions report | ~1,000+ HPNA policy violations and compliance exceptions by device | ✅ Documented |
| nd22 | HPNA tab (Cisco ISR4451) | Live software version, HA pair info (twin IP/hostname), HPNA access verification, SNMP OID | ✅ Documented |
| nd23 | Help menu | Page Help, SOP Document, Bug/Feedback, Release Notes, Sign out | ✅ Documented |
| nd24 | Quick Links menu | BlueCat PROD, HPNA UAT+PROD, NetDATA DEV+PROD, ServiceNow | ✅ Documented |

## Screenshots Still Needed

These would help complete the documentation and plan future Nautobot imports:

1. ~~**Device detail — all tabs**~~ ✅ nd8-nd14
2. ~~**Circuit Inventory**~~ ✅ nd9
3. ~~**Subnet Inventory**~~ ✅ nd16
4. ~~**BGP Inventory**~~ ✅ nd15
5. ~~**Site Inventory**~~ ✅ nd17
6. ~~**Chassis Inventory view**~~ ✅ nd20
7. ~~**A Reports page**~~ ✅ nd21
8. ~~**Resources menu**~~ ✅ nd19
9. ~~**Non-Meraki device detail**~~ ✅ nd18 + nd22 (HPNA tab)
10. ~~**Help menu**~~ ✅ nd23
11. ~~**Quick Links**~~ ✅ nd24

**All major NetData views have been documented.** 24 screenshots covering every inventory, every device tab, every menu, and reports.
