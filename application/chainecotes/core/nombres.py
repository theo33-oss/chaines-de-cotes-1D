"""Écriture des nombres à la française (virgule décimale), partagée par les graphiques, le PDF et les textes.

Ce module n'importe ni streamlit ni plotly.
"""

import math


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
    return format(v, fmt).replace(".", ",")


def ppmLisible(x: float | None, unite: bool = True) -> str:
    """Taux hors tolérance lisible : « < 0,001 ppm » sous 0,001 plutôt qu'un exposant comme 2,887e-07.

    Entrées : x (ppm, None ou nan acceptés), unite (False : sans « ppm », pour une colonne). Sortie : texte.
    """
    petit = x is not None and not math.isnan(x) and x < 1e-3
    texte = "< 0,001" if petit else fr(x, ".4g")
    return f"{texte} ppm" if unite and texte != "—" else texte
