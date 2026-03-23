# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NetBrain-to-Nautobot integration for Corebridge. Two main components:
1. **MCP servers** (`nautobot_server.py` is active, `server.py` for NetBrain is built but cannot connect — see below)
2. **Nautobot jobs** (`jobs/`) — import, rollup, diagnostic, and maintenance jobs that run inside Nautobot

The repo is registered as a **Nautobot Git data source** at `https://netbrain.crbg.nautobot.cloud`. Jobs sync automatically when the repo is synced in Nautobot.

### Network Topology — Critical
- **NetBrain** (10.134.98.133) is on a private network, accessible **only from Nautobot Cloud** via VPN tunnel
- **NetBrain is NOT accessible from WSL/Claude Code** — all NetBrain API calls must go through Nautobot jobs
- **Nautobot Cloud** (`netbrain.crbg.nautobot.cloud`) is accessible from Claude Code via REST API and MCP
- To interact with NetBrain: write a Nautobot job, push to GitHub, sync the repo in Nautobot, run the job
- The NetBrain MCP server (`server.py`) was built but cannot be used until VPN access is available from the dev environment

## Key Architecture

### Two-Phase Import Pattern (Joshua's Pattern)
- **Phase 1 — Import:** `NetBrainImportDemo.py` creates devices with minimal identity fields (name, serial, model, role, status, placeholder location) and stores the **full raw NetBrain API response** in `observations["netbrain"]["data"]["remote"]` custom field
- **Phase 2 — Rollup:** `NetBrainDeviceRollup.py` reads stored observations (no NetBrain API calls) and populates management IPs, location hierarchies, and tags

### Faker System (`netbrain_utils.py`)
- Controlled by `NAUTOBOT_FAKER` env var (any non-empty value = ON)
- **Deterministic:** same real value always produces same fake value via MD5 seeding — preserves relational integrity across imports
- **Identical algorithm to Joshua's `netdata_utils.py`** — same word lists, same MD5 seed, same output format. A device seen by both Meraki and NetBrain gets the same faked identity
- Import Demo job has faker **hardcoded ON** (`faker_on = True`)
- Key fakers: `_fake_hostname` (adj-noun-hex4), `_fake_ip_cidr` (XOR with MD5), `_fake_serial` (SN-hex12), `_fake_mac`, `_fake_address`
- Safe fields kept real: vendor, model, subTypeName, driverName, ver, os, all boolean flags

### Credential Loading (priority order)
1. Job UI form field (if filled)
2. Environment variable (`NETBRAIN_PASSWORD`, `NETBRAIN_CLIENT_ID`, `NETBRAIN_CLIENT_SECRET`)
3. Nautobot ConfigContext named "NetBrain Credentials"

### Nautobot Job Registration
- Root `__init__.py` **must exist** (empty) for Nautobot to treat repo as Python package
- `jobs/__init__.py` must exist (empty) — individual job files call `register_jobs()` at bottom
- Job `run()` uses positional args with defaults + `**kwargs` (not keyword-only `*`)
- `has_sensitive_variables = True` on jobs with credentials
- `commit_default = False` on all jobs

## NetBrain API Notes (R12.3)
- **Domain must be set with UUIDs:** `PUT /Session/CurrentDomain` requires `tenantId`/`domainId` (not names)
- **Pagination:** `limit` must be 10-100, use `skip` parameter
- **Inventory layout:** First ~7k are AWS, then End Systems, then Azure VMs, then real network devices start at ~18k-20k
- **No documented rate limits** but connection refused after ~50 rapid login/logout cycles. Use 0.1-0.3s delays between attribute fetches
- **Always logout** — sessions consume licensed seats
- **Site queries:** `GET /CMDB/Sites/ChildSites?sitePath=...` (not POST)
- **Interface attributes:** Response wraps as `{intf_name: {actual_attrs}}` — unwrap the single key

## Running Jobs

### Via API
```bash
source .env
# Sync repo
curl -s -X POST "https://netbrain.crbg.nautobot.cloud/api/extras/git-repositories/4f9a29b8/sync/" \
  -H "Authorization: Token $NAUTOBOT_TOKEN" -H "Content-Type: application/json" -d '{}'

# Run a job
curl -s -X POST "https://netbrain.crbg.nautobot.cloud/api/extras/jobs/$JOB_ID/run/" \
  -H "Authorization: Token $NAUTOBOT_TOKEN" -H "Content-Type: application/json" \
  -d '{"data": {"dry_run": false, ...}}'

# Check result
curl -s "https://netbrain.crbg.nautobot.cloud/api/extras/job-results/$RESULT_ID/logs/" \
  -H "Authorization: Token $NAUTOBOT_TOKEN"
```

### Via Nautobot UI
Extensibility → Jobs → select job → fill credentials → Run. Leave credential fields blank if ConfigContext "NetBrain Credentials" is configured.

### MCP Servers
```bash
# NetBrain MCP server
uv run server.py

# Nautobot MCP server (configured in .mcp.json for Claude Code)
uv run nautobot_server.py
```

## Target Device Types
The import filters to these NetBrain `subTypeName` values (~1,042 devices):
Router, L3 Switch (Cisco IOS/Nexus/ACI Spine, Arista, Aruba, Meraki), Firewall (Palo Alto, Meraki), F5 Load Balancer, SilverPeak WAN Optimizer, Cisco WLC, WAPs (Meraki AP, Aruba IAP, LWAP), IP Phone, Unclassified Device, Cisco ISE, Meraki Controller/Z-Series Gateway

Skipped: ~24,000 AWS objects, Azure VMs, ACI End Systems

## Job Quick Reference

| Job | Purpose | Speed |
|-----|---------|-------|
| `NetBrainSingleImport` | Import one device by hostname | ~5 seconds |
| `NetBrainImportDemo` | Import all ~1,042 network devices | ~15 minutes |
| `NetBrainDeviceRollup` | Populate IPs/locations/tags from observations | ~2 minutes |
| `NetBrainConnectivityTest` | Test NetBrain auth + API reachability | ~5 seconds |
| `NautobotDataWipe` | Delete all Nautobot data (requires typing "WIPE") | ~2 minutes |
| `NetBrainFieldDiscovery` | Dump raw field structures from sample devices | ~3 minutes |
| `NetBrainDiagnostic` | Troubleshoot inventory visibility | ~2 minutes |
| `NetBrainDeepDive` | Exhaustive device type scan | ~5 minutes |
| `NetBrainDeviceSync` | Legacy one-shot sync (import+normalize) | ~30 minutes |

## Wipe Job Gotchas
- Locations referenced by Controllers (protected FK) cannot be deleted — wipe skips them
- Wave limit capped at 10 to prevent infinite loops
- If wipe runs concurrently with import, it deletes Placeholder Site causing race condition — run sequentially
