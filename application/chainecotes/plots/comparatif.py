"""Figures de la comparaison de chaînes (Plotly, sans Qt) : plages de jeu, Cpk, distributions Monte-Carlo.

Une couleur, une trame et un symbole par colonne (jusqu'à 12) : la lecture reste possible en niveaux de gris.
Le vert, l'orange et le rouge restent réservés aux statuts et ne servent pas à distinguer les chaînes.
"""

import html
import math

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from chainecotes.core.donnees import chargerJson
from chainecotes.plots._common import (
    BLEU,
    GRIS,
    ROSE,
    TEXTE,
    VERMILLON,
    fr,
    intervalle,
    miseEnPage,
    teinte,
)

CPK_CIBLE = chargerJson("controles.json")["cpk_cible"]

# 12 teintes sans vert, orange ni rouge, de clarté variée (lisibles aussi en gris)
_COULEURS = [
    BLEU,
    "#0072B2",
    ROSE,
    "#56B4E9",
    "#7A4A1E",
    "#A0207A",
    "#1B1B1B",
    "#B39DDB",
    "#2A9DA8",
    "#8C6D00",
    GRIS,
    "#1F3A6E",
]
_TRAMES = ["", "/", "\\", "x", "-", "|", "+", ".", "/", "\\", "x", "-"]
_SYMBOLES = [
    "circle",
    "square",
    "diamond",
    "cross",
    "x",
    "triangle-up",
    "triangle-down",
    "star",
    "pentagon",
    "hexagon",
    "triangle-left",
    "triangle-right",
]
_NB_BACS = 40


def _h(texte: str, longueur: int = 30) -> str:
    """Texte saisi sûr pour Plotly (balises échappées), coupé s'il est long."""
    t = texte if len(texte) <= longueur else texte[: longueur - 1] + "…"
    return html.escape(t)


def _valides(resultat: dict) -> list[tuple[int, str, dict]]:
    """Colonnes calculées : (rang d'origine, nom, bundle). Le rang fixe la couleur de la colonne."""
    bundles = resultat.get("_bundles")
    if bundles is None:
        raise ValueError("Figures impossibles : les calculs (« _bundles ») manquent dans le résultat.")
    return [(i, c["nom"], b) for i, (c, b) in enumerate(zip(resultat["colonnes"], bundles, strict=True)) if b]


def _fini(x) -> bool:
    return x is not None and math.isfinite(float(x))


def _finaliser(fig: go.Figure, titre: str, hauteur: int) -> go.Figure:
    miseEnPage(fig, titre, hauteur)
    fig.update_layout(separators=", ")  # virgule décimale, espace entre les milliers
    return fig


def _figureVide(titre: str, message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        x=0.5, y=0.5, xref="paper", yref="paper", text=message, showarrow=False, font={"size": 14, "color": GRIS}
    )
    _finaliser(fig, titre, 260)
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


def _trame(i: int, couleur: str) -> dict:
    return {"shape": _TRAMES[i % len(_TRAMES)], "fgcolor": couleur, "bgcolor": "#FFFFFF", "size": 6, "solidity": 0.35}


