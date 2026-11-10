"""Figures de la page « Optimisation de chaîne de cotes » : coûts par maillon et IT de deux scénarios."""

import plotly.graph_objects as go

from chainecotes.plots._common import BLEU, VERMILLON, fr, miseEnPage


def _barres(noms, a, b, nomA, nomB, titre, unite, fmt) -> go.Figure:
    """Barres jumelées (A bleu, B vermillon) ; une valeur None n'est pas tracée."""
    fig = go.Figure(
        [
            go.Bar(x=noms, y=a, name=nomA, marker_color=BLEU, hovertemplate="%{x} : %{y:" + fmt + "}"),
            go.Bar(x=noms, y=b, name=nomB, marker_color=VERMILLON, hovertemplate="%{x} : %{y:" + fmt + "}"),
        ]
    )
    miseEnPage(fig, titre, 380)
    fig.update_layout(barmode="group")
    fig.update_yaxes(title_text=unite)
    return fig


def figureCoutsMaillons(noms: list[str], avant: list, apres: list) -> tuple:
    """Coût relatif de chaque maillon, avant (saisie) et après (répartition au coût minimal).

    Entrées : noms (maillons), avant et apres (coûts relatifs sans unité ; None si non défini).
    Sortie : (figure, légende en français).
    """
    fig = _barres(
        noms, avant, apres, "Avant (saisie)", "Après (coût minimal)", "Coût relatif par maillon", "Coût relatif", ".3f"
    )
    detail = " ; ".join(
        f"{n} : {'—' if a is None else fr(a, '.2f')} → {fr(b, '.2f')}"
        for n, a, b in zip(noms, avant, apres, strict=True)
    )
    return fig, f"Coût relatif par maillon, avant et après la répartition : {detail}."


def figureScenarios(maillons: list[dict], nomA: str = "Scénario A", nomB: str = "Scénario B") -> tuple:
    """IT (mm) des maillons des deux scénarios, en barres jumelées.

    Entrées : maillons (liste de comparerScenarios()['maillons'] : nom, itA, itB en mm, None si absent), nomA, nomB.
    Sortie : (figure, légende en français).
    """
    noms = [m["nom"] for m in maillons]
    a, b = (([m[k] for m in maillons]) for k in ("itA", "itB"))
    fig = _barres(noms, a, b, nomA, nomB, "Intervalles de tolérance IT par maillon", "IT (mm)", ".4f")
    detail = " ; ".join(
        f"{n} : {'—' if x is None else fr(x, '.4f')} / {'—' if y is None else fr(y, '.4f')} mm"
        for n, x, y in zip(noms, a, b, strict=True)
    )
    return fig, f"IT par maillon ({nomA} / {nomB}) : {detail}."
