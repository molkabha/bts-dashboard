"""Governorate centroids and GPS helpers for the BTS station map."""

from __future__ import annotations

import hashlib
import re
import unicodedata

import pandas as pd

# Approximate centroids (lat, lon) for Tunisian governorates
GOVERNORATE_COORDS: dict[str, tuple[float, float]] = {
    "tunis": (36.8065, 10.1815),
    "ariana": (36.8665, 10.1647),
    "ben arous": (36.7545, 10.2217),
    "manouba": (36.8101, 10.0970),
    "nabeul": (36.4561, 10.7376),
    "zaghouan": (36.4020, 10.1429),
    "bizerte": (37.2744, 9.8739),
    "beja": (36.7256, 9.1817),
    "jendouba": (36.5000, 8.7833),
    "le kef": (36.1742, 8.7047),
    "kef": (36.1742, 8.7047),
    "siliana": (36.0849, 9.3708),
    "sousse": (35.8256, 10.6360),
    "monastir": (35.7643, 10.8113),
    "mahdia": (35.5047, 11.0622),
    "sfax": (34.7406, 10.7603),
    "kairouan": (35.6781, 10.0963),
    "kasserine": (35.1676, 8.8365),
    "sidi bouzid": (35.0382, 9.4849),
    "gabes": (33.8815, 10.0982),
    "gabès": (33.8815, 10.0982),
    "medenine": (33.3549, 10.5055),
    "médenine": (33.3549, 10.5055),
    "tataouine": (32.9297, 10.4518),
    "gafsa": (34.4250, 8.7842),
    "tozeur": (33.9197, 8.1335),
    "kebili": (33.7044, 8.9690),
    "kébili": (33.7044, 8.9690),
}

GEO_COLUMN_ALIASES: dict[str, list[str]] = {
    "latitude": ["lat", "Lat", "LAT", "gps_lat", "station_lat", "latitude_station", "lat_station"],
    "longitude": ["lon", "lng", "long", "Lon", "LON", "gps_lon", "gps_lng", "station_lon", "longitude_station"],
}


def _normalize_key(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text.strip().lower())


def governorate_centroid(name: str) -> tuple[float, float] | None:
    if not name or pd.isna(name):
        return None
    key = _normalize_key(name)
    if key in GOVERNORATE_COORDS:
        return GOVERNORATE_COORDS[key]
    for gov, coords in GOVERNORATE_COORDS.items():
        if gov in key or key in gov:
            return coords
    return None


def station_coordinate_jitter(station_id: str, scale: float = 0.04) -> tuple[float, float]:
    """Small deterministic offset so stations in the same governorate do not stack."""
    digest = hashlib.md5(str(station_id).encode("utf-8")).hexdigest()
    a = int(digest[:8], 16) / 0xFFFFFFFF
    b = int(digest[8:16], 16) / 0xFFFFFFFF
    return (a - 0.5) * scale, (b - 0.5) * scale


def normalize_geo_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    for canonical, aliases in GEO_COLUMN_ALIASES.items():
        if canonical in out.columns:
            continue
        for alias in aliases:
            if alias in out.columns:
                out[canonical] = out[alias]
                break
    if "latitude" in out.columns:
        out["latitude"] = pd.to_numeric(out["latitude"], errors="coerce")
    if "longitude" in out.columns:
        out["longitude"] = pd.to_numeric(out["longitude"], errors="coerce")
    return out


def valid_coordinate_mask(df: pd.DataFrame) -> pd.Series:
    if not {"latitude", "longitude"}.issubset(df.columns):
        return pd.Series(False, index=df.index)
    lat = pd.to_numeric(df["latitude"], errors="coerce")
    lon = pd.to_numeric(df["longitude"], errors="coerce")
    return lat.notna() & lon.notna() & lat.between(-90, 90) & lon.between(-180, 180)
