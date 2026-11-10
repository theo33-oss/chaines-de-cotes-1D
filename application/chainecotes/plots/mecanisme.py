"""Figure du mécanisme : comparaison des Cpk de toutes les chaînes avec une ligne de seuil (Plotly, sans Streamlit)."""

import plotly.graph_objects as go

from chainecotes.plots._common import GRIS, ROUGE, VERMILLON, VERT, figureMessage, fr, miseEnPage

TITRE = "Capabilité Cpk par chaîne"


def figureCpkMecanisme(lignes: list[dict], seuil: float = 1.33) -> tuple[go.Figure, str]:
    """Barres horizontales des Cpk (une par chaîne) et ligne verticale du seuil de capabilité.

    Entrées : lignes (liste de dicts nom, cpk : sortie « lignes » de calculerMecanisme), seuil (Cpk minimal visé,
    sans unité). Une barre verte atteint le seuil, une barre rouge est en dessous ; une chaîne sans Cpk défini
    (erreur de calcul, σ nul) n'a pas de barre mais reste listée.
    Sortie : (figure, légende en français : pire Cpk, nombre de chaînes sous le seuil). Si aucune chaîne n'a de Cpk :
    figure explicative sans données.
    """
    avec = [x for x in lignes if x["cpk"] is not None]
    if not avec:
        return figureMessage(TITRE, "Aucun Cpk à comparer : une chaîne sans dispersion ou en erreur n'a pas de Cpk.")
    inverse = lignes[::-1]  # la première chaîne en haut
    valeurs = [x["cpk"] for x in inverse]
    couleurs = [GRIS if v is None else (VERT if v >= seuil else ROUGE) for v in valeurs]
    textes = ["sans Cpk" if v is None else fr(v, ".2f") for v in valeurs]
    fig = go.Figure(
        go.Bar(
            x=[0 if v is None else v for v in valeurs],
            y=[x["nom"] for x in inverse],
            orientation="h",
            marker={"color": couleurs},
            text=textes,
            textposition="outside",
            hovertemplate="%{y} : Cpk %{text}<extra></extra>",
        )
    )
    fig.add_vline(
        x=seuil,
        line={"color": VERMILLON, "width": 2, "dash": "dash"},
        annotation_text=f"seuil {fr(seuil, '.2f')}",
        annotation_position="top",
    )
    miseEnPage(fig, TITRE, max(260, 60 * len(inverse) + 130))
    fig.update_xaxes(title_text="Cpk", rangemode="tozero")
    fig.update_layout(showlegend=False)
    pire = min(avec, key=lambda x: x["cpk"])
    dessous = sum(1 for x in avec if x["cpk"] < seuil)
    return fig, (
        f"Pire Cpk : {fr(pire['cpk'], '.2f')} pour « {pire['nom']} » ; {dessous} chaîne(s) sous le seuil de "
        f"{fr(seuil, '.2f')} sur {len(avec)} avec Cpk."
    )
