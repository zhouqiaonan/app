import logging
import math
from typing import Any

from tools.db_tool import get_cached_distance, save_distance

logger = logging.getLogger(__name__)


def haversine_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> int:
    if lat1 == lat2 and lng1 == lng2:
        return 0

    earth_radius_meters = 6_371_000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    distance = earth_radius_meters * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(distance)


def calculate_distance_matrix(locations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    valid = [
        dict(item)
        for item in locations
        if item.get("lng") is not None and item.get("lat") is not None
    ]

    logger.info("calculate_distance_matrix: %d valid locations", len(valid))

    for origin in valid:
        origin["distances"] = {}
        for destination in valid:
            if origin["name"] == destination["name"]:
                origin["distances"][destination["name"]] = 0
                continue
            # Check cache
            cached = get_cached_distance(origin["name"], destination["name"])
            if cached is not None:
                origin["distances"][destination["name"]] = cached
                continue
            # Calculate and cache
            meters = haversine_meters(
                origin["lat"], origin["lng"],
                destination["lat"], destination["lng"],
            )
            origin["distances"][destination["name"]] = meters
            logger.info("distance: %s -> %s = %dm", origin["name"], destination["name"], meters)
            save_distance(origin["name"], destination["name"], meters)

    return valid
