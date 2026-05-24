from __future__ import annotations

from datetime import date

from hijri_converter import convert

CIVIL_HOLIDAYS: frozenset[tuple[int, int]] = frozenset({
    (1, 1),
    (3, 20),
    (4, 9),
    (5, 1),
    (7, 25),
    (8, 13),
    (10, 15),
    (12, 17),
})


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
