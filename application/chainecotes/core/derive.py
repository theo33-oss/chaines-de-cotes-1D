"""Dérive du procédé : évolution du jeu moyen avec le nombre de pièces et intervalle de re-réglage.

Chaque maillon peut porter une dérive d_i (µm / 1000 pièces, champ « derive » du maillon). La moyenne du jeu glisse
de v = Σ a_i · d_i / 1000 mm par millier de pièces ; σ_J est inchangé. µ_J(n) = µ_J + v · n / 1000, où µ_J est la
moyenne du procédé (CF_moy_proc, décentrage compris).
"""

import math

import numpy as np
from scipy.optimize import brentq

from chainecotes.core.chaine import capabilites, ppmHorsTolerance, solveurChaine
from chainecotes.core.errors import ErreurChaine


def _piecesAvantMoyenne(mu0: float, v: float, jmin: float, jmax: float):
    """Pièces avant que la moyenne sorte de [jmin ; jmax] (0 si déjà dehors, None si jamais)."""
    if mu0 < jmin or mu0 > jmax:
        return 0.0
    if v > 0 and math.isfinite(jmax):
        return (jmax - mu0) * 1000 / v
    if v < 0 and math.isfinite(jmin):
        return (jmin - mu0) * 1000 / v
    return None


def _piecesAvantPpm(mu0: float, v: float, sigma: float, jmin: float, jmax: float, seuil: float):
    """Pièces avant que les ppm dépassent `seuil` (0 si déjà dépassé, None si jamais ou σ = 0)."""
    if not sigma > 0 or v == 0:
        return None
    if ppmHorsTolerance(mu0, sigma, jmin, jmax) > seuil:
        return 0.0
    lim = jmax if v > 0 else jmin
    if not math.isfinite(lim):
        return None  # la moyenne s'éloigne de la seule limite finie : les ppm ne font que baisser
    fin = lim + (1 if v > 0 else -1) * 10 * sigma

    def f(mu):
        return ppmHorsTolerance(mu, sigma, jmin, jmax) - seuil

    if f(fin) <= 0:
        return None
    mu = brentq(f, mu0, fin, xtol=1e-14, rtol=1e-13)  # un seul franchissement (les ppm baissent puis montent)
    return (mu - mu0) * 1000 / v


def deriveSerie(probleme: dict, nPieces: int, pas: int, seuilPpm: float | None = None) -> dict:
    """Série du jeu moyen, des ppm et de Cpk en fonction du nombre de pièces produites.

    Entrées : probleme (dict condition, reglages, maillons ; champ maillon « derive » en µm / 1000 pièces),
    nPieces (entier ≥ 0, dernière pièce de la série), pas (entier > 0), seuilPpm (≥ 0 ou None).
    Sortie : dict n (pièces : 0, pas, 2·pas, … ≤ nPieces), mu (mm), ppm (loi normale, ppmHorsTolerance), cpk,
    vitesse (mm / 1000 pièces), piecesSortieMoyenne (pièces avant sortie de la moyenne hors [Jmin ; Jmax], 0 si
    déjà dehors), piecesSeuilPpm (pièces avant dépassement de seuilPpm), intervalleRecalage (le plus petit des
    deux, arrondi à l'entier inférieur : cadence maximale de re-réglage). Ces trois valeurs valent None si
    l'événement n'arrive jamais (dérive nulle, pas de limite finie du côté de la dérive, σ = 0 pour les ppm).
    Les séries restent plates, sans erreur, si la dérive est nulle ou si aucune limite n'est finie.
    Erreur : ErreurChaine si nPieces, pas ou seuilPpm sont invalides ou si la saisie du problème l'est.
    """
    if not (isinstance(nPieces, int | np.integer) and not isinstance(nPieces, bool) and nPieces >= 0):
        raise ErreurChaine("Derive:nPieces", "Le nombre de pièces doit être un entier positif ou nul.")
    if not (isinstance(pas, int | np.integer) and not isinstance(pas, bool) and pas > 0):
        raise ErreurChaine("Derive:pas", "Le pas doit être un entier strictement positif.")
    if seuilPpm is not None and not (math.isfinite(seuilPpm) and seuilPpm >= 0):
        raise ErreurChaine("Derive:seuilPpm", "Le seuil de ppm doit être un nombre positif ou nul.")
    res = solveurChaine(probleme)
    c, sg = res["condition"], res["CF_sigma"]
    d = np.array([m["derive"] for m in res["maillons"]])
    v = float(np.sum(np.asarray(res["coef"]) * d)) / 1000
    mu0 = res["CF_moy_proc"]
    n = np.arange(0, nPieces + 1, pas)
    mu = mu0 + v * n / 1000
    ppm = [ppmHorsTolerance(float(m), sg, c["jmin"], c["jmax"]) for m in mu]
    cpk = [capabilites(float(m), sg, c["jmin"], c["jmax"])["cpk"] for m in mu]
    pm = _piecesAvantMoyenne(mu0, v, c["jmin"], c["jmax"])
    pp = None if seuilPpm is None else _piecesAvantPpm(mu0, v, sg, c["jmin"], c["jmax"], seuilPpm)
    connus = [x for x in (pm, pp) if x is not None]
    return {
        "n": [int(x) for x in n],
        "mu": [float(x) for x in mu],
        "ppm": ppm,
        "cpk": cpk,
        "vitesse": v,
        "piecesSortieMoyenne": pm,
        "piecesSeuilPpm": pp,
        "intervalleRecalage": math.floor(min(connus)) if connus else None,
    }
