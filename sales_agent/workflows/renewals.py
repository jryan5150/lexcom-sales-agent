"""
Renewal tracking — upcoming CW agreement expirations
+ TD Synnex subscription renewals in a single view.
"""

from datetime import datetime, timedelta
from typing import Any

from sales_agent.clients.connectwise import CWClient
from tdsynnex.client.streamone import TDSynnexClient


async def renewal_radar(
    cw: CWClient,
    tdsynnex: TDSynnexClient,
    days_ahead: int = 90,
    company_id: int | None = None,
) -> dict[str, Any]:
    """
    Find all upcoming renewals across CW agreements and TD Synnex subscriptions.

    Returns renewals sorted by date, with company context.
    Perfect for proactive outreach before contracts expire.
    """
    today = datetime.utcnow().strftime("%Y-%m-%dT00:00:00Z")
    cutoff = (datetime.utcnow() + timedelta(days=days_ahead)).strftime(
        "%Y-%m-%dT00:00:00Z"
    )

    # --- CW agreements expiring within window ---
    conditions = f"endDate>[{today}] and endDate<[{cutoff}]"
    if company_id:
        conditions += f" and company/id={company_id}"

    cw_agreements = await cw.list_agreements(conditions=conditions, page_size=100)

    cw_renewals = [
        {
            "source": "connectwise",
            "type": "agreement",
            "id": a.get("id"),
            "name": a.get("name", ""),
            "company": a.get("company", {}).get("name", "Unknown"),
            "company_id": a.get("company", {}).get("id"),
            "end_date": a.get("endDate", ""),
            "agreement_type": a.get("type", {}).get("name", ""),
        }
        for a in cw_agreements
    ]

    # --- TD Synnex subscriptions renewing within window ---
    tdsynnex_renewals: list[dict[str, Any]] = []
    try:
        subscriptions = await tdsynnex.list_subscriptions()
        if isinstance(subscriptions, list):
            for sub in subscriptions:
                renewal_date = sub.get(
                    "renewalDate", sub.get("endDate", "")
                )
                if renewal_date and today <= renewal_date <= cutoff:
                    tdsynnex_renewals.append(
                        {
                            "source": "tdsynnex",
                            "type": "subscription",
                            "id": sub.get("id", sub.get("subscriptionId", "")),
                            "name": sub.get(
                                "productName", sub.get("name", "")
                            ),
                            "customer": sub.get("customerName", ""),
                            "renewal_date": renewal_date,
                            "quantity": sub.get("quantity", 0),
                            "status": sub.get("status", ""),
                        }
                    )
    except Exception:
        pass

    # Merge and sort by date
    all_renewals = cw_renewals + tdsynnex_renewals
    all_renewals.sort(
        key=lambda r: r.get("end_date", r.get("renewal_date", "9999"))
    )

    return {
        "window_days": days_ahead,
        "renewals": all_renewals,
        "summary": {
            "cw_agreements_expiring": len(cw_renewals),
            "tdsynnex_subscriptions_renewing": len(tdsynnex_renewals),
            "total": len(all_renewals),
        },
    }
