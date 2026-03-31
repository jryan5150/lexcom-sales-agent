# Lexcom Sales Agent

Inside sales intelligence for Lexcom Systems Group — bridges ConnectWise (PSA) and TD Synnex StreamOne (distributor) into composite sales workflows via MCP.

## Components

### 1. Sales Agent (`sales_agent/`)

MCP server with 6 composite tools for sales workflows:

| Tool | Description |
|------|-------------|
| `customer_profile` | Aggregates CW company + agreements + configs + tickets + TD Synnex subs |
| `suggest_upsells` | Analyzes stack gaps, suggests products from TD Synnex catalog |
| `price_comparison` | TD Synnex cost vs CW sell price — margin per product |
| `build_quote` | Creates TD Synnex cart as draft quote |
| `renewal_radar` | Upcoming CW agreement + TD Synnex subscription expirations |
| `opportunity_enrichment` | Enriches CW opportunity with customer context + catalog matches |

### 2. TD Synnex StreamOne Adapter (`tdsynnex/`)

Full StreamOne Ion V3 API client + 15-tool MCP server for direct distributor operations.

**API Coverage**: Auth (OAuth2 with token rotation), Customers, Catalog, Orders, Subscriptions, Carts, Provisioning.

## Setup

```bash
# Python 3.10+ required
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure credentials
cp .env.example .env
# Fill in CW + TD Synnex credentials
```

## Running

### Sales Agent MCP Server

```bash
python -m sales_agent.mcp.server
```

### TD Synnex MCP Server

```bash
python -m tdsynnex.mcp.server
```

### Claude Code Integration

Add to your `.mcp.json`:

```json
{
  "mcpServers": {
    "lexcom-sales": {
      "command": "python",
      "args": ["-m", "sales_agent.mcp.server"],
      "cwd": "/path/to/lexcom-edge",
      "env": {
        "CW_SITE_URL": "https://portal.lexcom.ca/v4_6_release/apis/3.0",
        "CW_COMPANY_ID": "Lexcom",
        "CW_PUBLIC_KEY": "...",
        "CW_PRIVATE_KEY": "...",
        "CW_CLIENT_ID": "...",
        "TDSYNNEX_HOSTNAME": "...",
        "TDSYNNEX_ACCOUNT_ID": "...",
        "TDSYNNEX_REFRESH_TOKEN": "..."
      }
    },
    "tdsynnex": {
      "command": "python",
      "args": ["-m", "tdsynnex.mcp.server"],
      "cwd": "/path/to/lexcom-edge",
      "env": {
        "TDSYNNEX_HOSTNAME": "...",
        "TDSYNNEX_ACCOUNT_ID": "...",
        "TDSYNNEX_REFRESH_TOKEN": "..."
      }
    }
  }
}
```

## Stack

- Python 3.10+
- httpx (async HTTP)
- pydantic / pydantic-settings (config)
- MCP Python SDK (tool serving)
- Ollama (future — AI-powered product matching)
