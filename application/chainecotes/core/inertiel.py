"""Méthodes statistiques complémentaires de la tradition française et industrielle : Bender et tolérancement inertiel.

- Statistique majorée de Bender : tolérance de fermeture 1,5 · √Σ (|a_i| · IT_i / 2)², entre le pire des cas et la somme
  quadratique pure ; le coefficient 1,5 couvre les décentrages et l'écart à la loi normale.
- Tolérancement inertiel (Pillet) : l'inertie d'une cote est I = √(σ² + δ²), δ étant l'écart de sa moyenne à la cible.
  Les inerties s'ajoutent quadratiquement dans le jeu : I_J = √(Σ a_i² I_i²). Une tolérance IT correspond à l'inertie
  maximale I_max = IT / 6 (même échelle que le Cp : Cpi = I_max / I, égal à Cp pour un procédé centré).
Aucune de ces méthodes ne change le calcul principal. Ce module n'importe ni streamlit ni plotly.
"""

import math

import numpy as np

from chainecotes.core.chaine import TOL_COMPARAISON

COEFFICIENT_BENDER = 1.5


def verdictBender(res: dict) -> dict:
    """Plage du jeu par la statistique majorée de Bender, centrée sur le jeu moyen.

    Entrée : res (sortie de solveurChaine).
    Sortie : dict demi (mm, 1,5 · √Σ (|a_i| IT_i / 2)²), min, max (mm), ok (bool : dans [Jmin ; Jmax]).
    """
    t = np.abs(np.asarray(res["coef"], dtype=float)) * np.asarray(res["IT"], dtype=float) / 2
    demi = min(COEFFICIENT_BENDER * float(np.sqrt(np.sum(t**2))), float(np.sum(t)))  # jamais au-delà du pire des cas
    c, mu = res["condition"], res["CF_moy"]
    return {
        "demi": demi,
        "min": mu - demi,
        "max": mu + demi,
        "ok": bool(mu - demi >= c["jmin"] - TOL_COMPARAISON and mu + demi <= c["jmax"] + TOL_COMPARAISON),
    }


def analyseInertielle(res: dict) -> dict:
    """Inertie du jeu, indicateur Cpi et répartition inertielle des tolérances.

    Entrée : res (sortie de solveurChaine ; σ_i et moyennes mesurées de l'atelier sont utilisés quand ils existent).
    Sortie : dict inertieJeu (mm, √(σ_J² + δ_J²)), cible (mm : milieu de [Jmin ; Jmax], sinon jeu moyen), ecartCible
    (δ_J, mm : moyenne du procédé − cible), inertieMax (mm, (Jmax − Jmin) / 6 ; nan sans deux limites), cpi (inertieMax
    / inertieJeu ; nan si indéfini) et liens, liste de dict :
    nom, sigma (mm, de la cote), ecart (mm, moyenne − cote moyenne), inertie (mm), inertieAllouee (mm,
    I_max / (|a_i|·√n)), itInertiel (6 · inertieAllouee, mm), itPireCas (mm : IT égal pour tous au pire des cas,
    nan sans deux limites).
    """
    c, n = res["condition"], len(res["Nom"])
    coef = np.asarray(res["coef"], dtype=float)
    sigma_x = np.where(coef != 0, np.asarray(res["sigma_i"], dtype=float) / np.where(coef != 0, np.abs(coef), 1), 0.0)
    moy = np.asarray(res["moyenne_reelle"], dtype=float)
    ecart = np.where(np.isnan(moy), 0.0, moy - np.asarray(res["C_moy"], dtype=float))
    inertie = np.sqrt(sigma_x**2 + ecart**2)
    deuxLimites = math.isfinite(c["jmin"]) and math.isfinite(c["jmax"])
    cible = (c["jmin"] + c["jmax"]) / 2 if deuxLimites else res["CF_moy"]
    ecartJeu = res["CF_moy_proc"] - cible
    inertieJeu = math.hypot(res["CF_sigma"], ecartJeu)
    imax = (c["jmax"] - c["jmin"]) / 6 if deuxLimites else math.nan
    liens = []
    for i, nom in enumerate(res["Nom"]):
        a = abs(coef[i])
        alloue = imax / (a * math.sqrt(n)) if a > 0 else math.nan
        liens.append(
            {
                "nom": nom,
                "sigma": float(sigma_x[i]),
                "ecart": float(ecart[i]),
                "inertie": float(inertie[i]),
                "inertieAllouee": alloue,
                "itInertiel": 6 * alloue,
                "itPireCas": (c["jmax"] - c["jmin"]) / (n * a) if deuxLimites and a > 0 else math.nan,
            }
        )
    return {
        "inertieJeu": inertieJeu,
        "cible": cible,
        "ecartCible": ecartJeu,
        "inertieMax": imax,
        "cpi": imax / inertieJeu if deuxLimites and inertieJeu > 0 else math.nan,
        "liens": liens,
    }
