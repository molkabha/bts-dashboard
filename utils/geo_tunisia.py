from __future__ import annotations

import hashlib

import re

import unicodedata

import pandas as pd

TUNISIA_LAT_MIN = 30.2

TUNISIA_LAT_MAX = 37.6

TUNISIA_LON_MIN = 7.4

TUNISIA_LON_MAX = 11.9

GOVERNORATE_BBOXES: dict[str, tuple[float, float, float, float]] = {
    "tunis": (36.74, 36.84, 10.08, 10.24),
    "ariana": (36.84, 36.94, 10.08, 10.24),
    "ben arous": (36.72, 36.82, 10.18, 10.3),
    "manouba": (36.78, 36.88, 9.96, 10.12),
    "nabeul": (36.36, 36.52, 10.42, 10.62),
    "zaghouan": (36.36, 36.5, 9.98, 10.18),
    "bizerte": (37.16, 37.28, 9.58, 9.82),
    "beja": (36.66, 36.78, 9.12, 9.32),
    "jendouba": (36.46, 36.58, 8.58, 8.86),
    "le kef": (36.12, 36.24, 8.58, 8.82),
    "kef": (36.12, 36.24, 8.58, 8.82),
    "siliana": (36.02, 36.14, 9.28, 9.48),
    "sousse": (35.81, 35.91, 10.48, 10.66),
    "monastir": (35.72, 35.8, 10.72, 10.86),
    "mahdia": (35.46, 35.56, 10.88, 11.02),
    "sfax": (34.68, 34.82, 10.52, 10.78),
    "kairouan": (35.62, 35.74, 9.98, 10.14),
    "kasserine": (35.12, 35.24, 8.68, 8.9),
    "sidi bouzid": (34.98, 35.12, 9.38, 9.62),
    "gabes": (33.86, 33.98, 9.98, 10.14),
    "gabès": (33.86, 33.98, 9.98, 10.14),
    "medenine": (33.32, 33.42, 10.38, 10.52),
    "médenine": (33.32, 33.42, 10.38, 10.52),
    "tataouine": (32.88, 33.02, 10.18, 10.42),
    "gafsa": (34.36, 34.48, 8.68, 8.9),
    "tozeur": (33.88, 33.98, 8.0, 8.22),
    "kebili": (33.66, 33.78, 8.88, 9.12),
    "kébili": (33.66, 33.78, 8.88, 9.12),
}


def _text_val(value, default: str = "") -> str:

    try:

        if pd.isna(value):

            return default

    except (TypeError, ValueError):

        pass

    text = str(value).strip()

    if text.lower() in ("", "nan", "none", "<na>"):

        return default

    return text


GEO_COLUMN_ALIASES: dict[str, list[str]] = {
    "latitude": [
        "lat",
        "Lat",
        "LAT",
        "gps_lat",
        "station_lat",
        "latitude_station",
        "lat_station",
    ],
    "longitude": [
        "lon",
        "lng",
        "long",
        "Lon",
        "LON",
        "gps_lon",
        "gps_lng",
        "station_lon",
        "longitude_station",
    ],
}

GPS_SOURCE_PRIORITY: dict[str, int] = {
    "carte_nb3": 40,
    "dataset_actif": 30,
    "swap_corrige": 25,
    "bbox_gouvernorat": 10,
    "centroide_gouvernorat": 5,
}


def _normalize_key(value: str) -> str:

    text = unicodedata.normalize("NFKD", str(value or ""))

    text = "".join((ch for ch in text if not unicodedata.combining(ch)))

    return re.sub("\\s+", " ", text.strip().lower())


def governorate_bbox(name: str) -> tuple[float, float, float, float] | None:

    if not name or pd.isna(name):

        return None

    key = _normalize_key(name)

    if key in GOVERNORATE_BBOXES:

        return GOVERNORATE_BBOXES[key]

    for gov, bbox in GOVERNORATE_BBOXES.items():

        if gov in key or key in gov:

            return bbox

    return None


def in_tunisia_bounds(lat: float, lon: float) -> bool:

    return (
        TUNISIA_LAT_MIN <= lat <= TUNISIA_LAT_MAX
        and TUNISIA_LON_MIN <= lon <= TUNISIA_LON_MAX
    )


def in_bbox(lat: float, lon: float, bbox: tuple[float, float, float, float]) -> bool:

    lat_min, lat_max, lon_min, lon_max = bbox

    return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max


def looks_lat_lon_swapped(lat: float, lon: float) -> bool:

    if not in_tunisia_bounds(lat, lon) and in_tunisia_bounds(lon, lat):

        return True

    if 7.0 <= lat <= 12.5 and 30.0 <= lon <= 38.0:

        return True

    return False


