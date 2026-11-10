"""Courbes de dilatation d'un matériau : déformation ε(T) et α moyen, avec les zones hors domaine d'emploi."""

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from chainecotes.core.materiaux import alphaMateriau, deformation
from chainecotes.plots._common import BLEU, GRIS, VERMILLON, fr, miseEnPage, teinte

T_MIN, T_MAX = -269.0, 600.0  # °C : de l'hélium liquide au haut des courbes du classeur


def intervallesHors(T: np.ndarray, hors: np.ndarray) -> list[tuple[float, float]]:
    """Intervalles de température contigus où le matériau est hors domaine.

    Entrées : T (°C, croissant), hors (bool, même forme). Sortie : liste de (début, fin) en °C.
    """
    zones, debut = [], None
    for t, h in zip(T, hors, strict=True):
        if h and debut is None:
            debut = t
        if not h and debut is not None:
            zones.append((debut, t))
            debut = None
    if debut is not None:
        zones.append((debut, T[-1]))
    return zones


def figureDilatation(m: dict, tref: float) -> tuple[go.Figure, str]:
    """Figure à deux étages : déformation ε(T) depuis 20 °C, puis α moyen entre Tref et T, de −269 à 600 °C.

    Entrées : m (élément de listeMateriaux), tref (°C). Sortie : (figure Plotly, légende en français).
    Les zones hors domaine d'emploi (ou extrapolées) sont grisées.
    """
    T = np.linspace(T_MIN, T_MAX, 870)
    eps = deformation(m, T) * 1e6  # µm/m
    r = alphaMateriau(m["nom"], T, tref)
    alpha = r["alpha"] * 1e6
    zones = intervallesHors(T, r["horsDomaine"])
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08)
    fig.add_trace(go.Scatter(x=T, y=eps, name="ε(T) depuis 20 °C", line={"color": BLEU, "width": 2}), row=1, col=1)
    fig.add_trace(
        go.Scatter(x=T, y=alpha, name=f"α moyen depuis {fr(tref, 'g')} °C", line={"color": VERMILLON, "width": 2}),
        row=2,
        col=1,
    )
    for a, b in zones:
        for ligne in (1, 2):
            fig.add_vrect(x0=a, x1=b, fillcolor=teinte(GRIS, 0.25), line_width=0, layer="below", row=ligne, col=1)
    miseEnPage(fig, f"Dilatation de {m['nom']} (zones grisées : hors domaine d'emploi ou extrapolé)", 560)
    fig.update_yaxes(title_text="ε (µm/m)", row=1, col=1)
    fig.update_yaxes(title_text="α moyen (10⁻⁶/K)", row=2, col=1)
    fig.update_xaxes(title_text="Température (°C)", row=2, col=1)
    legende = (
        f"{m['nom']} : déformation de {fr(eps[0], '.0f')} µm/m à {fr(T_MIN, 'g')} °C et {fr(eps[-1], '.0f')} µm/m à "
        f"{fr(T_MAX, 'g')} °C (nulle à 20 °C) ; α moyen depuis {fr(tref, 'g')} °C de {fr(np.nanmin(alpha), '.2f')} "
        f"à {fr(np.nanmax(alpha), '.2f')} × 10⁻⁶/K. "
    )
    if zones:
        legende += "Hors domaine : " + ", ".join(f"{fr(a, '.0f')} à {fr(b, '.0f')} °C" for a, b in zones) + "."
    else:
        legende += "Aucune zone hors domaine sur cette plage."
    return fig, legende
