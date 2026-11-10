"""Schéma des zones de tolérance d'un ajustement ISO 286 (alésage et arbre autour de la cote nominale)."""

import plotly.graph_objects as go

from chainecotes.core.ajustement import pieces
from chainecotes.plots._common import BLEU, GRIS, VERMILLON, fr, miseEnPage, teinte


def figureZones(designation: str, cote: float) -> tuple[go.Figure, str]:
    """Schéma simple des zones de tolérance de l'alésage et de l'arbre autour de la ligne zéro (cote nominale).

    Entrées : designation (« H7/g6 »), cote (mm). Sortie : (figure Plotly, légende) ; écarts en µm.
    Erreur : ErreurChaine si la désignation est illisible.
    """
    trou, arbre = pieces(designation, cote)
    fig = go.Figure()
    for piece, nom, couleur in ((trou, "Alésage", BLEU), (arbre, "Arbre", VERMILLON)):
        es, ei = piece["es"] * 1000, piece["ei"] * 1000
        fig.add_trace(
            go.Bar(
                x=[f"{nom} {piece['designation'].split()[-1]}"],
                y=[max(es - ei, 0.2)],  # largeur minimale visible si la tolérance est nulle
                base=[ei],
                marker={"color": teinte(couleur, 0.55), "line": {"color": couleur, "width": 2}},
                name=nom,
                hovertemplate=f"{nom} : de {fr(ei, 'g')} à {fr(es, 'g')} µm<extra></extra>",
                showlegend=False,
            )
        )
    fig.add_hline(
        y=0, line={"color": GRIS, "width": 2}, annotation_text="cote nominale", annotation_position="top left"
    )
    miseEnPage(fig, f"Zones de tolérance de {designation} à {fr(cote, 'g')} mm", 380)
    fig.update_yaxes(title_text="Écart par rapport à la cote nominale (µm)")
    fig.update_layout(bargap=0.55)
    jeuMini = round(trou["ei"] - arbre["es"], 9)
    jeuMaxi = round(trou["es"] - arbre["ei"], 9)
    return fig, (
        f"Alésage de {fr(trou['ei'] * 1000, 'g')} à {fr(trou['es'] * 1000, 'g')} µm, arbre de "
        f"{fr(arbre['ei'] * 1000, 'g')} à {fr(arbre['es'] * 1000, 'g')} µm : jeu de {fr(jeuMini, 'g')} à "
        f"{fr(jeuMaxi, 'g')} mm."
    )
