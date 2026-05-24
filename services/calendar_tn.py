from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import yaml
from hijri_converter import convert

from config.settings import ROOT

_DEFAULT_CIVIL = {
    (1, 1), (3, 20), (4, 9), (5, 1), (7, 25), (8, 13), (10, 15), (12, 17),
}

def _load_civil_holidays() -> frozenset[tuple[int, int]]:
    path = Path(ROOT) / "config" / "holidays_tn.yaml"
    if not path.exists():
        return frozenset(_DEFAULT_CIVIL)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        pairs = raw.get("civil") or []
        return frozenset((int(m), int(d)) for m, d in pairs)
    except Exception:
        return frozenset(_DEFAULT_CIVIL)


CIVIL_HOLIDAYS = _load_civil_holidays()


def _hijri(d: date):
    return convert.Gregorian(d.year, d.month, d.day).to_hijri()


def est_ferie_religieux(d: date) -> bool:
    h = _hijri(d)
    if h.month == 10 and h.day == 1:
        return True
    if h.month == 12 and h.day == 10:
        return True
    return False


def calendar_context(d: date) -> dict:
    jour_semaine = d.weekday()
    h = _hijri(d)
    est_weekend = int(jour_semaine in (5, 6))
    est_vendredi = int(jour_semaine == 4)
    est_ferie = int((d.month, d.day) in CIVIL_HOLIDAYS or est_ferie_religieux(d))
    est_ramadan = int(h.month == 9)
    return {
        "mois": d.month,
        "jour_semaine": jour_semaine,
        "est_weekend": est_weekend,
        "est_vendredi": est_vendredi,
        "est_ferie": est_ferie,
        "est_ramadan": est_ramadan,
        "jour_hijri": int(h.day),
        "mois_hijri": int(h.month),
    }


def calendar_label(d: date) -> str:
    ctx = calendar_context(d)
    parts = []
    if ctx.get("est_ramadan"):
        parts.append("Ramadan")
    if ctx.get("est_ferie"):
        parts.append("Ferie")
    if ctx.get("est_vendredi"):
        parts.append("Vendredi")
    if ctx.get("est_weekend"):
        parts.append("Week-end")
    return ", ".join(parts) if parts else "Jour ouvre"


def scenario_timestamps(
    start_date: date,
    start_hour: int = 0,
    num_days: int = 1,
) -> list:
    from datetime import datetime, time

    out = []
    days = max(1, int(num_days))
    for offset in range(days):
        day = start_date + timedelta(days=offset)
        h0 = int(start_hour) if offset == 0 else 0
        for h in range(h0, 24):
            out.append(datetime.combine(day, time(hour=h)))
    return out
