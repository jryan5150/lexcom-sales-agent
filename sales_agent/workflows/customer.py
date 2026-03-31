"""
Customer profile aggregation.

Combines CW company data + agreements + configs + recent tickets
+ TD Synnex subscriptions into a single sales-ready view.
"""

from typing import Any

from sales_agent.clients.connectwise import CWClient
from tdsynnex.client.streamone import TDSynnexClient


async def customer_profile(
    cw: CWClient,
    tdsynnex: TDSynnexClient,
    company_id: int,
    tdsynnex_customer_id: str | None = None,
) -> dict[str, Any]:
    """
    Build a complete customer profile for sales context.

    Aggregates:
        - CW company details
        - Primary contacts
        - Active agreements with line-item additions
        - Managed configurations (assets/devices)
        - Last 10 tickets (support health signal)
        - TD Synnex subscriptions (if customer ID mapped)
    """
    company = await cw.get_company(company_id)

    contacts = await cw.list_contacts(
        conditions=f"company/id={company_id}",
        page_size=25,
    )

    agreements = await cw.list_agreements(
        conditions=f"company/id={company_id}",
        page_size=50,
    )

    # Enrich each agreement with its line-item additions
    for agreement in agreements:
        try:
            additions = await cw.list_agreement_additions(agreement["id"])
            agreement["_additions"] = additions
        except Exception:
            agreement["_additions"] = []

    configurations = await cw.list_configurations(
        conditions=f"company/id={company_id}",
        page_size=100,
    )

    recent_tickets = await cw.list_tickets(
        conditions=f"company/id={company_id}",
        order_by="dateEntered desc",
        page_size=10,
    )

    # TD Synnex subscriptions if customer is mapped
    subscriptions: list = []
    if tdsynnex_customer_id:
        try:
            subscriptions = await tdsynnex.list_subscriptions(
                customerId=tdsynnex_customer_id,
            )
            if not isinstance(subscriptions, list):
                subscriptions = []
        except Exception:
            subscriptions = []

    return {
        "company": company,
        "contacts": contacts,
        "agreements": agreements,
        "configurations": configurations,
        "recent_tickets": recent_tickets,
        "subscriptions": subscriptions,
        "summary": {
            "company_name": company.get("name", "Unknown"),
            "agreement_count": len(agreements),
            "config_count": len(configurations),
            "active_subscription_count": len(subscriptions),
            "recent_ticket_count": len(recent_tickets),
        },
    }
