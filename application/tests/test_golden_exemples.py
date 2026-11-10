"""Chaque exemple de data/exemples.json redonne les résultats MATLAB de tests/golden/golden_exemples.json.

Déterministe (solveur, verdicts, Pareto, risque selon le Cp) : relative 1e-9, absolue 1e-12.
Monte-Carlo : numpy (PCG64) et MATLAB (mt19937ar + randn) ne tirent pas les mêmes nombres ; on compare donc des
statistiques, avec une tolérance de 5 erreurs-types de la différence de deux estimations indépendantes.
"""

import math

import numpy as np
import pytest

from chainecotes.core.chaine import contributions, risqueSelonCp, solveurChaine, verdicts
from chainecotes.core.donnees import chargerJson
from chainecotes.core.montecarlo import simulerMonteCarlo
from tests.golden_tools import assertConforme, assertTableau, casGolden, chargerGolden, enFlottant

GOLDEN = "golden_exemples.json"
CAS = casGolden(GOLDEN, "exemples")
IDS = [c["id"] for c in CAS]
N_ERREURS_TYPES = 5


def _cas(cid: str) -> dict:
    return next(c for c in chargerGolden(GOLDEN)["exemples"] if c["id"] == cid)


def _probleme(cid: str) -> dict:
    return next(e for e in chargerJson("exemples.json")["exemples"] if e["id"] == cid)


def test_tous_les_exemples_ont_un_golden():
    ids_data = [e["id"] for e in chargerJson("exemples.json")["exemples"]]
    assert sorted(ids_data) == sorted(c["id"] for c in chargerGolden(GOLDEN)["exemples"])


@pytest.mark.parametrize("cid", IDS)
def test_entrees_resolues(cid):
    """ISO 286, matériaux et températures résolus comme dans MATLAB (es, ei, α, θ, Tservice, réglages)."""
    e = _cas(cid)["entrees"]
    res = solveurChaine(_probleme(cid))
    assert res["Nom"] == e["nom"]
    assertTableau(res["Cote"], e["cote"], chemin="entrees.cote")
    assertTableau(res["ES"], e["es"], chemin="entrees.es")
    assertTableau(res["EI"], e["ei"], chemin="entrees.ei")
    assertTableau([m["theta"] for m in res["maillons"]], e["theta"], chemin="entrees.theta")
    assertTableau(res["alpha"], e["alpha"], chemin="entrees.alpha")
    assertTableau(res["Tservice"], e["tservice"], chemin="entrees.tservice")
    assert res["k_sigma"] == e["kSigma"]
    assert res["Tref"] == e["tref"]
    assert res["mode_thermique"] == e["modeT"]
    # null = pas de limite de ce côté
    assert res["condition"]["jmin"] == (-math.inf if e["jmin"] is None else e["jmin"])
    assert res["condition"]["jmax"] == (math.inf if e["jmax"] is None else e["jmax"])


@pytest.mark.parametrize("cid", IDS)
def test_resultats_solveur(cid):
    """Toutes les grandeurs de Solveur_chaine_de_cotes_1D.m, vecteurs compris (dJ_th_i, coef, C_moy, IT, α, dT)."""
    assertConforme(solveurChaine(_probleme(cid)), _cas(cid)["resultats"], chemin="resultats")


@pytest.mark.parametrize("cid", IDS)
def test_graphiques(cid):
    """Verdicts, capabilités, ppm, Pareto et risque selon le Cp face aux champs de graphiques.m."""
    g = _cas(cid)["graphiques"]
    res = solveurChaine(_probleme(cid))
    v = verdicts(res)
    contrib = contributions(res)
    assertTableau([c["partPireCas"] for c in contrib], g["paretoWC"], chemin="paretoWC")
    assertTableau([c["partVariance"] for c in contrib], g["paretoRSS"], chemin="paretoRSS")
    assertConforme(v["cp"], g["cp"], chemin="cp")
    assertConforme(v["cpk"], g["cpk"], chemin="cpk")
    assertConforme(v["ppm"], g["ppm"], chemin="ppm")
    assertTableau([v["rssK"]["min"], v["rssK"]["max"]], g["rss3"], chemin="rss3")
    assertTableau([v["rss6"]["min"], v["rss6"]["max"]], g["rss6"], chemin="rss6")
    r = risqueSelonCp(res)
    if g["risqueCp"]:
        assertTableau(r["cp"], g["risqueCp"], chemin="risqueCp")
        assertTableau(r["ppm"], g["risquePpm"], chemin="risquePpm")
    else:
        # MATLAB ne trace pas le risque quand σ = 0 ; le site rend des ppm non définis (nan)
        assert res["CF_sigma"] == 0 and all(math.isnan(p) for p in r["ppm"])


@pytest.mark.parametrize("cid", IDS)
def test_montecarlo_statistique(cid):
    """Moyenne, écart-type et ppm simulés proches de ceux de MATLAB (tolérance statistique justifiée)."""
    g = _cas(cid)["monteCarlo"]
    res = solveurChaine(_probleme(cid))
    if g["N"] == 0:
        # σ = 0 : MATLAB ne simule pas, il garde le jeu moyen
        assert res["CF_sigma"] == 0
        assertConforme(res["CF_moy"], g["moyenne"], chemin="monteCarlo.moyenne")
        return
    n = g["N"]
    mc = simulerMonteCarlo(res, n=n, graine=g["graine"])
    s = res["CF_sigma"]
    # deux moyennes indépendantes de n tirages : erreur-type de la différence √2 · σ / √n
    tol_moy = N_ERREURS_TYPES * math.sqrt(2) * s / math.sqrt(n)
    assert abs(mc["moyenne"] - g["moyenne"]) <= tol_moy
    # écart-type d'un échantillon normal : erreur-type σ / √(2n) ; différence de deux : σ / √n
    tol_ecart = N_ERREURS_TYPES * s / math.sqrt(n)
    assert abs(mc["ecartType"] - g["ecartType"]) <= tol_ecart
    # ppm : deux proportions binomiales de n tirages, p pris au plus grand du ppm MATLAB et de la formule ;
    # plus une unité de résolution (10⁶/n) pour le caractère discret du comptage
    p = max(enFlottant(g["ppm"]), verdicts(res)["ppm"]) / 1e6
    tol_ppm = 1e6 * (N_ERREURS_TYPES * math.sqrt(2 * p * (1 - p) / n) + 1 / n)
    assert abs(mc["ppm"] - g["ppm"]) <= tol_ppm, f"ppm {mc['ppm']} contre MATLAB {g['ppm']} (± {tol_ppm:.3g})"
    assert np.isfinite(mc["J"]).all()
