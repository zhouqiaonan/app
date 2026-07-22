"""SQLite-based geocode cache and distance matrix storage."""

import sqlite3
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_db_path: str | None = None


def init_db(db_path: str) -> None:
    """Initialize the SQLite database. Idempotent — safe to call multiple times."""
    global _db_path
    _db_path = db_path
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS geocode_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT NOT NULL UNIQUE,
                lng REAL NOT NULL,
                lat REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_geocode_address ON geocode_cache(address);

            CREATE TABLE IF NOT EXISTS distance_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name_a TEXT NOT NULL,
                name_b TEXT NOT NULL,
                distance_meters INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(name_a, name_b)
            );
            CREATE INDEX IF NOT EXISTS idx_distance_lookup ON distance_cache(name_a, name_b);
        """)
    logger.info("Database initialized at %s", db_path)


def _get_conn() -> sqlite3.Connection:
    if _db_path is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_cached_geocode(address: str) -> dict[str, Any] | None:
    """Look up a cached geocode result. Returns None if not found."""
    try:
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT lng, lat FROM geocode_cache WHERE address = ?",
                (address.strip(),),
            ).fetchone()
            if row:
                return {"lng": row["lng"], "lat": row["lat"]}
    except sqlite3.Error as e:
        logger.warning("Failed to read geocode cache: %s", e)
    return None


def save_geocode(address: str, lng: float, lat: float) -> None:
    """Save a successful geocode result to cache."""
    try:
        with _get_conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO geocode_cache (address, lng, lat) VALUES (?, ?, ?)",
                (address.strip(), lng, lat),
            )
    except sqlite3.Error as e:
        logger.warning("Failed to save geocode cache: %s", e)


def get_cached_distance(name_a: str, name_b: str) -> int | None:
    """Look up a cached distance between two points. Returns meters or None.
    
    Names are normalized so (A, B) and (B, A) hit the same cache entry.
    """
    a, b = sorted([name_a.strip(), name_b.strip()])
    try:
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT distance_meters FROM distance_cache WHERE name_a = ? AND name_b = ?",
                (a, b),
            ).fetchone()
            if row:
                return row["distance_meters"]
    except sqlite3.Error as e:
        logger.warning("Failed to read distance cache: %s", e)
    return None


def save_distance(name_a: str, name_b: str, meters: int) -> None:
    """Save a calculated distance to cache."""
    a, b = sorted([name_a.strip(), name_b.strip()])
    try:
        with _get_conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO distance_cache (name_a, name_b, distance_meters) VALUES (?, ?, ?)",
                (a, b, meters),
            )
    except sqlite3.Error as e:
        logger.warning("Failed to save distance cache: %s", e)