def is_likely_in_sea(lat: float, lon: float) -> bool:

    if not in_tunisia_bounds(lat, lon):

        return True

    if lat >= 36.88 and lon >= 10.32:

        return True

    if lat >= 37.05 and lon >= 10.05:

        return True

    if lat >= 35.62 and lon >= 11.08:

        return True

    if lat >= 35.48 and lon >= 11.15:

        return True

    if lat >= 37.32 and lon >= 9.9:

        return True

    if lat >= 36.55 and lon >= 10.72:

        return True

    if lat < 33.0 and lon >= 11.0:

        return True

    return False


def station_position_in_governorate(
    station_id: str, governorate: str
) -> tuple[float, float] | None:

    bbox = governorate_bbox(governorate)

    if bbox is None:

        return None

    lat_min, lat_max, lon_min, lon_max = bbox

    digest = hashlib.md5(str(station_id).encode("utf-8")).hexdigest()

    a = int(digest[:8], 16) / 4294967295

    b = int(digest[8:16], 16) / 4294967295

    lat = lat_min + a * (lat_max - lat_min)

    lon = lon_min + b * (lon_max - lon_min)

    return (lat, lon)


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


def repair_coordinate_pair(
    lat: float | None, lon: float | None, governorate: str | None = None
) -> tuple[float | None, float | None, str]:

    if lat is None or lon is None or pd.isna(lat) or pd.isna(lon):

        if governorate and (not pd.isna(governorate)):

            pos = station_position_in_governorate("unknown", str(governorate))

            if pos:

                return (pos[0], pos[1], "bbox_gouvernorat")

        return (None, None, "invalid")

    lat_f, lon_f = (float(lat), float(lon))

    source = "ok"

    if looks_lat_lon_swapped(lat_f, lon_f):

        lat_f, lon_f = (lon_f, lat_f)

        source = "swap_corrige"

    gov = (
        str(governorate)
        if governorate is not None and (not pd.isna(governorate))
        else ""
    )

    bbox = governorate_bbox(gov) if gov else None

    needs_repair = (
        not in_tunisia_bounds(lat_f, lon_f)
        or is_likely_in_sea(lat_f, lon_f)
        or (bbox is not None and (not in_bbox(lat_f, lon_f, bbox)))
    )

    if needs_repair and gov:

        pos = station_position_in_governorate(f"{lat_f}:{lon_f}", gov)

        if pos:

            return (pos[0], pos[1], "bbox_gouvernorat")

    if not in_tunisia_bounds(lat_f, lon_f) or is_likely_in_sea(lat_f, lon_f):

        return (None, None, "invalid")

    return (lat_f, lon_f, source if source != "ok" else "valide")


def sanitize_station_coordinates(stations: pd.DataFrame) -> pd.DataFrame:

    if stations.empty or "station_id" not in stations.columns:

        return stations

    out = normalize_geo_columns(stations)

    if "gps_source" not in out.columns:

        out["gps_source"] = pd.NA

    gov_col = "gouvernorat" if "gouvernorat" in out.columns else None

    for idx, row in out.iterrows():

        gov = row[gov_col] if gov_col else None

        lat = row.get("latitude")

        lon = row.get("longitude")

        prev_source = _text_val(row.get("gps_source"))

        if pd.isna(lat) or pd.isna(lon):

            pos = station_position_in_governorate(
                str(row["station_id"]), str(gov or "")
            )

            if pos:

                out.at[idx, "latitude"] = pos[0]

                out.at[idx, "longitude"] = pos[1]

                out.at[idx, "gps_source"] = "bbox_gouvernorat"

            continue

        new_lat, new_lon, tag = repair_coordinate_pair(lat, lon, gov)

        if new_lat is None or new_lon is None:

            pos = station_position_in_governorate(
                str(row["station_id"]), str(gov or "")
            )

            if pos:

                out.at[idx, "latitude"] = pos[0]

                out.at[idx, "longitude"] = pos[1]

                out.at[idx, "gps_source"] = "bbox_gouvernorat"

            continue

        out.at[idx, "latitude"] = new_lat

        out.at[idx, "longitude"] = new_lon

        if tag == "swap_corrige":

            out.at[idx, "gps_source"] = (
                f"{prev_source}+swap"
                if prev_source and prev_source not in ("nan", "None")
                else "swap_corrige"
            )

        elif tag == "bbox_gouvernorat":

            out.at[idx, "gps_source"] = "bbox_gouvernorat"

        elif not prev_source or prev_source in ("nan", "None", ""):

            out.at[idx, "gps_source"] = "valide"

    return out
