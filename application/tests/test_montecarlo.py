"""Monte-Carlo : reproductible à graine égale, statistiques conformes à la théorie (tolérance 5 erreurs-types)."""

import math

import numpy as np
import pytest

from chainecotes.core.chaine import capabilites, solveurChaine
from chainecotes.core.montecarlo import simulerMonteCarlo
from chainecotes.services.exemples import chargerExemple

N = 200_000
Z = 5  # erreurs-types


@pytest.fixture(scope="module")
def res():
    return solveurChaine(chargerExemple("ajustements_h7_h6_n7"))


def test_meme_graine_memes_tirages(res):
    assert np.array_equal(simulerMonteCarlo(res, 1000, 7)["J"], simulerMonteCarlo(res, 1000, 7)["J"])


def test_graines_differentes_tirages_differents(res):
    assert not np.array_equal(simulerMonteCarlo(res, 1000, 1)["J"], simulerMonteCarlo(res, 1000, 2)["J"])


def test_moyenne_et_ecart_type_theoriques(res):
    """Moyenne : erreur-type σ/√n ; écart-type d'un échantillon normal : erreur-type σ/√(2n)."""
    mc = simulerMonteCarlo(res, N, 1)
    s = res["CF_sigma"]
    assert abs(mc["moyenne"] - res["CF_moy"]) <= Z * s / math.sqrt(N)
    assert abs(mc["ecartType"] - s) <= Z * s / math.sqrt(2 * N)


def test_loi_uniforme_bornee():
    """Chaque cote uniforme reste dans [C_moy − IT/2 ; C_moy + IT/2], donc le jeu dans [J_min ; J_max] du pire cas."""
    p = chargerExemple("validation_100_40_59")
    for m in p["maillons"]:
        m["loi"] = "uniforme"
    r = solveurChaine(p)
    mc = simulerMonteCarlo(r, N, 3)
    assert mc["J"].min() >= r["CF_min"] - 1e-12
    assert mc["J"].max() <= r["CF_max"] + 1e-12
    # σ_J = √Σ (IT_i/√12)² ; écart-type d'échantillon : erreur-type ≈ σ/√(2n) (marge large, loi non normale)
    s = math.sqrt(sum((it / math.sqrt(12)) ** 2 for it in r["IT"]))
    assert r["CF_sigma"] == pytest.approx(s, rel=1e-12)
    assert abs(mc["moyenne"] - r["CF_moy"]) <= Z * s / math.sqrt(N)
    assert abs(mc["ecartType"] - s) <= 2 * Z * s / math.sqrt(2 * N)


def test_ppm_nul_si_tout_dans_les_limites():
    """Lois uniformes et limites au pire des cas : aucun tirage ne peut sortir."""
    p = chargerExemple("validation_100_40_59")
    for m in p["maillons"]:
        m["loi"] = "uniforme"
    r = solveurChaine(p)
    r["condition"] = {"nom": "Jeu J", "jmin": r["CF_min"], "jmax": r["CF_max"]}
    mc = simulerMonteCarlo(r, 20_000, 1)
    assert mc["nHors"] == 0 and mc["ppm"] == 0
    assert mc["resolutionPpm"] == pytest.approx(1e6 / 20_000)


def test_cp_cpk_coherents(res):
    mc = simulerMonteCarlo(res, N, 1)
    c = res["condition"]
    cap = capabilites(mc["moyenne"], mc["ecartType"], c["jmin"], c["jmax"])
    assert mc["cp"] == cap["cp"] and mc["cpk"] == cap["cpk"]
    assert mc["cpk"] <= mc["cp"]
    assert mc["ppm"] == pytest.approx(1e6 * mc["nHors"] / N, rel=1e-12)
    assert mc["quantiles"]["bas"] < mc["quantiles"]["mediane"] < mc["quantiles"]["haut"]
