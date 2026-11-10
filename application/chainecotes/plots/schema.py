"""Schéma 1D vivant d'une chaîne de cotes : flèches à l'échelle mises bout à bout et cote condition colorée."""

import math

import plotly.graph_objects as go

from chainecotes.core.geometrie import TYPES as TYPES_GEOMETRIE
from chainecotes.plots._common import (
    BLEU,
    GRIS,
    ROUGE,
    TEXTE,
    VERMILLON,
    VERT,
    etatThermique,
    fr,
    intervalle,
    miseEnPage,
    teinte,
)
from chainecotes.services.calcul import apercuChaine

# Largeur minimale visible d'une zone de tolérance, en fraction de l'étendue du dessin
_FRACTION_MIN = 0.008


def _maillonsCalcules(res: dict) -> list[dict]:
    """Maillons d'une saisie valide : nom, signe, cote (mm), écarts (mm), libellé « Alésage 100 H7 »."""
    sortie = []
    for m in res["maillons"]:
        if m["geometrie"]:
            valeur = f"{TYPES_GEOMETRIE[m['geometrie']][1]} {fr(m['es'] - m['ei'], 'g')}"
        elif m["iso"]:
            valeur = f"{fr(m['cote'], 'g')} {m['iso']}"
        elif m["es"] == 0 and m["ei"] == 0:
            valeur = fr(m["cote"], "g")
        else:
            # écarts au dixième de µm : une tolérance répartie (0,279166…) reste lisible
            valeur = f"{fr(m['cote'], 'g')} {fr(round(m['es'], 4), '+g')}/{fr(round(m['ei'], 4), '+g')}"
        signe = 1.0 if m["sens"] == "+" else -1.0
        sortie.append(
            {
                "nom": m["nom"],
                "signe": signe,
                "cote": m["cote"],
                "es": m["es"],
                "ei": m["ei"],
                "libelle": f"{m['nom']} {valeur}",
            }
        )
    return sortie


def _maillonsBruts(probleme: dict) -> list[dict]:
    """Maillons lisibles d'une saisie invalide (cote numérique), sans tolérance : le dessin suit la saisie."""
    sortie = []
    for i, m in enumerate(probleme.get("maillons") or []):
        try:
            cote = float(m.get("cote"))
        except (TypeError, ValueError):
            continue
        if not math.isfinite(cote):
            continue
        nom = str(m.get("nom") or f"Maillon {i + 1}")
        signe = -1.0 if str(m.get("sens", "+")).strip() in ("-", "−") else 1.0
        sortie.append(
            {"nom": nom, "signe": signe, "cote": cote, "es": 0.0, "ei": 0.0, "libelle": f"{nom} {fr(cote, 'g')}"}
        )
    return sortie


def _fleche(
    fig: go.Figure, notes: list, x0: float, x1: float, y: float, couleur: str, nom: str, largeur: float = 2.5
) -> None:
    """Flèche horizontale de x0 vers x1 à l'ordonnée y (point si longueur nulle) ; nom repère la flèche.

    L'annotation est ajoutée à `notes` (affectée en bloc à la figure : add_annotation revalide toutes les
    annotations déjà présentes, soit un coût quadratique avec le nombre de maillons).
    """
    notes.append(
        {
            "name": nom,
            "x": x1,
            "y": y,
            "ax": x0,
            "ay": y,
            "xref": "x",
            "yref": "y",
            "axref": "x",
            "ayref": "y",
            "text": "",
            "showarrow": True,
            "arrowhead": 2,
            "arrowsize": 1.1,
            "arrowwidth": largeur,
            "arrowcolor": couleur,
        }
    )
    if x1 == x0:
        fig.add_trace(go.Scatter(x=[x0], y=[y], mode="markers", marker={"color": couleur, "size": 8}, showlegend=False))


