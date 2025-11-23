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
        """
        Try to pull Ozon SKU (product_id) out of a URL.
        We prefer the /product/.../<sku> segment, otherwise pick the longest digit sequence (>=6 chars)
        to avoid grabbing short query params like "09" that break the API.
        """
        if not url:
            return None

        # Prefer explicit product path
        m = re.search(r"/product/[^/]+/(\d+)", url)
        if m:
            digits = m.group(1).strip()
            if digits and len(digits) >= 6:
                return digits

        # Fallback: choose the longest digit chunk in the URL
        candidates = re.findall(r"(\d+)", url)
        if not candidates:
            return None
        longest = max(candidates, key=len)
        if len(longest) < 6:
            return None
        return longest.strip() or None

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
        Ozon often responds with anti-bot 403 first; we reuse cookies and retry, then fall back to the composer API.
        """
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru,en;q=0.9",
        }

        session = requests.Session()
        session.headers.update(headers)

        def try_urls(urls):
            for candidate in urls:
                sku = self.extract_sku_from_url(candidate)
                if sku:
                    return sku
            return None

        # First, try real HTTP redirects (2 attempts to reuse anti-bot cookies)
        for _ in range(2):
            try:
                resp = session.get(ozon_url, allow_redirects=True, timeout=10)
            except Exception:
                resp = None
            if resp is None:
                continue
            urls_to_check = [h.headers.get("location") or "" for h in resp.history] + [resp.url or ""]
            sku = try_urls(urls_to_check)
            if sku:
                return sku

        # Fallback: call the public composer API by path (/t/<code>) and scrape digits
        if "/t/" in ozon_url:
            short_code = ozon_url.rsplit("/t/", 1)[-1].split("/")[0]
            api_url = f"https://www.ozon.ru/api/composer-api.bx/page/json/v2?url=/t/{short_code}"
            try:
                resp = session.get(api_url, timeout=10)
                if resp.ok:
                    sku = self.extract_sku_from_url(resp.text)
                    if sku:
                        return sku
            except Exception:
                pass

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
