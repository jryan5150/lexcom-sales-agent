"""
Quote building and price comparison workflows.

build_quote: Creates a TD Synnex cart as a draft quote.
price_comparison: Compares distributor cost vs CW sell price for margin analysis.
"""

from typing import Any

from sales_agent.clients.connectwise import CWClient
from tdsynnex.client.streamone import TDSynnexClient


async def price_comparison(
    cw: CWClient,
    tdsynnex: TDSynnexClient,
    product_ids: list[str],
    cw_catalog_conditions: str | None = None,
) -> dict[str, Any]:
    """
    Compare TD Synnex distributor cost against CW catalog sell prices.

    Returns cost, MSRP, sell price, margin, and margin % for each product.
    """
    tdsynnex_pricing = await tdsynnex.get_product_pricing(
        {"productIds": product_ids}
    )

    # Get CW catalog items for comparison if conditions provided
    cw_catalog: list = []
    if cw_catalog_conditions:
        cw_catalog = await cw.list_catalog_items(conditions=cw_catalog_conditions)

    items = tdsynnex_pricing if isinstance(tdsynnex_pricing, list) else [tdsynnex_pricing]
    comparison = []

    for product in items:
        entry: dict[str, Any] = {
            "product_id": product.get("productId", ""),
            "name": product.get("productName", ""),
            "tdsynnex_cost": product.get("resellerPrice", product.get("cost", 0)),
            "msrp": product.get("msrp", product.get("listPrice", 0)),
        }

        # Attempt fuzzy match against CW catalog
        for cw_item in cw_catalog:
            cw_desc = cw_item.get("description", "").lower()
            cw_ident = cw_item.get("identifier", "").lower()
            product_name = entry["name"].lower()

            if cw_ident in product_name or product_name in cw_desc:
                sell = cw_item.get("price", 0)
                cost = entry["tdsynnex_cost"]
                entry["cw_sell_price"] = sell
                entry["margin"] = sell - cost
                entry["margin_pct"] = round(
                    (sell - cost) / sell * 100, 1
                ) if sell > 0 else 0
                entry["cw_catalog_match"] = cw_item.get("identifier", "")
                break

        comparison.append(entry)

    return {
        "products": comparison,
        "totals": {
            "cost": sum(p.get("tdsynnex_cost", 0) for p in comparison),
            "msrp": sum(p.get("msrp", 0) for p in comparison),
        },
    }


async def build_quote(
    tdsynnex: TDSynnexClient,
    customer_id: str,
    items: list[dict],
    cart_name: str = "Sales Agent Quote",
) -> dict[str, Any]:
    """
    Build a draft quote by creating a TD Synnex cart with products.

    Does NOT checkout — returns the cart with pricing for review.
    Use the TD Synnex checkout_cart tool to finalize.

    Args:
        customer_id: TD Synnex customer ID.
        items: [{"product_id": "...", "quantity": 1}, ...]
        cart_name: Display name for the cart.
    """
    cart = await tdsynnex.create_cart(customer_id, {"name": cart_name})
    cart_id = cart.get("id", cart.get("cartId", ""))

    added_items = []
    for item in items:
        result = await tdsynnex.create_cart_item(
            customer_id,
            cart_id,
            {
                "productId": item["product_id"],
                "quantity": item.get("quantity", 1),
            },
        )
        added_items.append(result)

    full_cart = await tdsynnex.get_cart(customer_id, cart_id)

    return {
        "cart_id": cart_id,
        "customer_id": customer_id,
        "name": cart_name,
        "items": added_items,
        "cart": full_cart,
        "status": "draft",
        "next_step": "Review pricing, then use checkout_cart to finalize the order.",
    }
