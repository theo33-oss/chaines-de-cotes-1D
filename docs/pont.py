"""Pont entre la page web (JavaScript) et le calcul Python de l'application : trois fonctions, entrées et sorties en JSON.

Le navigateur les appelle par Pyodide ; elles servent aussi aux essais en Python ordinaire (essai_pont.py).
"""

import json
import math

from chainecotes.core.errors import ErreurChaine
from chainecotes.core.nombres import fr
from chainecotes.plots.graphiques import figureComparaison, figureDistribution, figureMonteCarlo, figurePareto
from chainecotes.plots.schema import figureSchema
from chainecotes.services.calcul import apercuChaine, calculerChaine
from chainecotes.services.conclusion import conclusionEtude
from chainecotes.services.exemples import chargerExemple, listeExemples

N_TIRAGES = 100_000  # plus léger que le bureau (200 000) : la page tourne sur le processeur du visiteur
FIGURES = (
    ("schema", "Schéma", None),
    ("comparaison", "Comparaison des méthodes", figureComparaison),
    ("pareto", "Pareto", figurePareto),
    ("montecarlo", "Monte-Carlo", figureMonteCarlo),
    ("distribution", "Distribution", figureDistribution),
)


def exemples() -> str:
    """Liste des exemples (id, titre, description) en JSON."""
    return json.dumps([{k: e[k] for k in ("id", "titre", "description") if k in e} for e in listeExemples()])


def charger(identifiant: str) -> str:
    """Problème d'un exemple en JSON : une limite absente (infini) est écrite null."""
    return json.dumps(chargerExemple(identifiant), allow_nan=False)


def _vide(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def _nettoyer(p: dict) -> dict:
    """Cases vides de la page (texte vide) → None, comme les cases vides du tableau de l'application de bureau."""
    condition = {k: (None if _vide(v) else v) for k, v in p.get("condition", {}).items()}
    reglages = {k: (None if _vide(v) else v) for k, v in p.get("reglages", {}).items()}
    maillons = [{k: v for k, v in m.items() if not _vide(v)} for m in p.get("maillons", [])]
    return {"condition": condition, "reglages": reglages, "maillons": maillons}


def _fini(v) -> bool:
    return isinstance(v, float) and math.isfinite(v)


def calculer(texte: str) -> str:
    """Calcul complet d'un problème (JSON) : verdict, conseil, chiffres clés, figures Plotly (JSON) et avertissements.

    Sortie JSON : {"erreur": message} si la saisie est invalide, sinon niveau, titre, conseil, details, metriques
    ([libellé, valeur]), figures ([{id, titre, legende, fig}], fig = JSON Plotly) et avertissements.
    """
    try:
        probleme = _nettoyer(json.loads(texte))
        apercu = apercuChaine(probleme)
        if "erreur" in apercu:
            return json.dumps({"erreur": apercu["erreur"]})
        bundle = calculerChaine(probleme, n=N_TIRAGES)
    except ErreurChaine as e:
        return json.dumps({"erreur": e.message})
    except (ValueError, TypeError, KeyError) as e:
        return json.dumps({"erreur": f"Saisie incomplète : {e}"})
    v, conclusion = bundle["verdicts"], conclusionEtude(bundle)
    figures = []
    for ident, titre, fabrique in FIGURES:
        fig, legende = figureSchema(probleme, apercu) if fabrique is None else fabrique(bundle)
        figures.append({"id": ident, "titre": titre, "legende": legende, "fig": json.loads(fig.to_json())})
    return json.dumps(
        {
            "niveau": conclusion["niveau"],
            "titre": conclusion["titre"],
            "conseil": conclusion["conseils"][0] if conclusion["conseils"] else "",
            "details": conclusion["details"],
            "metriques": [
                ["Jeu mini (pire des cas)", f"{fr(v['pireCas']['min'])} mm"],
                ["Jeu maxi (pire des cas)", f"{fr(v['pireCas']['max'])} mm"],
                ["Cpk", fr(v["cpk"], ".3g")],
                ["Hors tolérance (formule)", f"{fr(v['ppm'], '.3g')} ppm" if _fini(v["ppm"]) else "—"],
            ],
            "figures": figures,
            "avertissements": bundle["avertissements"],
        },
        allow_nan=False,
    )
