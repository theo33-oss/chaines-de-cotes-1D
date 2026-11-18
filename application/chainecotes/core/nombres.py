"""Écriture des nombres à la française (virgule décimale), partagée par les graphiques, le PDF et les textes.

Ce module n'importe ni streamlit ni plotly.
"""

import math
import re

_HAUT = str.maketrans("0123456789+-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻")
_EXPOSANT = re.compile(r"[eE]([+-]?)0*(\d+)")


def exposants(texte: str) -> str:
    """Remplace un exposant écrit « e+07 » par « ·10⁷ » (« e-05 » par « ·10⁻⁵ »).

    Entrée : texte (nombre déjà écrit). Sortie : texte lisible, inchangé s'il n'y a pas d'exposant.
    """
    def _remplacer(m: re.Match) -> str:
        signe = "-" if m.group(1) == "-" else ""
        return "·10" + (signe + m.group(2)).translate(_HAUT)

    return _EXPOSANT.sub(_remplacer, texte)


def fr(v: float, fmt: str = ".4f") -> str:
    """Nombre écrit à la française (virgule décimale), « +∞ » / « −∞ » pour l'infini, « — » pour nan ou vide.

    Entrées : v (nombre ou None), fmt (format Python, ex. « .4f », « .3g »). Sortie : texte.
    """
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    if math.isinf(v):
        return "+∞" if v > 0 else "−∞"
    if abs(v) < 1e-12:
        v = 0.0
    return exposants(format(v, fmt)).replace(".", ",")


def ppmLisible(x: float | None, unite: bool = True) -> str:
    """Taux hors tolérance lisible : « < 0,001 ppm » sous 0,001 plutôt qu'un exposant comme 2,887e-07.

    Entrées : x (ppm, None ou nan acceptés), unite (False : sans « ppm », pour une colonne). Sortie : texte.
    """
    petit = x is not None and not math.isnan(x) and x < 1e-3
    texte = "< 0,001" if petit else fr(x, ".4g")
    return f"{texte} ppm" if unite and texte != "—" else texte