def figureSchema(probleme: dict, apercu: dict | None = None) -> tuple[go.Figure, str]:
    """Schéma 1D vivant : une flèche à l'échelle par maillon, bout à bout depuis l'origine, puis la cote condition.

    Entrées : probleme (dict condition, reglages, maillons), apercu (sortie de apercuChaine, calculée si None).
    Sortie : (figure Plotly, légende) ; abscisses en mm, une ligne par maillon (escalier vertical) ; flèche de la
    cote condition verte si le pire cas tient [Jmin ; Jmax], rouge sinon, grise si la saisie est invalide.
    Les flèches portent le nom « maillon:i » (i à partir de 0) ou « condition ».
    """
    if apercu is None:
        apercu = apercuChaine(probleme)
    erreur = apercu.get("erreur")
    maillons = _maillonsBruts(probleme) if erreur else _maillonsCalcules(apercu["res"])
    n = len(maillons)

    # Positions : maillon i sur la ligne y = −i, de x0 à x0 + signe·cote
    xs, debut = [0.0], 0.0
    for m in maillons:
        m["x0"], m["x1"] = debut, debut + m["signe"] * m["cote"]
        bornes = (m["x0"] + m["signe"] * (m["cote"] + m["ei"]), m["x0"] + m["signe"] * (m["cote"] + m["es"]))
        m["zone"] = (min(bornes), max(bornes))
        xs += [m["x1"], *m["zone"]]
        debut = m["x1"]
    etendue = (max(xs) - min(xs)) or 1.0
    largeurMin = _FRACTION_MIN * etendue
    yCond = -n - 0.4

    fig = go.Figure()
    formes, notes = [], []  # affectées en bloc à la fin
    nElargies = 0
    for i, m in enumerate(maillons):
        y = -float(i)
        couleur = BLEU if m["signe"] > 0 else VERMILLON
        it = m["zone"][1] - m["zone"][0]
        if it > 0:
            lo, hi = m["zone"]
            if it < largeurMin:
                centre = (lo + hi) / 2
                lo, hi = centre - largeurMin / 2, centre + largeurMin / 2
                nElargies += 1
            formes.append(
                {
                    "type": "rect",
                    "x0": lo,
                    "x1": hi,
                    "y0": y - 0.28,
                    "y1": y + 0.28,
                    "line": {"color": couleur, "width": 1},
                    "fillcolor": teinte(couleur, 0.3),
                }
            )
        _fleche(fig, notes, m["x0"], m["x1"], y, couleur, f"maillon:{i}")
        # texte calé sur le bout de la flèche côté bord du dessin : un long libellé ne sort plus du cadre
        aGauche = (m["x0"] + m["x1"]) / 2 < (min(xs) + max(xs)) / 2
        notes.append(
            {
                "x": min(m["x0"], m["x1"]) if aGauche else max(m["x0"], m["x1"]),
                "xanchor": "left" if aGauche else "right",
                "y": y,
                "yshift": 11,
                "text": m["libelle"],
                "showarrow": False,
                "font": {"size": 12, "color": TEXTE},
            }
        )
        yBas = -float(i + 1) if i + 1 < n else yCond
        formes.append(
            {
                "type": "line",
                "x0": m["x1"],
                "x1": m["x1"],
                "y0": y,
                "y1": yBas,
                "line": {"color": GRIS, "width": 1, "dash": "dot"},
            }
        )
    formes.append({"type": "line", "x0": 0, "x1": 0, "y0": 0.4, "y1": yCond, "line": {"color": TEXTE, "width": 1.5}})

    # Cote condition : de l'origine à la fin de la chaîne (vers la gauche si le jeu nominal est négatif)
    fin = maillons[-1]["x1"] if maillons else 0.0
    nomCond = str((probleme.get("condition") or {}).get("nom") or "Jeu J")
    if erreur:
        couleurCond, texteCond = GRIS, f"{nomCond} : saisie invalide"
        legende = f"Schéma provisoire, saisie invalide : {erreur}"
        notes.append(
            {
                "x": 0.5,
                "y": 1.0,
                "xref": "paper",
                "yref": "paper",
                "yanchor": "bottom",
                "text": f"Saisie invalide : {erreur}",
                "showarrow": False,
                "font": {"size": 12, "color": ROUGE},
                "bgcolor": "white",
                "bordercolor": ROUGE,
                "borderwidth": 1,
            }
        )
    else:
        res, pire = apercu["res"], apercu["verdicts"]["pireCas"]
        c = res["condition"]
        couleurCond = VERT if pire["ok"] else ROUGE
        texteCond = f"{res['condition']['nom']} = {fr(fin)} mm, pire cas {intervalle(pire['min'], pire['max'])}"
        nature = "jeu" if fin >= 0 else "serrage (jeu négatif)"
        legende = (
            f"{res['condition']['nom']} nominal {fr(fin)} mm ({nature}) ; au pire des cas "
            f"{intervalle(pire['min'], pire['max'])} mm, {'dans' if pire['ok'] else 'hors de'} "
            f"{intervalle(c['jmin'], c['jmax'])} mm"
        )
        if etat := etatThermique(res):
            legende += (
                f" {etat}, avec un jeu nominal de {fr(res['CF_nom'])} mm à cet état (schéma tracé aux cotes nominales)"
            )
        if nElargies:
            legende += f" ; {nElargies} zone(s) de tolérance élargie(s) pour rester visible(s)"
        legende += "."
    _fleche(fig, notes, 0.0, fin, yCond, couleurCond, "condition", 3.5)
    marge = 0.08 * etendue
    # ancrée au bord gauche : la flèche du jeu est souvent trop courte pour porter son texte
    notes.append(
        {
            "x": 0.01,
            "xref": "paper",
            "y": yCond,
            "yshift": -16,
            "xanchor": "left",
            "text": f"<b>{texteCond}</b>",
            "showarrow": False,
            "font": {"size": 12, "color": couleurCond},
        }
    )
    fig.update_layout(shapes=formes, annotations=notes)

    miseEnPage(fig, "Schéma de la chaîne (cotes nominales à l'échelle)", min(1100, max(320, 150 + 30 * (n + 1))))
    fig.update_xaxes(title="Position (mm)", range=[min(xs) - marge, max(xs) + marge], zeroline=False)
    fig.update_yaxes(visible=False, range=[yCond - 0.8, 0.8])
    fig.update_layout(showlegend=False)
    return fig, legende
