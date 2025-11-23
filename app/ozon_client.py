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

    def extract_sku_from_url(self, url: str) -> Optional[str]:
        if not url:
            return None

        m = re.search(r"/product/[^/]*?(\d+)(?:[/?]|$)", url)
        if not m:
            m = re.search(r"(\d+)(?:[/?]|$)", url)
        if not m:
            return None

        digits = m.group(1)
        return digits.strip() or None

    def get_product_by_sku(self, sku: str) -> Optional[Dict[str, Any]]:
        body = {
            "offer_id": [],
            "product_id": [],
            "sku": [str(sku)],
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

    def _extract_sku_with_redirects(self, ozon_url: str) -> Optional[str]:
        """
        Resolve short links like https://ozon.ru/t/xxxxx to a full product URL and pull out the SKU.
        Some short links return 403/anti-bot without a browser-like User-Agent, so we try both HEAD and GET.
        """
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        for method in ("head", "get"):
            try:
                resp = requests.request(
                    method,
                    ozon_url,
                    allow_redirects=True,
                    timeout=10,
                    headers=headers,
                )
            except Exception:
                continue

            # Check every redirect hop plus the final URL
            urls_to_check = [h.headers.get("location") or "" for h in resp.history] + [resp.url or ""]
            for candidate in urls_to_check:
                sku = self.extract_sku_from_url(candidate)
                if sku:
                    return sku

        return None

    def get_price_by_url(self, ozon_url: str) -> Optional[Dict[str, Any]]:
        # 1) Try to extract directly from the provided URL
        sku = self.extract_sku_from_url(ozon_url)
        # 2) If it's a short link (e.g., https://ozon.ru/t/xxxxx), follow redirects to grab the SKU
        if not sku and ozon_url:
            sku = self._extract_sku_with_redirects(ozon_url)
        if not sku:
            return None
        return self.get_product_by_sku(sku)
