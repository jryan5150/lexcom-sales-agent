"""
TD Synnex StreamOne Ion V3 API Client.

Wraps the full StreamOne Ion API surface for the inside sales bot.
OAuth2 bearer auth with refresh token rotation.

API Docs: StreamOne Ion V3 API Reference Guide
Auth: OAuth2 — access token (7200s / 2hr), refresh token (32 days, single-use)
"""

import httpx
from datetime import datetime, timedelta
from typing import Any


class TDSynnexAuth:
    """Handles OAuth2 token lifecycle with automatic refresh."""

    def __init__(
        self,
        hostname: str,
        refresh_token: str,
    ):
        self.hostname = hostname
        self.base_url = f"https://{hostname}"
        self._access_token: str | None = None
        self._refresh_token: str = refresh_token
        self._expires_at: datetime | None = None

    async def get_token(self, client: httpx.AsyncClient) -> str:
        """Get a valid access token, refreshing if needed."""
        if self._access_token and self._expires_at and datetime.utcnow() < self._expires_at:
            return self._access_token

        resp = await client.post(
            f"{self.base_url}/oauth/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        data = resp.json()

        self._access_token = data["access_token"]
        # Refresh token is single-use — store the new one
        self._refresh_token = data["refresh_token"]
        self._expires_at = datetime.utcnow() + timedelta(seconds=data.get("expires_in", 7200) - 60)

        return self._access_token

    @property
    def current_refresh_token(self) -> str:
        """Current refresh token (save this — it rotates on each use)."""
        return self._refresh_token


class TDSynnexClient:
    """
    StreamOne Ion V3 API client.
    
    Covers: Customers, Catalog, Orders, Subscriptions, Carts, Provisioning.
    """

    def __init__(
        self,
        hostname: str,
        account_id: str,
        refresh_token: str,
    ):
        self.hostname = hostname
        self.account_id = account_id
        self.base_url = f"https://{hostname}/api/v3"
        self.auth = TDSynnexAuth(hostname, refresh_token)
        self.client = httpx.AsyncClient(timeout=30.0)

    async def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        json_body: dict | None = None,
    ) -> dict | list:
        """Authenticated request to StreamOne Ion API."""
        token = await self.auth.get_token(self.client)
        url = f"{self.base_url}{path}"

        resp = await self.client.request(
            method,
            url,
            params=params,
            json=json_body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Customers
    # ------------------------------------------------------------------

    async def list_customers(self, **params) -> list[dict]:
        return await self._request(
            "GET",
            f"/accounts/{self.account_id}/customers/",
            params=params,
        )

    async def get_customer(self, customer_id: str) -> dict:
        return await self._request(
            "GET",
            f"/accounts/{self.account_id}/customers/{customer_id}",
        )

    async def create_customer(self, customer_data: dict) -> dict:
        return await self._request(
            "POST",
            f"/accounts/{self.account_id}/customers",
            json_body=customer_data,
        )

    async def update_customer(self, customer_id: str, update_data: dict) -> dict:
        return await self._request(
            "PUT",
            f"/accounts/{self.account_id}/customers/{customer_id}/",
            json_body=update_data,
        )

    # ------------------------------------------------------------------
    # Catalog
    # ------------------------------------------------------------------

    async def list_products(self, **params) -> list[dict]:
        return await self._request(
            "GET",
            f"/accounts/{self.account_id}/products",
            params=params,
        )

    async def list_categories(self, **params) -> list[dict]:
        return await self._request(
            "GET",
            f"/accounts/{self.account_id}/products/categories",
            params=params,
        )

    async def list_verticals(self, **params) -> list[dict]:
        return await self._request(
            "GET",
            f"/accounts/{self.account_id}/products/verticals",
            params=params,
        )

    async def get_product(self, product_id: str) -> dict:
        return await self._request(
            "GET",
            f"/accounts/{self.account_id}/products/{product_id}",
        )

    async def get_product_pricing(self, pricing_request: dict) -> dict:
        return await self._request(
            "POST",
            f"/accounts/{self.account_id}/products/products:pricing",
            json_body=pricing_request,
        )

    async def enable_product(self, product_id: str) -> dict:
        return await self._request(
            "POST",
            f"/accounts/{self.account_id}/products/{product_id}:enable",
        )

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    async def get_order(self, customer_id: str, order_id: str) -> dict:
        return await self._request(
            "GET",
            f"/accounts/{self.account_id}/customers/{customer_id}/orders/{order_id}",
        )

    async def list_account_orders(self, **params) -> list[dict]:
        return await self._request(
            "GET",
            f"/accounts/{self.account_id}/orders",
            params=params,
        )

    async def list_customer_orders(self, customer_id: str, **params) -> list[dict]:
        return await self._request(
            "GET",
            f"/accounts/{self.account_id}/customers/{customer_id}/orders",
            params=params,
        )

    async def create_order(self, customer_id: str, order_data: dict) -> dict:
        return await self._request(
            "POST",
            f"/accounts/{self.account_id}/customers/{customer_id}/orders",
            json_body=order_data,
        )

    async def update_order(self, customer_id: str, order_id: str, update_data: dict) -> dict:
        return await self._request(
            "POST",  # API uses POST for update per docs
            f"/accounts/{self.account_id}/customers/{customer_id}/orders/{order_id}",
            json_body=update_data,
        )

    async def cancel_order(self, customer_id: str, order_id: str) -> dict:
        return await self._request(
            "POST",
            f"/accounts/{self.account_id}/customers/{customer_id}/orders/{order_id}:cancel",
        )

    # ------------------------------------------------------------------
    # Subscriptions
    # ------------------------------------------------------------------

    async def list_subscriptions(self, **params) -> list[dict]:
        return await self._request(
            "GET",
            f"/accounts/{self.account_id}/subscriptions",
            params=params,
        )

    async def get_subscription(self, customer_id: str, subscription_id: str) -> dict:
        return await self._request(
            "GET",
            f"/accounts/{self.account_id}/customers/{customer_id}/subscriptions/{subscription_id}",
        )

    # ------------------------------------------------------------------
    # Carts
    # ------------------------------------------------------------------

    async def list_carts(self, customer_id: str) -> list[dict]:
        return await self._request(
            "GET",
            f"/customers/{customer_id}/carts",
        )

    async def create_cart(self, customer_id: str, cart_data: dict) -> dict:
        return await self._request(
            "POST",
            f"/customers/{customer_id}/carts",
            json_body=cart_data,
        )

    async def get_cart(self, customer_id: str, cart_id: str) -> dict:
        return await self._request(
            "GET",
            f"/customers/{customer_id}/carts/{cart_id}",
        )

    async def update_cart(self, customer_id: str, cart_id: str, update_data: dict) -> dict:
        return await self._request(
            "PUT",
            f"/customers/{customer_id}/carts/{cart_id}",
            json_body=update_data,
        )

    async def delete_cart(self, customer_id: str, cart_id: str) -> dict:
        return await self._request(
            "DELETE",
            f"/customers/{customer_id}/carts/{cart_id}",
        )

    async def checkout_cart(self, customer_id: str, cart_id: str) -> dict:
        return await self._request(
            "POST",
            f"/customers/{customer_id}/carts/{cart_id}:checkout",
        )

    # ------------------------------------------------------------------
    # Cart Items
    # ------------------------------------------------------------------

    async def list_cart_items(self, customer_id: str, cart_id: str) -> list[dict]:
        return await self._request(
            "GET",
            f"/customers/{customer_id}/carts/{cart_id}/cartItems",
        )

    async def create_cart_item(self, customer_id: str, cart_id: str, item_data: dict) -> dict:
        return await self._request(
            "POST",
            f"/customers/{customer_id}/carts/{cart_id}/cartItems/",
            json_body=item_data,
        )

    async def get_cart_item(self, customer_id: str, cart_id: str, item_id: str) -> dict:
        return await self._request(
            "GET",
            f"/customers/{customer_id}/carts/{cart_id}/cartItems/{item_id}",
        )

    async def update_cart_item(
        self, customer_id: str, cart_id: str, item_id: str, update_data: dict,
    ) -> dict:
        return await self._request(
            "PUT",
            f"/customers/{customer_id}/carts/{cart_id}/cartItems/{item_id}",
            json_body=update_data,
        )

    async def delete_cart_item(self, customer_id: str, cart_id: str, item_id: str) -> dict:
        return await self._request(
            "DELETE",
            f"/customers/{customer_id}/carts/{cart_id}/cartItems/{item_id}",
        )

    # ------------------------------------------------------------------
    # Provisioning Templates
    # ------------------------------------------------------------------

    async def get_provisioning_templates(
        self, vendor: str | None = None, action: str | None = None,
    ) -> list[dict]:
        params = {}
        if vendor:
            params["vendor"] = vendor
        if action:
            params["action"] = action
        return await self._request(
            "GET",
            f"/accounts/{self.account_id}/provisionTemplates",
            params=params,
        )

    # ------------------------------------------------------------------
    # Cloud Provider linking (customer-level)
    # ------------------------------------------------------------------

    async def link_cloud_provider(
        self, customer_id: str, provider_id: str, link_data: dict,
    ) -> dict:
        return await self._request(
            "POST",
            f"/accounts/{self.account_id}/customers/{customer_id}/cloudProviders/{provider_id}:link",
            json_body=link_data,
        )

    async def provision_cloud_provider(
        self, customer_id: str, provider_id: str, provision_data: dict,
    ) -> dict:
        return await self._request(
            "POST",
            f"/accounts/{self.account_id}/customers/{customer_id}/cloudProviders/{provider_id}:provision",
            json_body=provision_data,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self):
        await self.client.aclose()
