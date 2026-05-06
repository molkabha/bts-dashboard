"""Hijri calendar and Tunisian holiday utilities."""

from __future__ import annotations

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

try:
    import pyarrow.parquet as pq
except Exception:
    pq = None

try:
    from hijri_converter import convert as hijri_convert
except Exception:
    hijri_convert = None

try:
    from hijridate import Hijri as HijriDate
except Exception:
    HijriDate = None

RAMADAN_DEPS_AVAILABLE = hijri_convert is not None or HijriDate is not None
RAMADAN_ENABLED = bool(RAMADAN_DEPS_AVAILABLE)
RAMADAN_DISABLED_REASON = (
    "Ramadan/hijri désactivé: dépendances hijri-converter/hijridate indisponibles au runtime."
)

RAMADAN_ANCHOR_START = datetime(2026, 2, 18).date()
RAMADAN_ANCHOR_YEAR = 2026
RAMADAN_LENGTH_DAYS = 30
HIJRI_YEAR_DAYS = 354.367

FIXED_TUNISIA_HOLIDAYS = {
    (1, 1): "Nouvel an",
    (3, 20): "Fete de l'independance",
    (4, 9): "Jour des martyrs",
    (5, 1): "Fete du travail",
    (7, 25): "Fete de la republique",
    (8, 13): "Fete de la femme",
    (10, 15): "Fete de l'evacuation",
    (12, 17): "Fete de la Revolution et de la Jeunesse",
}

PROFILS_TRAFIC_REALTIME = {
    "ramadan": np.array([
        0.95, 0.90, 0.75, 0.55, 0.35, 0.20,
        0.15, 0.12, 0.18, 0.25, 0.35, 0.40,
        0.38, 0.35, 0.30, 0.28, 0.32, 0.45,
        0.60, 0.75, 0.95, 1.00, 0.98, 0.97,
    ]),
    "weekend": np.array([
        0.25, 0.20, 0.18, 0.15, 0.14, 0.16,
        0.22, 0.35, 0.55, 0.70, 0.80, 0.82,
        0.78, 0.74, 0.70, 0.72, 0.78, 0.84,
        0.88, 0.92, 0.90, 0.80, 0.65, 0.40,
    ]),
    "normal": np.array([
        0.20, 0.16, 0.13, 0.11, 0.10, 0.16,
        0.30, 0.60, 0.85, 1.00, 1.05, 1.00,
        0.92, 0.85, 0.78, 0.80, 0.92, 1.00,
        1.05, 1.10, 1.05, 0.92, 0.75, 0.45,
    ]),
}
FACTEUR_ZONE_REALTIME = {"Urbain": 1.0, "Periurbain": 0.72, "Rural": 0.40}
REALTIME_START_DATE = datetime(2025, 1, 1).date()
REALTIME_END_DATE = datetime(2028, 12, 31).date()


def _hijri_to_gregorian(hijri_year: int, hijri_month: int, hijri_day: int):
    """Convert Hijri date to Gregorian date."""
    if hijri_convert is not None:
        return hijri_convert.Hijri(hijri_year, hijri_month, hijri_day).to_gregorian()
    if HijriDate is not None:
        return HijriDate(hijri_year, hijri_month, hijri_day).to_gregorian()
    return tabular_hijri_to_gregorian(hijri_year, hijri_month, hijri_day)


def _gregorian_to_hijri_year(year: int) -> int | None:
    """Convert Gregorian year to Hijri year."""
    if hijri_convert is not None:
        return hijri_convert.Gregorian(year, 1, 1).to_hijri().year
    if HijriDate is not None:
        from hijridate import Gregorian
        return Gregorian(year, 1, 1).to_hijri().year
    return tabular_gregorian_to_hijri_year(year, 1, 1)


def islamic_to_julian_day(year: int, month: int, day: int) -> int:
    """Convert Islamic Hijri date to Julian day number."""
    return int(
        day
        + np.ceil(29.5 * (month - 1))
        + (year - 1) * 354
        + np.floor((3 + 11 * year) / 30)
        + 1948439
    )


def julian_day_to_gregorian(julian_day: int):
    """Convert Julian day number to Gregorian date."""
    value = int(julian_day)
    l_val = value + 68569
    n_val = (4 * l_val) // 146097
    l_val = l_val - (146097 * n_val + 3) // 4
    i_val = (4000 * (l_val + 1)) // 1461001
    l_val = l_val - (1461 * i_val) // 4 + 31
    j_val = (80 * l_val) // 2447
    day = l_val - (2447 * j_val) // 80
    l_val = j_val // 11
    month = j_val + 2 - 12 * l_val
    year = 100 * (n_val - 49) + i_val + l_val
    return datetime(int(year), int(month), int(day)).date()


def tabular_hijri_to_gregorian(year: int, month: int, day: int):
    """Convert Hijri date to Gregorian using tabular method."""
    return julian_day_to_gregorian(islamic_to_julian_day(year, month, day))


def gregorian_to_julian_day(year: int, month: int, day: int) -> int:
    """Convert Gregorian date to Julian day number."""
    return datetime(year, month, day).date().toordinal() + 1721425


