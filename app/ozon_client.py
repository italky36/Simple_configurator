import re
from typing import Dict, Any, Optional

import requests


class OzonClient:
    def __init__(self, client_id: str, api_key: str):
        self.client_id = client_id
        self.api_key = api_key
        self.base_url = "https://api-seller.ozon.ru"

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = self.base_url + path
        headers = {
            "Client-Id": self.client_id,
            "Api-Key": self.api_key,
            "Content-Type": "application/json",
        }

        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        if resp.status_code != 200:
            raise Exception(f"Ozon API HTTP error {resp.status_code}: {resp.text}")

        data = resp.json()

        if isinstance(data, dict) and "code" in data and data.get("code") not in (0, "0"):
            raise Exception(f"Ozon business error: {data.get('message', 'Unknown error')}")

        return data

    def extract_offer_id_from_url(self, url: str) -> Optional[str]:
        if not url:
            return None

        m = re.search(r"/product/[^/]*?(\d+)(?:[/?]|$)", url)
        if not m:
            m = re.search(r"(\d+)(?:[/?]|$)", url)
        if not m:
            return None

        digits = m.group(1)
        return digits.strip() or None

    def get_product_by_offer_id(self, offer_id: str) -> Optional[Dict[str, Any]]:
        body = {
            "offer_id": [str(offer_id)],
            "product_id": [],
            "sku": [],
        }

        data = self._post("/v3/product/info/list", body)
        items = data.get("items") or []

        if not items:
            return None

        item = items[0]
        price_val = item.get("price")
        currency = item.get("currency_code") or "RUB"

        return {
            "product_id": item.get("id") or item.get("product_id"),
            "offer_id": str(item.get("offer_id")) if item.get("offer_id") is not None else None,
            "name": item.get("name") or "",
            "price": price_val,
            "currency": currency,
        }

    def get_price_by_url(self, ozon_url: str) -> Optional[Dict[str, Any]]:
        offer_id = self.extract_offer_id_from_url(ozon_url)
        if not offer_id:
            return None

        return self.get_product_by_offer_id(offer_id)
