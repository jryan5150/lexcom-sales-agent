"""
TD Synnex StreamOne Ion MCP Server.

Exposes the StreamOne Ion API as MCP tools for the inside sales bot.
Run standalone or integrate into Claude Code sessions.

Usage:
    python -m tdsynnex.mcp.server
    
Or via Claude Code:
    Add to .mcp.json as a stdio server.
"""

import asyncio
import json
import os
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from tdsynnex.client.streamone import TDSynnexClient


# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------

server = Server("tdsynnex-streamone")

_client: TDSynnexClient | None = None


def get_client() -> TDSynnexClient:
    global _client
    if _client is None:
        _client = TDSynnexClient(
            hostname=os.environ["TDSYNNEX_HOSTNAME"],
            account_id=os.environ["TDSYNNEX_ACCOUNT_ID"],
            refresh_token=os.environ["TDSYNNEX_REFRESH_TOKEN"],
        )
    return _client


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS = [
    Tool(
        name="list_customers",
        description="List all customers in the TD Synnex StreamOne account. Returns customer names, IDs, and status.",
        inputSchema={
            "type": "object",
            "properties": {
                "page": {"type": "integer", "description": "Page number", "default": 1},
                "page_size": {"type": "integer", "description": "Results per page", "default": 25},
            },
        },
    ),
    Tool(
        name="get_customer",
        description="Get detailed information about a specific customer by their ID.",
        inputSchema={
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "Customer ID"},
            },
            "required": ["customer_id"],
        },
    ),
    Tool(
        name="search_products",
        description="Search the TD Synnex product catalog. Filter by category, vendor, or keyword.",
        inputSchema={
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "Search keyword"},
                "category": {"type": "string", "description": "Product category filter"},
                "vendor": {"type": "string", "description": "Vendor name filter (e.g. microsoft, google)"},
                "page": {"type": "integer", "default": 1},
                "page_size": {"type": "integer", "default": 25},
            },
        },
    ),
    Tool(
        name="get_product",
        description="Get detailed product information including features, SKUs, and configuration options.",
        inputSchema={
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "Product ID"},
            },
            "required": ["product_id"],
        },
    ),
    Tool(
        name="get_product_pricing",
        description="Get pricing for one or more products. Returns MSRP, reseller cost, and margin.",
        inputSchema={
            "type": "object",
            "properties": {
                "product_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of product IDs to price",
                },
            },
            "required": ["product_ids"],
        },
    ),
    Tool(
        name="list_categories",
        description="List all product categories in the catalog.",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="list_verticals",
        description="List all industry verticals available for product filtering.",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="list_customer_orders",
        description="List all orders for a specific customer.",
        inputSchema={
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "Customer ID"},
            },
            "required": ["customer_id"],
        },
    ),
    Tool(
        name="get_order",
        description="Get detailed order information including line items and status.",
        inputSchema={
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "Customer ID"},
                "order_id": {"type": "string", "description": "Order ID"},
            },
            "required": ["customer_id", "order_id"],
        },
    ),
    Tool(
        name="list_customer_subscriptions",
        description="List all active subscriptions for a customer. Shows renewal dates, quantities, and status.",
        inputSchema={
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "Customer ID"},
            },
            "required": ["customer_id"],
        },
    ),
    Tool(
        name="get_subscription",
        description="Get detailed subscription info including usage, billing, and provisioning status.",
        inputSchema={
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "Customer ID"},
                "subscription_id": {"type": "string", "description": "Subscription ID"},
            },
            "required": ["customer_id", "subscription_id"],
        },
    ),
    Tool(
        name="create_cart",
        description="Create a new shopping cart for a customer to start building an order.",
        inputSchema={
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "Customer ID"},
                "name": {"type": "string", "description": "Cart name/description"},
            },
            "required": ["customer_id"],
        },
    ),
    Tool(
        name="add_to_cart",
        description="Add a product to an existing cart.",
        inputSchema={
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "Customer ID"},
                "cart_id": {"type": "string", "description": "Cart ID"},
                "product_id": {"type": "string", "description": "Product ID to add"},
                "quantity": {"type": "integer", "description": "Number of units", "default": 1},
            },
            "required": ["customer_id", "cart_id", "product_id"],
        },
    ),
    Tool(
        name="checkout_cart",
        description="Submit a cart as an order. This finalizes the purchase.",
        inputSchema={
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "Customer ID"},
                "cart_id": {"type": "string", "description": "Cart ID to checkout"},
            },
            "required": ["customer_id", "cart_id"],
        },
    ),
    Tool(
        name="get_provisioning_templates",
        description="Get provisioning templates for a vendor. Shows required fields for setting up services.",
        inputSchema={
            "type": "object",
            "properties": {
                "vendor": {"type": "string", "description": "Vendor (e.g. microsoft, google)"},
                "action": {"type": "string", "description": "Action type (create, update)", "default": "create"},
            },
            "required": ["vendor"],
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
    client = get_client()
    result: Any = None

    try:
        match name:
            # Customers
            case "list_customers":
                result = await client.list_customers(
                    page=arguments.get("page", 1),
                    pageSize=arguments.get("page_size", 25),
                )
            case "get_customer":
                result = await client.get_customer(arguments["customer_id"])

            # Catalog
            case "search_products":
                params = {}
                if arguments.get("keyword"):
                    params["keyword"] = arguments["keyword"]
                if arguments.get("category"):
                    params["category"] = arguments["category"]
                if arguments.get("vendor"):
                    params["vendor"] = arguments["vendor"]
                params["page"] = arguments.get("page", 1)
                params["pageSize"] = arguments.get("page_size", 25)
                result = await client.list_products(**params)
            case "get_product":
                result = await client.get_product(arguments["product_id"])
            case "get_product_pricing":
                result = await client.get_product_pricing({
                    "productIds": arguments["product_ids"],
                })
            case "list_categories":
                result = await client.list_categories()
            case "list_verticals":
                result = await client.list_verticals()

            # Orders
            case "list_customer_orders":
                result = await client.list_customer_orders(arguments["customer_id"])
            case "get_order":
                result = await client.get_order(
                    arguments["customer_id"],
                    arguments["order_id"],
                )

            # Subscriptions
            case "list_customer_subscriptions":
                result = await client.list_subscriptions(
                    customerId=arguments["customer_id"],
                )
            case "get_subscription":
                result = await client.get_subscription(
                    arguments["customer_id"],
                    arguments["subscription_id"],
                )

            # Carts
            case "create_cart":
                cart_data = {}
                if arguments.get("name"):
                    cart_data["name"] = arguments["name"]
                result = await client.create_cart(
                    arguments["customer_id"],
                    cart_data,
                )
            case "add_to_cart":
                result = await client.create_cart_item(
                    arguments["customer_id"],
                    arguments["cart_id"],
                    {
                        "productId": arguments["product_id"],
                        "quantity": arguments.get("quantity", 1),
                    },
                )
            case "checkout_cart":
                result = await client.checkout_cart(
                    arguments["customer_id"],
                    arguments["cart_id"],
                )

            # Provisioning
            case "get_provisioning_templates":
                result = await client.get_provisioning_templates(
                    vendor=arguments["vendor"],
                    action=arguments.get("action", "create"),
                )

            case _:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2, default=str),
        )]

    except Exception as e:
        return [TextContent(
            type="text",
            text=f"Error calling {name}: {str(e)}",
        )]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
