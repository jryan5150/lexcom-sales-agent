"""
Lexcom Sales Agent MCP Server.

Composite sales tools that orchestrate ConnectWise + TD Synnex data.
Run standalone or integrate into Claude Code sessions.

Usage:
    python -m sales_agent.mcp.server

Or via Claude Code (.mcp.json):
    {
        "mcpServers": {
            "lexcom-sales": {
                "command": "python",
                "args": ["-m", "sales_agent.mcp.server"],
                "cwd": "/path/to/lexcom-edge"
            }
        }
    }
"""

import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from sales_agent.clients.connectwise import CWClient
from sales_agent.config.settings import Settings
from sales_agent.workflows.customer import customer_profile
from sales_agent.workflows.quoting import build_quote, price_comparison
from sales_agent.workflows.renewals import renewal_radar
from sales_agent.workflows.opportunities import opportunity_enrichment, suggest_upsells
from tdsynnex.client.streamone import TDSynnexClient


# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------

server = Server("lexcom-sales-agent")

_cw: CWClient | None = None
_tdsynnex: TDSynnexClient | None = None


def get_clients() -> tuple[CWClient, TDSynnexClient]:
    global _cw, _tdsynnex

    if _cw is None or _tdsynnex is None:
        settings = Settings()
        _cw = CWClient(
            site_url=settings.cw_site_url,
            company_id=settings.cw_company_id,
            public_key=settings.cw_public_key,
            private_key=settings.cw_private_key,
            client_id=settings.cw_client_id,
        )
        _tdsynnex = TDSynnexClient(
            hostname=settings.tdsynnex_hostname,
            account_id=settings.tdsynnex_account_id,
            refresh_token=settings.tdsynnex_refresh_token,
        )

    return _cw, _tdsynnex


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS = [
    Tool(
        name="customer_profile",
        description=(
            "Build a complete customer profile for sales context. "
            "Aggregates CW company data, contacts, agreements (with line-item additions), "
            "configurations (managed assets), recent support tickets, and TD Synnex subscriptions "
            "into a single view. Use this before any sales conversation."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "company_id": {
                    "type": "integer",
                    "description": "ConnectWise company ID",
                },
                "tdsynnex_customer_id": {
                    "type": "string",
                    "description": "TD Synnex customer ID (optional — include for subscription data)",
                },
            },
            "required": ["company_id"],
        },
    ),
    Tool(
        name="suggest_upsells",
        description=(
            "Analyze a customer's current stack (CW configurations, agreements, "
            "TD Synnex subscriptions) and suggest upsell opportunities from the "
            "TD Synnex catalog. Identifies gaps in backup, security, productivity, "
            "and networking based on what's already deployed."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "company_id": {
                    "type": "integer",
                    "description": "ConnectWise company ID",
                },
                "tdsynnex_customer_id": {
                    "type": "string",
                    "description": "TD Synnex customer ID (optional — enriches with subscription data)",
                },
            },
            "required": ["company_id"],
        },
    ),
    Tool(
        name="price_comparison",
        description=(
            "Compare TD Synnex distributor cost against CW catalog sell prices. "
            "Shows cost, MSRP, sell price, margin, and margin percentage per product. "
            "Use before quoting to verify margins."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "product_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "TD Synnex product IDs to price",
                },
                "cw_catalog_conditions": {
                    "type": "string",
                    "description": "CW conditions to find matching catalog items for margin comparison (optional)",
                },
            },
            "required": ["product_ids"],
        },
    ),
    Tool(
        name="build_quote",
        description=(
            "Create a draft quote by building a TD Synnex cart with products. "
            "Returns the cart with pricing for review — does NOT finalize the order. "
            "Use the TD Synnex checkout_cart tool separately to submit."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "string",
                    "description": "TD Synnex customer ID",
                },
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "product_id": {"type": "string"},
                            "quantity": {"type": "integer", "default": 1},
                        },
                        "required": ["product_id"],
                    },
                    "description": "Products to include in the quote",
                },
                "cart_name": {
                    "type": "string",
                    "description": "Name for the quote/cart",
                    "default": "Sales Agent Quote",
                },
            },
            "required": ["customer_id", "items"],
        },
    ),
    Tool(
        name="renewal_radar",
        description=(
            "Find all upcoming renewals across CW agreements and TD Synnex subscriptions. "
            "Returns renewals sorted by date within the specified window. "
            "Use for proactive outreach before contracts expire."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "days_ahead": {
                    "type": "integer",
                    "description": "How many days ahead to look (default: 90)",
                    "default": 90,
                },
                "company_id": {
                    "type": "integer",
                    "description": "Filter to a specific CW company (optional)",
                },
            },
        },
    ),
    Tool(
        name="opportunity_enrichment",
        description=(
            "Enrich a CW sales opportunity with customer context and TD Synnex product matches. "
            "Pulls the opportunity, gets the company's current stack (configs + agreements), "
            "and searches the TD Synnex catalog for relevant products to attach."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "opportunity_id": {
                    "type": "integer",
                    "description": "ConnectWise opportunity ID",
                },
            },
            "required": ["opportunity_id"],
        },
    ),
]


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------


@server.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    cw, tdsynnex = get_clients()

    try:
        match name:
            case "customer_profile":
                result = await customer_profile(
                    cw,
                    tdsynnex,
                    company_id=arguments["company_id"],
                    tdsynnex_customer_id=arguments.get("tdsynnex_customer_id"),
                )
            case "suggest_upsells":
                result = await suggest_upsells(
                    cw,
                    tdsynnex,
                    company_id=arguments["company_id"],
                    tdsynnex_customer_id=arguments.get("tdsynnex_customer_id"),
                )
            case "price_comparison":
                result = await price_comparison(
                    cw,
                    tdsynnex,
                    product_ids=arguments["product_ids"],
                    cw_catalog_conditions=arguments.get("cw_catalog_conditions"),
                )
            case "build_quote":
                result = await build_quote(
                    tdsynnex,
                    customer_id=arguments["customer_id"],
                    items=arguments["items"],
                    cart_name=arguments.get("cart_name", "Sales Agent Quote"),
                )
            case "renewal_radar":
                result = await renewal_radar(
                    cw,
                    tdsynnex,
                    days_ahead=arguments.get("days_ahead", 90),
                    company_id=arguments.get("company_id"),
                )
            case "opportunity_enrichment":
                result = await opportunity_enrichment(
                    cw,
                    tdsynnex,
                    opportunity_id=arguments["opportunity_id"],
                )
            case _:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

        return [
            TextContent(
                type="text",
                text=json.dumps(result, indent=2, default=str),
            )
        ]

    except Exception as e:
        return [TextContent(type="text", text=f"Error in {name}: {e}")]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
