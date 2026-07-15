from typing import Any

import requests


class AMapClient:
    def __init__(self, web_key: str):
        self.web_key = web_key

    def geocode_addresses(self, locations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        geocoded = []
        for location in locations:
            geocoded.append(self._geocode_one(location))
        return geocoded

    def _geocode_one(self, location: dict[str, Any]) -> dict[str, Any]:
        response = requests.get(
            "https://restapi.amap.com/v3/geocode/geo",
            params={"address": location.get("address", ""), "key": self.web_key},
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()

        if payload.get("status") == "1" and int(payload.get("count", "0")) > 0:
            lng, lat = payload["geocodes"][0]["location"].split(",", maxsplit=1)
            return {
                "name": location.get("name", "未命名"),
                "address": location.get("address", ""),
                "lng": float(lng),
                "lat": float(lat),
            }

        return {
            "name": location.get("name", "未命名"),
            "address": location.get("address", ""),
            "lng": None,
            "lat": None,
            "error": payload.get("info", "地理编码失败"),
        }
