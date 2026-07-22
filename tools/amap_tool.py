import asyncio
from typing import Any

import aiohttp
import requests

from tools.db_tool import get_cached_geocode, save_geocode, init_db


class AMapClient:
    def __init__(self, web_key: str):
        self.web_key = web_key

    def geocode_addresses(self, locations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        geocoded = []
        for location in locations:
            geocoded.append(self._geocode_one(location))
        return geocoded

    def _geocode_one(self, location: dict[str, Any]) -> dict[str, Any]:
        address = location.get("address", "").strip()
        # Check cache first
        if address:
            cached = get_cached_geocode(address)
            if cached:
                return {
                    "name": location.get("name", "未命名"),
                    "address": address,
                    "lng": cached["lng"],
                    "lat": cached["lat"],
                }
        # Not cached — call AMap API
        response = requests.get(
            "https://restapi.amap.com/v3/geocode/geo",
            params={"address": address, "key": self.web_key},
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        result = self._parse_geocode_response(location, payload)
        # Save successful result to cache
        if result.get("lng") is not None and address:
            save_geocode(address, result["lng"], result["lat"])
        return result

    async def async_geocode_addresses(
        self,
        locations: list[dict[str, Any]],
        max_concurrency: int = 2,
    ) -> list[dict[str, Any]]:
        semaphore = asyncio.Semaphore(max_concurrency)

        async def geocode_with_semaphore(location: dict[str, Any]) -> dict[str, Any]:
            async with semaphore:
                return await self._geocode_one_async(session, location)

        async with aiohttp.ClientSession() as session:
            tasks = [geocode_with_semaphore(loc) for loc in locations]
            return await asyncio.gather(*tasks)

    async def _geocode_one_async(
        self, session: aiohttp.ClientSession, location: dict[str, Any]
    ) -> dict[str, Any]:
        address = location.get("address", "").strip()
        # Check cache first
        if address:
            cached = get_cached_geocode(address)
            if cached:
                return {
                    "name": location.get("name", "未命名"),
                    "address": address,
                    "lng": cached["lng"],
                    "lat": cached["lat"],
                }
        try:
            async with session.get(
                "https://restapi.amap.com/v3/geocode/geo",
                params={"address": address, "key": self.web_key},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                response.raise_for_status()
                payload = await response.json()
                await asyncio.sleep(0.2)
                result = self._parse_geocode_response(location, payload)
                if result.get("lng") is not None and address:
                    save_geocode(address, result["lng"], result["lat"])
                return result
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            return {
                "name": location.get("name", "未命名"),
                "address": address,
                "lng": None,
                "lat": None,
                "error": str(e),
            }
        except Exception as e:
            return {
                "name": location.get("name", "未命名"),
                "address": address,
                "lng": None,
                "lat": None,
                "error": repr(e),
            }

    def _parse_geocode_response(
        self, location: dict[str, Any], payload: dict[str, Any]
    ) -> dict[str, Any]:
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
