"""Outils communs aux figures : couleurs du thème, nombres à la française, mise en page, figure explicative."""

import math

import plotly.graph_objects as go

from chainecotes.core.nombres import fr

# Couleurs de .streamlit/config.toml : Twilight Purple de la palette, puis Okabe-Ito (sûres pour les daltoniens)
BLEU = "#5C4B99"
VERMILLON = "#D55E00"
VERT_OI = "#009E73"
ORANGE = "#E69F00"
ROSE = "#CC79A7"
VERT = "#17692F"
ROUGE = "#B3141F"
GRIS = "#8E86AA"
TEXTE = "#3D246C"  # Midnight Violet
GRILLE = "#E2DDF1"
FOND_FIGURE = "#FFF8F3"  # blanc chaud : les figures restent des cartes claires sur la page Vanilla Peach


def teinte(hexa: str, alpha: float) -> str:
    """Couleur CSS rgba() d'une couleur « #RRVVBB » avec une transparence.

    Entrées : hexa (texte « #RRVVBB »), alpha (entre 0 et 1). Sortie : texte « rgba(r,v,b,alpha) ».
    """
    r, v, b = (int(hexa[i : i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r},{v},{b},{alpha:g})"


def intervalle(lo: float, hi: float, fmt: str = ".4f") -> str:
    """Intervalle écrit à la française, ouvert du côté infini : « [1,0300 ; 1,0600] », « [0,0000 ; +∞[ ».

    Entrées : lo, hi (mm, infinis acceptés), fmt (format Python). Sortie : texte.
    """
    gauche = "]" if math.isinf(lo) else "["
    droite = "[" if math.isinf(hi) else "]"
    return f"{gauche}{fr(lo, fmt)} ; {fr(hi, fmt)}{droite}"


def etatThermique(res: dict) -> str:
    """Mention de l'état en service (comme etat() de graphiques.m), vide si aucun effet thermique.

    Entrée : res (sortie de solveurChaine).
    Sortie : texte « en service (T = 120 °C) », « en service (T par cote) » ou « ».
    """
    if not res["thermique_actif"]:
        return ""
    if res["mode_thermique"] == "par_cote":
        return "en service (T par cote)"
    return f"en service (T = {fr(res['reglages']['tservice'], 'g')} °C)"


def miseEnPage(fig: go.Figure, titre: str, hauteur: int = 420) -> go.Figure:
    """Mise en page commune : fond blanc, police lisible, marges réduites, légende horizontale sous le titre.

    Entrées : fig (figure Plotly), titre (texte HTML), hauteur (pixels, adaptée au téléphone).
    Sortie : la même figure, modifiée en place.
    """
    fig.update_layout(
        title={"text": titre, "x": 0.01, "xanchor": "left", "font": {"size": 15}},
        height=hauteur,
        margin={"l": 55, "r": 20, "t": 70, "b": 50},
        paper_bgcolor=FOND_FIGURE,
        plot_bgcolor=FOND_FIGURE,
        font={"family": "Source Sans Pro, Arial, sans-serif", "size": 13, "color": TEXTE},
        legend={"orientation": "h", "x": 0, "y": 1.0, "yanchor": "bottom", "bgcolor": "rgba(255,255,255,0.8)"},
        hoverlabel={"bgcolor": "white"},
    )
    fig.update_xaxes(gridcolor=GRILLE, zerolinecolor=GRIS, linecolor=GRIS, showline=True)
    fig.update_yaxes(gridcolor=GRILLE, zerolinecolor=GRIS, linecolor=GRIS, showline=True)
    return fig


def figureMessage(titre: str, message: str) -> tuple[go.Figure, str]:
    """Figure explicative sans données (ex. pas de Monte-Carlo, pas d'effet thermique).

    Entrées : titre, message (textes). Sortie : (figure avec le message au centre, légende = message).
    """
    fig = go.Figure()
    fig.add_annotation(
        x=0.5, y=0.5, xref="paper", yref="paper", text=message, showarrow=False, font={"size": 14, "color": GRIS}
    )
    miseEnPage(fig, titre, 260)
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig, message