def _figurePlages(valides: list[tuple[int, str, dict]]) -> tuple[go.Figure, str]:
    n = len(valides)
    pires, stats, bandes = [], [], []
    for _, _, b in valides:
        v, c = b["verdicts"], b["res"]["condition"]
        pires.append((float(v["pireCas"]["min"]), float(v["pireCas"]["max"])))
        stats.append((float(v["rssProc"]["min"]), float(v["rssProc"]["max"])))
        bandes.append((float(c["jmin"]), float(c["jmax"])))
    donnees = [x for p in pires + stats for x in p] + [x for p in bandes for x in p if math.isfinite(x)]
    bas, haut = min(donnees), max(donnees)
    marge = 0.08 * (haut - bas) if haut > bas else max(abs(bas) * 0.05, 0.01)
    bas, haut = bas - marge, haut + marge
    fig = go.Figure()
    for r, ((i, nom, _), pire, stat, bande) in enumerate(zip(valides, pires, stats, bandes, strict=True)):
        couleur = _COULEURS[i % len(_COULEURS)]
        etiquette = _h(nom, 60)
        fig.add_trace(
            go.Bar(
                base=[pire[0]],
                x=[pire[1] - pire[0]],
                y=[r],
                orientation="h",
                width=0.62,
                marker={"color": teinte(couleur, 0.35), "line": {"color": couleur, "width": 1.5}, "pattern": _trame(i, couleur)},
                name=etiquette,
                showlegend=False,
                hoverinfo="text",
                hovertext=f"{etiquette}<br>Pire des cas : {intervalle(*pire)} mm",
            )
        )
        fig.add_trace(
            go.Bar(
                base=[stat[0]],
                x=[stat[1] - stat[0]],
                y=[r],
                orientation="h",
                width=0.26,
                marker={"color": couleur, "line": {"color": TEXTE, "width": 1}},
                name=etiquette,
                showlegend=False,
                hoverinfo="text",
                hovertext=f"{etiquette}<br>± kσ : {intervalle(*stat)} mm",
            )
        )
        lo, hi = max(bande[0], bas), min(bande[1], haut)  # limite absente : le cadre va jusqu'au bord du graphique
        if lo < hi:
            fig.add_trace(
                go.Scatter(
                    x=[lo, hi, hi, lo, lo],
                    y=[r - 0.42, r - 0.42, r + 0.42, r + 0.42, r - 0.42],
                    mode="lines+markers",
                    line={"color": TEXTE, "width": 1.5, "dash": "dot"},
                    marker={"symbol": _SYMBOLES[i % len(_SYMBOLES)], "size": 7, "color": TEXTE, "opacity": [1, 0, 1, 0, 0]},
                    name=etiquette,
                    showlegend=False,
                    hoverinfo="text",
                    hovertext=f"{etiquette}<br>Exigé : {intervalle(*bande)} mm",
                )
            )
    titre = (
        "Plages de jeu par chaîne<br><sup>barre large hachurée : pire des cas · barre étroite pleine : ± kσ · "
        "cadre pointillé : jeu exigé</sup>"
    )
    _finaliser(fig, titre, max(280, 70 * n + 150))
    fig.update_layout(barmode="overlay", margin={"l": 140, "r": 20, "t": 90, "b": 50})
    fig.update_xaxes(title_text="Jeu (mm)", range=[bas, haut])
    fig.update_yaxes(
        tickmode="array",
        tickvals=list(range(n)),
        ticktext=[_h(nom) for _, nom, _ in valides],
        range=[n - 0.5, -0.5],
        showgrid=False,
    )
    pireBas = min(p[0] for p in pires)
    pireHaut = max(p[1] for p in pires)
    description = (
        f"Barres horizontales du jeu de {n} chaîne(s) : plage au pire des cas (barre large) et plage à ± kσ "
        f"(barre étroite), avec le cadre du jeu exigé. Tous les pires cas sont compris entre {fr(pireBas, '.4f')} "
        f"et {fr(pireHaut, '.4f')} mm."
    )
    return fig, description


def _figureCpk(valides: list[tuple[int, str, dict]]) -> tuple[go.Figure, str]:
    titre = "Capabilité Cpk par chaîne"
    avec = [(i, nom, float(b["verdicts"]["cpk"])) for i, nom, b in valides if _fini(b["verdicts"]["cpk"])]
    if not avec:
        message = "Aucun Cpk à comparer : une chaîne sans dispersion ni limite n'a pas de Cpk."
        return _figureVide(titre, message), message
    fig = go.Figure()
    for r, (i, nom, cpk) in enumerate(avec):
        couleur = _COULEURS[i % len(_COULEURS)]
        etiquette = _h(nom, 60)
        fig.add_trace(
            go.Bar(
                x=[cpk],
                y=[r],
                orientation="h",
                width=0.6,
                marker={"color": teinte(couleur, 0.55), "line": {"color": couleur, "width": 1.5}, "pattern": _trame(i, couleur)},
                text=[fr(cpk, ".2f")],
                textposition="outside",
                cliponaxis=False,
                name=etiquette,
                showlegend=False,
                hoverinfo="text",
                hovertext=f"{etiquette}<br>Cpk : {fr(cpk, '.2f')}",
            )
        )
    fig.add_vline(
        x=CPK_CIBLE,
        line={"color": VERMILLON, "width": 2, "dash": "dash"},
        annotation_text=f"seuil {fr(CPK_CIBLE, '.2f')}",
        annotation_position="top",
    )
    _finaliser(fig, titre, max(260, 60 * len(avec) + 140))
    fig.update_layout(margin={"l": 140, "r": 40, "t": 80, "b": 50})
    fig.update_xaxes(title_text="Cpk", rangemode="tozero")
    fig.update_yaxes(
        tickmode="array",
        tickvals=list(range(len(avec))),
        ticktext=[_h(nom) for _, nom, _ in avec],
        range=[len(avec) - 0.5, -0.5],
        showgrid=False,
    )
    pire = min(avec, key=lambda x: x[2])
    dessous = sum(1 for x in avec if x[2] < CPK_CIBLE)
    description = (
        f"Barres des Cpk de {len(avec)} chaîne(s) et ligne de seuil à {fr(CPK_CIBLE, '.2f')}. Le plus faible est "
        f"{fr(pire[2], '.2f')} pour « {pire[1]} » ; {dessous} chaîne(s) sous le seuil."
    )
    return fig, description


