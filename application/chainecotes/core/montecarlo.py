"""Simulation Monte-Carlo d'une chaîne de cotes (port de graph_montecarlo de graphiques.m).

Chaque maillon est tiré au hasard autour de sa cote moyenne : loi normale d'écart-type IT/(2k) (comme MATLAB)
loi uniforme sur [C_moy − IT/2 ; C_moy + IT/2] ou loi triangulaire symétrique sur le même intervalle (ajouts).
Un maillon à écart type mesuré (res["sigma_reel"]) suit une loi normale de cet écart type, quelle que soit sa loi.
Le décalage du procédé (res["decalage"], mm : décentrage et moyennes mesurées) est ajouté à chaque tirage.
Le jeu de chaque tirage est Σ a_i · X_i.
Le générateur est fixé (graine) : le résultat est reproductible. Il diffère des tirages MATLAB (randn de MATLAB et
numpy n'utilisent pas le même algorithme) ; seules les statistiques sont comparables.
"""

import math

import numpy as np

from chainecotes.core.chaine import TOL_COMPARAISON, capabilites

N_DEFAUT = 200_000
GRAINE_DEFAUT = 1


def simulerMonteCarlo(res: dict, n: int = N_DEFAUT, graine: int = GRAINE_DEFAUT) -> dict:
    """Tire n assemblages virtuels et compte ceux dont le jeu sort de la cote condition.

    Entrées : res (sortie de solveurChaine), n (nombre de tirages), graine (entier, générateur numpy PCG64).
    Sortie : dict J (np.ndarray float64 des jeux, mm), n, graine, moyenne, ecartType (mm), nHors (tirages hors
    [jmin ; jmax]), tauxHors (fraction), ppm, resolutionPpm (10⁶/n), cp, cpk (calculés sur les tirages),
    quantiles (dict 0.135 %, 50 %, 99.865 % en mm).
    """
    n = int(n)
    rng = np.random.default_rng(graine)
    k = res["k_sigma"]
    cmoy, it, a = np.asarray(res["C_moy"]), np.asarray(res["IT"]), np.asarray(res["coef"])
    J = np.zeros(n)
    mesure = np.asarray(res["sigma_reel"], dtype=float)
    for i, loi in enumerate(res["loi"]):
        if not np.isnan(mesure[i]):
            x = cmoy[i] + mesure[i] * rng.standard_normal(n)
        elif loi == "triangulaire":
            h = it[i] / 2
            x = rng.triangular(cmoy[i] - h, cmoy[i], cmoy[i] + h, n) if h > 0 else np.full(n, cmoy[i])
        elif loi == "uniforme":
            x = rng.uniform(cmoy[i] - it[i] / 2, cmoy[i] + it[i] / 2, n)
        else:
            x = cmoy[i] + it[i] / (2 * k) * rng.standard_normal(n)
        J += a[i] * x
    J += res["decalage"]
    c = res["condition"]
    hors = (J < c["jmin"] - TOL_COMPARAISON) | (J > c["jmax"] + TOL_COMPARAISON)  # même règle que verdicts
    moyenne = float(J.mean()) if n else math.nan
    ecart = float(J.std(ddof=1)) if n > 1 else 0.0
    cap = capabilites(moyenne, ecart, c["jmin"], c["jmax"])
    q = np.quantile(J, [0.00135, 0.5, 0.99865]) if n else [math.nan] * 3
    return {
        "J": J,  # float64 : float32 (7 chiffres) écrase la dispersion des jeux de grande valeur absolue
        "n": n,
        "graine": graine,
        "moyenne": moyenne,
        "ecartType": ecart,
        "nHors": int(hors.sum()),
        "tauxHors": float(hors.mean()) if n else math.nan,
        "ppm": 1e6 * float(hors.mean()) if n else math.nan,
        "resolutionPpm": 1e6 / n if n else math.nan,
        "cp": cap["cp"],
        "cpk": cap["cpk"],
        "quantiles": {"bas": float(q[0]), "mediane": float(q[1]), "haut": float(q[2])},
    }
