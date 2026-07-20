import asyncio
from typing import Any

import aiohttp
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
        return self._parse_geocode_response(location, payload)

    async def async_geocode_addresses(
        self,
        locations: list[dict[str, Any]],
        max_concurrency: int = 10,
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
        try:
            async with session.get(
                "https://restapi.amap.com/v3/geocode/geo",
                params={"address": location.get("address", ""), "key": self.web_key},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                response.raise_for_status()
                payload = await response.json()
                return self._parse_geocode_response(location, payload)
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            return {
                "name": location.get("name", "未命名"),
                "address": location.get("address", ""),
                "lng": None,
                "lat": None,
                "error": str(e),
            }
        except Exception as e:
            return {
                "name": location.get("name", "未命名"),
                "address": location.get("address", ""),
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