def _figureDistributions(valides: list[tuple[int, str, dict]]) -> tuple[go.Figure, str]:
    titre = "Distribution du jeu simulé (Monte-Carlo)"
    avec = [(i, nom, b) for i, nom, b in valides if b["mc"] is not None and len(b["mc"]["J"]) > 1]
    if not avec:
        message = "Pas de simulation Monte-Carlo à tracer : toutes les tolérances sont nulles."
        return _figureVide(titre, message), message
    n = len(avec)
    colonnes = 1 if n == 1 else (2 if n <= 4 else 3)
    rangs = math.ceil(n / colonnes)
    fig = make_subplots(
        rows=rangs, cols=colonnes, subplot_titles=[_h(nom, 28) for _, nom, _ in avec], horizontal_spacing=0.08,
        vertical_spacing=min(0.2, 0.5 / rangs),
    )
    for k, (i, nom, b) in enumerate(avec):
        rang, col = k // colonnes + 1, k % colonnes + 1
        couleur = _COULEURS[i % len(_COULEURS)]
        J = np.asarray(b["mc"]["J"], dtype=float)
        J = J[np.isfinite(J)]
        if J.size < 2 or J.max() == J.min():
            continue
        densite, bords = np.histogram(J, bins=_NB_BACS, density=True)
        centres = (bords[:-1] + bords[1:]) / 2
        fig.add_trace(
            go.Bar(
                x=centres.tolist(),
                y=densite.tolist(),
                width=float(bords[1] - bords[0]),
                marker={"color": teinte(couleur, 0.5), "line": {"color": couleur, "width": 0.5}, "pattern": _trame(i, couleur)},
                name=_h(nom, 60),
                showlegend=False,
                hovertemplate="Jeu %{x:.4f} mm<br>Densité %{y:.3g} /mm<extra></extra>",
            ),
            row=rang,
            col=col,
        )
        mu, sg = float(b["res"]["CF_moy"]), float(b["res"]["CF_sigma"])
        for limite in (b["res"]["condition"]["jmin"], b["res"]["condition"]["jmax"]):
            if math.isfinite(limite) and abs(limite - mu) <= 8 * max(sg, 1e-12):
                fig.add_vline(x=limite, line={"color": TEXTE, "width": 2, "dash": "dash"}, row=rang, col=col)
        fig.update_xaxes(title_text="Jeu (mm)", row=rang, col=col, title_font={"size": 11})
    for rang in range(1, rangs + 1):
        fig.update_yaxes(title_text="Densité (1/mm)", row=rang, col=1, title_font={"size": 11})
    _finaliser(fig, titre + "<br><sup>traits pointillés : limites Jmin et Jmax exigées</sup>", 250 * rangs + 110)
    fig.update_layout(bargap=0, margin={"l": 60, "r": 20, "t": 90, "b": 50})
    fig.update_annotations(font={"size": 12, "color": TEXTE})
    nTirages = min(len(b["mc"]["J"]) for _, _, b in avec)
    description = (
        f"Histogrammes du jeu simulé, un par chaîne ({n} chaîne(s), au moins {nTirages} tirages chacune), avec les "
        "limites Jmin et Jmax exigées en traits pointillés."
    )
    return fig, description


def figuresComparatif(resultat: dict) -> list[dict]:
    """Figures Plotly de la comparaison : plages de jeu, Cpk, distributions Monte-Carlo.

    Entrée : resultat de comparerColonnes, avec sa clé « _bundles » (à appeler avant de la retirer pour la
    sérialisation). Les colonnes en erreur sont ignorées.
    Sortie : liste de dict id (« plages », « cpk », « distributions »), titre, fig (figure Plotly), description
    (texte alternatif en français) ; liste vide si toutes les colonnes sont en erreur.
    Erreur : ValueError si « _bundles » manque.
    """
    valides = _valides(resultat)
    if not valides:
        return []
    sortie = []
    for identifiant, titre, fabrique in (
        ("plages", "Plages de jeu", _figurePlages),
        ("cpk", "Capabilité Cpk", _figureCpk),
        ("distributions", "Distributions du jeu", _figureDistributions),
    ):
        fig, description = fabrique(valides)
        sortie.append({"id": identifiant, "titre": titre, "fig": fig, "description": description})
    return sortie