def tabular_gregorian_to_hijri_year(year: int, month: int, day: int) -> int:
    """Convert Gregorian date to Hijri year using tabular method."""
    jd = gregorian_to_julian_day(year, month, day)
    return int(np.floor((30 * (jd - 1948439) + 10646) / 10631))


def precise_hijri_date(year: int, hijri_month: int, hijri_day: int):
    """Get precise Gregorian date for a Hijri date."""
    h_year = _gregorian_to_hijri_year(year)
    if h_year is None:
        return None
    for candidate in [h_year - 1, h_year, h_year + 1, h_year + 2]:
        converted = _hijri_to_gregorian(candidate, hijri_month, hijri_day)
        if converted is not None and converted.year == year:
            return datetime(converted.year, converted.month, converted.day).date()
    return None


def approximate_ramadan_start(year: int):
    """Get approximate Ramadan start date for a year."""
    shift_days = round((year - RAMADAN_ANCHOR_YEAR) * HIJRI_YEAR_DAYS)
    return RAMADAN_ANCHOR_START + timedelta(days=shift_days)


def ramadan_range(year: int, method: str = "auto") -> tuple:
    """Get Ramadan date range for a given year."""
    if not RAMADAN_ENABLED:
        return None, None, "ramadan_disabled_missing_hijri_deps"
    precise = precise_hijri_date(year, 9, 1)
    precise_source = "hijri_converter" if hijri_convert is not None or HijriDate is not None else "hijri_tabulaire"
    if method == "precise":
        start = precise
        source = precise_source
    elif method == "approx":
        start = approximate_ramadan_start(year)
        source = "approx_-10_11_jours"
    else:
        start = precise or approximate_ramadan_start(year)
        source = precise_source if precise else "approx_-10_11_jours"
    if start is None:
        return None, None, source
    return start, start + timedelta(days=RAMADAN_LENGTH_DAYS - 1), source


def ramadan_method_check(years: list[int]) -> pd.DataFrame:
    """Compare precise vs approximate Ramadan dates for multiple years."""
    rows = []
    for year in years:
        precise_start, precise_end, _ = ramadan_range(year, "precise")
        approx_start, approx_end, _ = ramadan_range(year, "approx")
        rows.append(
            {
                "annee": year,
                "debut_hijri": precise_start,
                "fin_hijri": precise_end,
                "debut_approx": approx_start,
                "fin_approx": approx_end,
                "ecart_jours": (approx_start - precise_start).days if precise_start and approx_start else np.nan,
            }
        )
    return pd.DataFrame(rows)


def islamic_holiday_dates(year: int) -> dict:
    """Get Islamic holiday dates for a given year."""
    dates = {}
    ramadan_start, ramadan_end, source = ramadan_range(year, "auto")
    if ramadan_end:
        dates[ramadan_end + timedelta(days=1)] = f"Aid el-Fitr ({source})"
        dates[ramadan_end + timedelta(days=2)] = f"Aid el-Fitr 2 ({source})"
        dates[ramadan_end + timedelta(days=3)] = f"Aid el-Fitr 3 ({source})"
    aid_adha = precise_hijri_date(year, 12, 10)
    if aid_adha is None:
        # Approximation: environ 70 jours apres Aid el-Fitr.
        aid_adha = (ramadan_end + timedelta(days=71)) if ramadan_end else None
    if aid_adha:
        dates[aid_adha] = "Aid el-Adha"
        dates[aid_adha + timedelta(days=1)] = "Aid el-Adha 2"
    hijri_new_year = precise_hijri_date(year, 1, 1)
    if hijri_new_year:
        dates[hijri_new_year] = "Nouvel an Hijri"
    mouled = precise_hijri_date(year, 3, 12)
    if mouled:
        dates[mouled] = "Mouled"
    return dates


def tunisian_holiday_name(ts: datetime) -> str:
    """Get Tunisian holiday name for a given date."""
    current = ts.date()
    fixed = FIXED_TUNISIA_HOLIDAYS.get((current.month, current.day))
    if not RAMADAN_ENABLED:
        return fixed or ""
    islamic = islamic_holiday_dates(current.year).get(current, "")
    if fixed and islamic:
        return f"{fixed} / {islamic}"
    return fixed or islamic


def tunisian_holidays_for_year(year: int) -> pd.DataFrame:
    """Get all Tunisian holidays for a given year."""
    rows = []
    start = datetime(year, 1, 1).date()
    for offset in range(366):
        day = start + timedelta(days=offset)
        if day.year != year:
            break
        name = tunisian_holiday_name(datetime.combine(day, datetime.min.time()))
        if name:
            rows.append({"date": day, "jour_ferie": name})
    return pd.DataFrame(rows)


def is_ramadan_date(ts: datetime) -> int:
    """Check if a date is during Ramadan."""
    if not RAMADAN_ENABLED:
        return 0
    current = ts.date()
    start, end, _ = ramadan_range(current.year, "auto")
    return int(start is not None and end is not None and start <= current <= end)


def is_tunisian_holiday(ts: datetime) -> int:
    """Check if a date is a Tunisian holiday."""
    return int(bool(tunisian_holiday_name(ts)))