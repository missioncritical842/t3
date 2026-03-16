# NetBrain MCP Server

MCP (Model Context Protocol) server that exposes NetBrain network management operations as tools for Claude Desktop, Claude Code, or any MCP-compatible client.

## Setup

```bash
# Install dependencies
uv venv && uv pip install -r requirements.txt

# Or with pip
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your credentials.

## Running

```bash
# stdio transport (for Claude Desktop / Claude Code)
uv run server.py

# HTTP transport (for remote clients)
uv run server.py --http
```

## Claude Code Configuration

Add to `~/.claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "netbrain": {
      "command": "/home/jea7587/t3/.venv/bin/python",
      "args": ["/home/jea7587/t3/server.py"],
      "env": {
        "NETBRAIN_HOST": "https://netbrain.crbgf.net",
        "NETBRAIN_USERNAME": "admin"
      }
    }
  }
}
```

## Available Tools

| Tool | Description |
|------|-------------|
| `netbrain_login` | Authenticate and start a session |
| `netbrain_logout` | End the current session |
| `netbrain_get_version` | Get NetBrain product version |
| `netbrain_list_tenants` | List accessible tenants |
| `netbrain_list_domains` | List domains for a tenant |
| `netbrain_set_domain` | Set working domain |
| `netbrain_search_devices` | Search/list devices |
| `netbrain_get_device_attributes` | Get device details |
| `netbrain_get_device_config` | Get device running config |
| `netbrain_get_interfaces` | List device interfaces |
| `netbrain_get_interface_attributes` | Get interface details |
| `netbrain_calculate_path` | Calculate network path between IPs |
| `netbrain_get_path_result` | Get path calculation result |
| `netbrain_list_sites` | List all sites |
| `netbrain_get_site_devices` | List devices in a site |
| `netbrain_search` | Global search across NetBrain |
