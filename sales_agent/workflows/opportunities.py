"""
Opportunity enrichment and upsell suggestion workflows.

opportunity_enrichment: Enrich a CW opportunity with customer context + TD Synnex product matches.
suggest_upsells: Analyze current stack and suggest gaps from TD Synnex catalog.
"""

from typing import Any

from sales_agent.clients.connectwise import CWClient
from tdsynnex.client.streamone import TDSynnexClient


async def opportunity_enrichment(
    cw: CWClient,
    tdsynnex: TDSynnexClient,
    opportunity_id: int,
) -> dict[str, Any]:
    """
    Enrich a CW opportunity with customer context and TD Synnex product matches.

    Pulls opportunity details, grabs the company's current stack,
    then searches the TD Synnex catalog for relevant products.
    """
    opportunity = await cw.get_opportunity(opportunity_id)

    company_id = opportunity.get("company", {}).get("id")
    company: dict = {}
    configurations: list = []
    agreements: list = []

    if company_id:
        company = await cw.get_company(company_id)
        configurations = await cw.list_configurations(
            conditions=f"company/id={company_id}", page_size=50
        )
        agreements = await cw.list_agreements(
            conditions=f"company/id={company_id}", page_size=50
        )

    # Extract keywords from opportunity for catalog search
    opp_name = opportunity.get("name", "")
    opp_notes = opportunity.get("notes", "")
    search_terms = _extract_search_terms(opp_name, opp_notes)

    catalog_matches: list = []
    for term in search_terms[:3]:
        try:
            products = await tdsynnex.list_products(keyword=term, pageSize=10)
            if isinstance(products, list):
                catalog_matches.extend(products)
        except Exception:
            pass

    # Deduplicate by product ID
    seen: set[str] = set()
    unique_matches = []
    for product in catalog_matches:
        pid = str(product.get("id", product.get("productId", "")))
        if pid and pid not in seen:
            seen.add(pid)
            unique_matches.append(product)

    return {
        "opportunity": opportunity,
        "company": company,
        "current_stack": {
            "configurations": configurations,
            "agreements": agreements,
        },
        "catalog_matches": unique_matches[:20],
        "search_terms_used": search_terms,
    }


async def suggest_upsells(
    cw: CWClient,
    tdsynnex: TDSynnexClient,
    company_id: int,
    tdsynnex_customer_id: str | None = None,
) -> dict[str, Any]:
    """
    Analyze a customer's current stack and suggest upsell opportunities.

    Compares CW configurations/agreements against TD Synnex catalog
    to find gaps in backup, security, productivity, and networking.
    """
    configurations = await cw.list_configurations(
        conditions=f"company/id={company_id}", page_size=100
    )
    agreements = await cw.list_agreements(
        conditions=f"company/id={company_id}", page_size=50
    )

    current_subs: list = []
    if tdsynnex_customer_id:
        try:
            result = await tdsynnex.list_subscriptions(
                customerId=tdsynnex_customer_id
            )
            current_subs = result if isinstance(result, list) else []
        except Exception:
            pass

    # Build current stack profile by config type
    config_types: dict[str, list[str]] = {}
    for config in configurations:
        type_name = config.get("type", {}).get("name", "Other")
        config_types.setdefault(type_name, []).append(
            config.get("name", "Unknown")
        )

    # Identify upsell searches based on stack gaps
    upsell_searches = _identify_upsell_searches(
        config_types, agreements, current_subs
    )

    suggestions = []
    for search in upsell_searches:
        try:
            products = await tdsynnex.list_products(
                keyword=search["keyword"], pageSize=5
            )
            if isinstance(products, list) and products:
                suggestions.append(
                    {
                        "reason": search["reason"],
                        "category": search["category"],
                        "products": products[:3],
                    }
                )
        except Exception:
            pass

    return {
        "company_id": company_id,
        "current_stack": config_types,
        "agreement_count": len(agreements),
        "subscription_count": len(current_subs),
        "suggestions": suggestions,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_search_terms(name: str, notes: str) -> list[str]:
    """Extract meaningful search terms from opportunity text."""
    text = f"{name} {notes}".lower()

    keywords = [
        "microsoft 365",
        "m365",
        "office 365",
        "azure",
        "google workspace",
        "backup",
        "security",
        "firewall",
        "switch",
        "access point",
        "wifi",
        "server",
        "workstation",
        "laptop",
        "desktop",
        "monitor",
        "antivirus",
        "endpoint",
        "email",
        "voip",
        "phone",
        "license",
        "subscription",
        "cloud",
        "storage",
    ]

    found = [kw for kw in keywords if kw in text]

    # Fall back to splitting the opportunity name
    name_words = [
        w
        for w in name.split()
        if len(w) > 3 and w.lower() not in {"the", "for", "and", "with"}
    ]
    if name_words:
        found.append(" ".join(name_words[:3]))

    return found if found else [name.split()[0]] if name.split() else ["microsoft"]


def _identify_upsell_searches(
    config_types: dict[str, list[str]],
    agreements: list,
    current_subs: list,
) -> list[dict[str, str]]:
    """Identify upsell opportunities based on current stack gaps."""
    searches: list[dict[str, str]] = []
    type_names = {t.lower() for t in config_types}

    # Endpoints without backup
    if any(
        kw in t for t in type_names for kw in ("workstation", "desktop", "laptop")
    ):
        searches.append(
            {
                "keyword": "backup",
                "category": "Data Protection",
                "reason": "Endpoints detected — no backup solution visible in stack",
            }
        )

    # Servers without advanced security
    if any("server" in t for t in type_names):
        searches.append(
            {
                "keyword": "endpoint security",
                "category": "Security",
                "reason": "Servers in environment — verify advanced threat protection",
            }
        )

    # Networking gear — refresh cycle
    if any(
        kw in t
        for t in type_names
        for kw in ("switch", "router", "firewall", "access point")
    ):
        searches.append(
            {
                "keyword": "network switch",
                "category": "Networking",
                "reason": "Network infrastructure present — check for refresh cycle",
            }
        )

    # M365 gap
    sub_names = " ".join(s.get("productName", "") for s in current_subs).lower()
    if "365" not in sub_names and "microsoft" not in sub_names:
        searches.append(
            {
                "keyword": "microsoft 365 business",
                "category": "Productivity",
                "reason": "No Microsoft 365 subscription detected",
            }
        )

    # Always suggest security assessments — high-margin recurring
    searches.append(
        {
            "keyword": "security assessment",
            "category": "Security",
            "reason": "Security assessments are high-margin recurring revenue",
        }
    )

    return searches
