"""
ConnectWise Manage API client for the Lexcom Sales Agent.
Thin async wrapper — mirrors auth pattern from jryan5150/cw-mcp-server.

This is a focused client for sales workflows, not a full CW SDK.
The 73-tool CW MCP server handles direct CW operations.
"""

import base64

import httpx
from typing import Any


class CWClient:
    """
    Async ConnectWise Manage API client.

    Auth: Basic base64(companyId+publicKey:privateKey) + clientId header.
    Base URL example: https://portal.lexcom.ca/v4_6_release/apis/3.0
    """

    def __init__(
        self,
        site_url: str,
        company_id: str,
        public_key: str,
        private_key: str,
        client_id: str,
    ):
        auth_raw = f"{company_id}+{public_key}:{private_key}"
        auth_b64 = base64.b64encode(auth_raw.encode()).decode()

        self.client = httpx.AsyncClient(
            base_url=site_url.rstrip("/"),
            headers={
                "Authorization": f"Basic {auth_b64}",
                "clientId": client_id,
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    async def _get(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        resp = await self.client.get(endpoint, params=params)
        resp.raise_for_status()
        if resp.status_code == 204:
            return {}
        return resp.json()

    async def _get_all(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        max_results: int = 1000,
    ) -> list:
        """Paginate through all results."""
        params = dict(params or {})
        page_size = int(params.pop("pageSize", 25))
        all_items: list = []
        page = 1

        while len(all_items) < max_results:
            result = await self._get(
                endpoint, {**params, "pageSize": page_size, "page": page}
            )
            if not isinstance(result, list):
                break
            all_items.extend(result)
            if len(result) < page_size:
                break
            page += 1

        return all_items[:max_results]

    # -----------------------------------------------------------------
    # Companies
    # -----------------------------------------------------------------

    async def get_company(self, company_id: int) -> dict:
        return await self._get(f"/company/companies/{company_id}")

    async def list_companies(
        self, conditions: str | None = None, page_size: int = 25
    ) -> list:
        params: dict[str, Any] = {"pageSize": page_size}
        if conditions:
            params["conditions"] = conditions
        return await self._get("/company/companies", params)

    async def get_company_notes(self, company_id: int) -> list:
        return await self._get(f"/company/companies/{company_id}/notes")

    # -----------------------------------------------------------------
    # Contacts
    # -----------------------------------------------------------------

    async def list_contacts(
        self, conditions: str | None = None, page_size: int = 25
    ) -> list:
        params: dict[str, Any] = {"pageSize": page_size}
        if conditions:
            params["conditions"] = conditions
        return await self._get("/company/contacts", params)

    # -----------------------------------------------------------------
    # Configurations (managed assets / devices)
    # -----------------------------------------------------------------

    async def list_configurations(
        self, conditions: str | None = None, page_size: int = 100
    ) -> list:
        params: dict[str, Any] = {"pageSize": page_size}
        if conditions:
            params["conditions"] = conditions
        return await self._get("/company/configurations", params)

    # -----------------------------------------------------------------
    # Agreements
    # -----------------------------------------------------------------

    async def list_agreements(
        self, conditions: str | None = None, page_size: int = 50
    ) -> list:
        params: dict[str, Any] = {"pageSize": page_size}
        if conditions:
            params["conditions"] = conditions
        return await self._get("/finance/agreements", params)

    async def get_agreement(self, agreement_id: int) -> dict:
        return await self._get(f"/finance/agreements/{agreement_id}")

    async def list_agreement_additions(self, agreement_id: int) -> list:
        return await self._get(f"/finance/agreements/{agreement_id}/additions")

    # -----------------------------------------------------------------
    # Opportunities
    # -----------------------------------------------------------------

    async def list_opportunities(
        self, conditions: str | None = None, page_size: int = 25
    ) -> list:
        params: dict[str, Any] = {"pageSize": page_size}
        if conditions:
            params["conditions"] = conditions
        return await self._get("/sales/opportunities", params)

    async def get_opportunity(self, opportunity_id: int) -> dict:
        return await self._get(f"/sales/opportunities/{opportunity_id}")

    # -----------------------------------------------------------------
    # Tickets (recent support context for sales)
    # -----------------------------------------------------------------

    async def list_tickets(
        self,
        conditions: str | None = None,
        order_by: str | None = None,
        page_size: int = 25,
    ) -> list:
        params: dict[str, Any] = {"pageSize": page_size}
        if conditions:
            params["conditions"] = conditions
        if order_by:
            params["orderBy"] = order_by
        return await self._get("/service/tickets", params)

    # -----------------------------------------------------------------
    # Procurement / Catalog
    # -----------------------------------------------------------------

    async def list_catalog_items(
        self, conditions: str | None = None, page_size: int = 25
    ) -> list:
        params: dict[str, Any] = {"pageSize": page_size}
        if conditions:
            params["conditions"] = conditions
        return await self._get("/procurement/catalog", params)

    # -----------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------

    async def close(self):
        await self.client.aclose()
