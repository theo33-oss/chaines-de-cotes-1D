"""Orchestration d'un calcul complet de chaîne de cotes (solveur, verdicts, Monte-Carlo, thermique)."""

import copy
import math

import numpy as np

from chainecotes.core.chaine import (
    contributions,
    jeuSelonTemperature,
    ppmExact,
    risqueSelonCp,
    solveurChaine,
    verdicts,
)
from chainecotes.core.errors import ErreurChaine
from chainecotes.core.montecarlo import GRAINE_DEFAUT, N_DEFAUT, simulerMonteCarlo
from chainecotes.core.nombres import fr


def _avertissements(res: dict) -> list[str]:
    """Textes à afficher avec les résultats : écarts connus avec la norme, domaines d'emploi, cas limites."""
    textes = []
    for m in res["maillons"]:
        if m["avertissement"]:
            textes.append(f"{m['nom']} : {m['avertissement']}")
        if m["horsDomaine"]:
            textes.append(f"{m['nom']} ({m['materiau']}, {fr(m['tservice'], 'g')} °C) : hors domaine, {m['motif']}.")
    autres = sorted({m["loi"] for m in res["maillons"]} - {"normale"})
    if autres:
        textes.append(
            f"Loi non normale utilisée ({', '.join(autres)}) : Cp et Cpk par formule supposent un jeu quasi "
            "normal (théorème central limite) ; avec peu de maillons ou un maillon dominant, ils sont approchés. "
            "Le taux hors tolérance (ppm) est calculé exactement selon la loi de chaque maillon ; la formule "
            "normale n'est donnée qu'à titre indicatif et la simulation Monte-Carlo le recoupe."
        )
    if not res["CF_sigma"] > 0:
        textes.append("Toutes les tolérances sont nulles : pas de dispersion, pas de calcul statistique.")
    c = res["condition"]
    if not math.isfinite(c["jmin"]) and not math.isfinite(c["jmax"]):
        textes.append("Aucune limite sur la cote condition : pas de verdict ni de taux hors tolérance.")
        if res["decentrage"] > 0:
            textes.append("Décentrage sans effet : aucune limite finie vers laquelle décaler la moyenne.")
    return textes


def calculerChaine(probleme: dict, monteCarlo: bool = True, n: int = N_DEFAUT, graine: int = GRAINE_DEFAUT) -> dict:
    """Calcul complet d'un problème : solveur, verdicts, contributions, risque, Monte-Carlo, jeu selon T.

    Entrées : probleme (dict condition, reglages, maillons), monteCarlo (bool), n (tirages), graine (entier).
    Sortie : dict probleme, res (solveurChaine), decentrage (σ_J, réglage) et decalage (mm, décalage appliqué à la
    moyenne du jeu pour Cpk, ppm et Monte-Carlo), verdicts, contributions, risque (risqueSelonCp),
    mc (simulerMonteCarlo ou None si σ = 0 ou monteCarlo=False), jeuT (jeuSelonTemperature de Tref − 100 à
    Tref + 200 °C, ou None si aucun maillon n'a de coefficient de dilatation), avertissements (liste de textes).
    Erreur : ErreurChaine si la saisie est invalide ou la chaîne non fermée.
    """
    res = solveurChaine(probleme)
    mc = simulerMonteCarlo(res, n, graine) if monteCarlo and res["CF_sigma"] > 0 else None
    jeuT = None
    if np.any(res["alpha"] != 0) or any(m["materiau"] for m in res["maillons"]):
        jeuT = jeuSelonTemperature(res, np.linspace(res["Tref"] - 100, res["Tref"] + 200, 301))
    return {
        "probleme": copy.deepcopy(probleme),
        "res": res,
        "decentrage": res["decentrage"],
        "decalage": res["decalage"],
        "verdicts": verdicts(res),
        "ppmExact": ppmExact(res),  # None si tous les maillons sont normaux : verdicts["ppm"] est alors exact
        "contributions": contributions(res),
        "risque": risqueSelonCp(res),
        "mc": mc,
        "jeuT": jeuT,
        "avertissements": _avertissements(res),
    }


def apercuChaine(probleme: dict) -> dict:
    """Calcul léger pour le schéma vivant et les curseurs (sans Monte-Carlo ni balayage en température).

    Entrée : probleme (dict condition, reglages, maillons).
    Sortie : dict res, verdicts, avertissements ; ou dict erreur (message) si la saisie est invalide.
    Ne lève jamais d'exception : le schéma se dessine même pendant la saisie.
    """
    try:
        res = solveurChaine(probleme)
    except ErreurChaine as e:
        return {"erreur": e.message}
    except (TypeError, ValueError, KeyError) as e:
        return {"erreur": f"Saisie incomplète : {e}"}
    return {"res": res, "verdicts": verdicts(res), "avertissements": _avertissements(res)}
