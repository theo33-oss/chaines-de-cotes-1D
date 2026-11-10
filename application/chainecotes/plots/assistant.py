"""Figure de l'assistant : une ligne par pièce, les contacts en pointillés, la chaîne retenue en couleur."""

import plotly.graph_objects as go

from chainecotes.core.construction import positions
from chainecotes.plots._common import BLEU, GRIS, VERMILLON, fr, miseEnPage, teinte


def figureConstruction(
    cotes: list[dict], contacts: list[tuple[str, str]], depart: str, arrivee: str, chaine: dict | None = None
) -> tuple[go.Figure, str]:
    """Plan à plat des pièces dans le sens de la chaîne, avec les cotes, les contacts et le jeu.

    Entrées : cotes et contacts (sortie de core.construction.lireSaisie), depart et arrivee (surfaces
    « Pièce.surface »),
    chaine (un élément de construireChaines, ou None : aucune cote en couleur).
    Sortie : (figure Plotly, légende en français). Positions nominales en mm depuis la surface de départ ;
    les pièces non reliées à la surface de départ sont placées à part (grisées dans la légende).
    """
    pos, incoherences = positions(cotes, contacts, depart)
    pieces = list(dict.fromkeys(c["piece"] for c in cotes))
    ligne = {p: i for i, p in enumerate(pieces)}
    retenues = set(chaine["cotes"]) if chaine else set()
    sens = {}
    if chaine:
        for m, i in zip(chaine["maillons"], chaine["cotes"], strict=True):
            sens[i] = m["sens"]
    fig = go.Figure()
    for p in pieces:
        xs = [pos[n] for c in cotes if c["piece"] == p for n in (c["noeudDe"], c["noeudVers"])]
        fig.add_trace(
            go.Scatter(
                x=[min(xs), max(xs)],
                y=[ligne[p]] * 2,
                mode="lines",
                line={"color": teinte(GRIS, 0.35), "width": 14},
                hoverinfo="skip",
                showlegend=False,
            )
        )
    for i, c in enumerate(cotes):
        y = ligne[c["piece"]]
        x0, x1 = pos[c["noeudDe"]], pos[c["noeudVers"]]
        couleur = (VERMILLON if sens.get(i) == "+" else BLEU) if i in retenues else teinte(GRIS, 0.9)
        fig.add_trace(
            go.Scatter(
                x=[x0, x1],
                y=[y, y],
                mode="lines+markers+text",
                line={"color": couleur, "width": 5 if i in retenues else 2},
                marker={"size": 9, "color": couleur},
                text=["", f"{fr(c['cote'], 'g')}"],
                textposition="top center",
                hovertemplate=f"{c['piece']} : {c['de']} → {c['vers']}<br>cote {fr(c['cote'], 'g')} mm<extra></extra>",
                showlegend=False,
            )
        )
        fig.add_annotation(x=x0, y=y, text=c["de"], showarrow=False, yshift=-16, font={"size": 11})
        fig.add_annotation(x=x1, y=y, text=c["vers"], showarrow=False, yshift=-16, font={"size": 11})
    for a, b in contacts:
        pa = next((c for c in cotes if a in (c["noeudDe"], c["noeudVers"])), None)
        pb = next((c for c in cotes if b in (c["noeudDe"], c["noeudVers"])), None)
        if pa and pb:
            fig.add_trace(
                go.Scatter(
                    x=[pos[a], pos[b]],
                    y=[ligne[pa["piece"]], ligne[pb["piece"]]],
                    mode="lines",
                    line={"color": GRIS, "width": 1.5, "dash": "dot"},
                    hovertemplate=f"Contact {a} / {b}<extra></extra>",
                    showlegend=False,
                )
            )
    jeu = pos[arrivee] - pos[depart]
    haut = -0.9
    fig.add_trace(
        go.Scatter(
            x=[pos[depart], pos[arrivee]],
            y=[haut, haut],
            mode="lines+markers+text",
            line={"color": "#17692F", "width": 3},
            marker={"size": 10, "symbol": "diamond", "color": "#17692F"},
            text=["", f"J = {fr(jeu, 'g')} mm"],
            textposition="top center",
            hoverinfo="skip",
            showlegend=False,
        )
    )
    miseEnPage(fig, "Plan de la chaîne (positions nominales)", 150 + 70 * len(pieces))
    fig.update_yaxes(
        tickvals=list(range(len(pieces))),
        ticktext=pieces,
        autorange="reversed",
        range=[-1.6, len(pieces) - 0.4],
        gridcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(title_text="Position le long de l'axe de la chaîne (mm)")
    legende = (
        "Une ligne par pièce ; les segments sont les cotes, les pointillés les contacts. En couleur, la chaîne retenue "
        "(rouge : cote qui s'ajoute au jeu, violet : cote qui s'en retranche) ; en vert, le jeu étudié "
        f"de {depart} à {arrivee}."
    )
    if incoherences:
        legende += " Cotes redondantes incompatibles : " + " ; ".join(incoherences[:3]) + "."
    return fig, legende
