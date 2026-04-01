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

## Reports Menu

| Report | What it provides | CSV mapping |
|---|---|---|
| **Tacacs Accounting** | TACACS+ authentication/authorization logs | *(no CSV)* |
| **Site Upgrade Info** | Site-level upgrade status and planning | Related to `netdata_site-planning` |
| **Netops OS Upgrade** | Device OS upgrade tracking | `netdata_netops-os-upgrade` CSV |
| **Network Exceptions** | Devices/configs that deviate from standards | *(no CSV)* |
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

## The 7 Sections of a NetData Device Record

When you click into a device in NetData's Device Inventory, you see a rich record with 7 categories of information:

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

### 2. Location

Where the device physically sits. Property/facilities data from CBRE's MyData system.

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

### 3. Meraki

Meraki-specific data from the Meraki Dashboard cloud. Only populated for Meraki devices.

| Field | Example | What it tells you |
|---|---|---|
| Network ID / Organization ID | (Meraki GUIDs) | Which Meraki network and org |
| Firmware Version | `wireless-30-7` | Current firmware |
| LAN IP / Public IP / MAC | (network addresses) | Network identity |
| Product Type | `wireless` | wireless, switch, appliance, camera, sensor |
| Last Reported At | `2026-03-15T10:00:00Z` | Last cloud check-in |
| License Status / Expiration | `licensed` / `2027-01-01` | License health |

### 4. ServiceNow (SNOW)

Data from the ServiceNow CMDB.

| Field | Example | What it tells you |
|---|---|---|
| Sys ID | `Sa2C5ege938dc...` | ServiceNow's unique CI identifier |
| CI Class | `cmdb_ci_netgear` | SNOW classification |
| Install Status / Operational Status | `In use` / `Unknown` | SNOW's view of the device |
| Support Group / Owned By | `Network Operations` | Ownership and management |
| Cost Center / Purchase Date / Warranty | (financial data) | Asset management |
| Discovery Source | `Network Scan` | How SNOW learned about it |

### 5. Lifecycle Management

Hardware and software lifecycle tracking.

| Field | Example | What it tells you |
|---|---|---|
| Purchase End of Life | `2099-12-31` | When hardware is fully EOL |
| End of Support | `2099-12-31` | When vendor stops supporting |
| End of Sale | `2025-12-31` | Last date to buy new/spares |
| SW Version | `3.22+09` | Current software version |
| SW Status | `current` | Is software up to date? |
| SW Recommendation | `upgrade` | What action is recommended? |
| Lease / Contract / PO / SOW | (reference numbers) | Procurement tracking |

### 6. Circuits / Realty Data

Network circuits and their connection to physical facilities.

| Field | Example | What it tells you |
|---|---|---|
| Realty Data | `1000831` | Facility ID linking to realty system |
| Circuit carrier / ID / type | AT&T / CKT-12345 / MPLS | Which circuit connects this site |
| Bandwidth | `100000 kbps` | Circuit speed |
| Building details | (address, lat/lng, capacity) | The physical facility |

### 7. Site Planning

Capacity planning and site rollout data.

| Field | Example | What it tells you |
|---|---|---|
| Device counts by type | Switches: 2, APs: 5, Firewalls: 1 | What's deployed at this site |
| Program | `Branch Refresh 2025` | Which deployment program |
| Phase / Status / Target date | `Phase 2` / `Complete` / `2025-Q2` | Rollout tracking |

---

## Integrations with Other Systems

NetData doesn't exist in isolation — it actively integrates with:

| System | Direction | What flows |
|---|---|---|
| **ServiceNow CMDB** | NetData → SNOW | Device records, vendor/model validation against CMDB hardware table |
| **CBRE MyData** | MyData → NetData | Property/facility data, site information |
| **HPNA** (HP Network Automation) | HPNA → NetData | Network automation data. Recently migrated to cloud: `https://hpnaprod.crbgf.net` |
| **Meraki Dashboard** | Meraki → NetData | Meraki device data, firmware, licensing |
| **Palo Alto Panorama** | Panorama → NetData | PAN-OS firewall data |
| **LDAP (CRBG)** | LDAP → NetData | User authentication |

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

## Screenshots Still Needed

These would help complete the documentation and plan future Nautobot imports:

1. **A single device detail page** — click a hostname in Device Inventory to see all 7 sections (Device Details, Location, Meraki, ServiceNow, Lifecycle, Circuits, Site Planning)
2. **Circuit Inventory view** — the circuit list showing carriers, circuit IDs, types, bandwidth
3. **Subnet Inventory view** — how subnets/prefixes are displayed with zones
4. **BGP Inventory view** — BGP peering table with ASNs and peer IPs
5. **Chassis Inventory view** — hardware purchase records with serials and dates
6. **Site Inventory list view** — the full site list (not a single site detail)
7. **A Reports page** (e.g., Netops OS Upgrade or Network Exceptions) — to understand report format
8. **Resources menu** — haven't seen what's in this dropdown yet
