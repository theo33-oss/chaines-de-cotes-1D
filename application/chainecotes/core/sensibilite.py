"""Sensibilité globale du jeu : indices de variance du premier ordre (Sobol) et gain si l'on resserre une tolérance.

Le jeu J = Σ a_i · x_i est linéaire en variables indépendantes : l'indice de Sobol du premier ordre est exact
et vaut S_i = (a_i σ_i)² / Σ (a_j σ_j)², avec σ_i l'écart type de x_i selon sa loi (res["sigma_i"] contient déjà
|a_i| · σ(x_i)). Les indices somment à 1 (pas d'interaction). Un décentrage du procédé décale la moyenne du jeu
sans changer sa variance : il n'a donc aucun effet sur ces indices (il agit sur Cpk et les ppm, voir gainSiResserre).
"""

import math

import numpy as np

from chainecotes.core.chaine import capabilites, ppmHorsTolerance
from chainecotes.core.errors import ErreurChaine


def indicesSensibilite(res: dict) -> list[dict]:
    """Indice de variance du premier ordre de chaque maillon, classement et part du pire cas.

    Entrée : res (sortie de solveurChaine).
    Sortie : liste (ordre des maillons) de dict nom, indice (S_i, somme = 1 ; 0 partout si σ_J = 0), rang (1 = maillon
    le plus influent), partPireCas (part de |a_i|·IT_i/2 dans la demi-dispersion du pire cas, de somme 1).
    """
    var = np.asarray(res["sigma_i"], dtype=float) ** 2
    wc = np.abs(res["coef"]) * np.asarray(res["IT"], dtype=float) / 2
    sv, sw = var.sum(), wc.sum()
    ordre = np.argsort(-var, kind="stable")
    rang = np.empty(len(var), dtype=int)
    rang[ordre] = np.arange(1, len(var) + 1)
    return [
        {
            "nom": n,
            "indice": float(v / sv) if sv > 0 else 0.0,
            "rang": int(r),
            "partPireCas": float(w / sw) if sw > 0 else 0.0,
        }
        for n, v, w, r in zip(res["Nom"], var, wc, rang, strict=True)
    ]


def gainSiResserre(res: dict, facteur: float = 0.5) -> list[dict]:
    """Effet de la réduction d'une seule tolérance (IT_i · facteur), maillon par maillon.

    Entrées : res (sortie de solveurChaine), facteur (0 ≤ facteur < 1, défaut 0,5 : tolérance divisée par deux).
    σ_i est proportionnel à IT_i pour toutes les lois : σ_J'² = σ_J² − (1 − facteur²) σ_i². La moyenne du procédé
    (CF_moy_proc) et les limites de la cote condition restent inchangées.
    Sortie : liste (ordre des maillons) de dict nom, sigma (mm, après), gainSigma (mm, ≥ 0), gainSigmaPct (%),
    cpk (après), gainCpk (après − avant, nan sans limite finie ou si σ = 0), ppm (après, nan si σ = 0).
    Erreur : ErreurChaine si facteur n'est pas dans [0 ; 1[.
    """
    if not (math.isfinite(facteur) and 0 <= facteur < 1):
        raise ErreurChaine("Sensibilite:facteur", "Le facteur de resserrement doit être dans [0 ; 1[.")
    c, mu, s0 = res["condition"], res["CF_moy_proc"], res["CF_sigma"]
    cpk0 = capabilites(mu, s0, c["jmin"], c["jmax"])["cpk"]
    sortie = []
    for nom, si in zip(res["Nom"], np.asarray(res["sigma_i"], dtype=float), strict=True):
        s1 = math.sqrt(max(s0**2 - (1 - facteur**2) * si**2, 0.0))
        cpk1 = capabilites(mu, s1, c["jmin"], c["jmax"])["cpk"]
        sortie.append(
            {
                "nom": nom,
                "sigma": s1,
                "gainSigma": s0 - s1,
                "gainSigmaPct": 100 * (s0 - s1) / s0 if s0 > 0 else 0.0,
                "cpk": cpk1,
                "gainCpk": cpk1 - cpk0,
                "ppm": ppmHorsTolerance(mu, s1, c["jmin"], c["jmax"]),
            }
        )
    return sortie


def verifierSensibiliteMonteCarlo(res: dict, n: int = 200000, graine: int = 1) -> list[float]:
    """Indices du premier ordre estimés par Monte-Carlo (estimateur de Jansen, plan de Saltelli A / B / AB_i).

    Entrées : res (sortie de solveurChaine), n (tirages par matrice), graine (reproductibilité).
    Chaque x_i suit sa loi (normale d'écart type σ_i, uniforme, triangulaire symétrique), toutes de moyenne nulle
    (la moyenne n'influe pas sur la variance). S_i = 1 − E[(Y_A − Y_ABi)²] / (2 Var Y).
    Sortie : liste des S_i estimés (ordre des maillons), à comparer à indicesSensibilite.
    """
    rng = np.random.default_rng(graine)
    sig = np.asarray(res["sigma_i"], dtype=float)

    def tirer():
        x = np.empty((n, len(sig)))
        for i, (loi, s) in enumerate(zip(res["loi"], sig, strict=True)):
            if loi == "normale":
                x[:, i] = rng.normal(0.0, s, n)
            elif loi == "uniforme":
                x[:, i] = rng.uniform(-math.sqrt(3) * s, math.sqrt(3) * s, n)
            else:
                h = math.sqrt(6) * s
                x[:, i] = rng.triangular(-h, 0.0, h, n)
        return x

    A, B = tirer(), tirer()
    yA, yB = A.sum(axis=1), B.sum(axis=1)
    var = np.var(np.concatenate([yA, yB]))
    if not var > 0:
        return [0.0] * len(sig)
    out = []
    for i in range(len(sig)):
        yAB = yB + (A[:, i] - B[:, i])  # AB_i : B dont la colonne i vient de A
        out.append(float(1 - np.mean((yA - yAB) ** 2) / (2 * var)))
    return out
