"""Sensibilité globale : indices de variance, classement, gain si resserré, vérification Monte-Carlo (Jansen)."""

import math

import numpy as np
import pytest
from scipy.stats import norm

from chainecotes.core.chaine import solveurChaine
from chainecotes.core.errors import ErreurChaine
from chainecotes.core.sensibilite import gainSiResserre, indicesSensibilite, verifierSensibiliteMonteCarlo


def _probleme(lois=("normale", "normale", "normale"), decentrage=None, jmin=0.9, jmax=1.3, tserv=20.0, alpha=None):
    """J = 100 − 40 − 59 = 1 mm ; IT = 0,2 ; 0,1 ; 0,1 mm."""
    reglages = {"kSigma": 3, "tref": 20.0, "modeT": "uniforme", "tservice": tserv}
    if decentrage is not None:
        reglages["decentrage"] = decentrage
    donnees = [("A", "+", 100.0, 0.1), ("B", "-", 40.0, 0.05), ("C", "-", 59.0, 0.05)]
    maillons = [
        {"nom": n, "sens": s, "cote": c, "es": e, "ei": -e, "loi": loi, "alpha": alpha if n == "A" else None}
        for (n, s, c, e), loi in zip(donnees, lois, strict=True)
    ]
    return {"condition": {"jmin": jmin, "jmax": jmax}, "reglages": reglages, "maillons": maillons}


def test_indices_formule_a_la_main():
    ind = indicesSensibilite(solveurChaine(_probleme()))
    var = np.array([(0.2 / 6) ** 2, (0.1 / 6) ** 2, (0.1 / 6) ** 2])
    assert [i["indice"] for i in ind] == pytest.approx(list(var / var.sum()), rel=1e-12)
    assert sum(i["indice"] for i in ind) == pytest.approx(1.0)
    assert [i["rang"] for i in ind] == [1, 2, 3]  # égalité B / C : ordre de saisie
    assert [i["partPireCas"] for i in ind] == pytest.approx([0.5, 0.25, 0.25])


def test_indices_pris_en_compte_loi_et_thermique():
    """Un maillon uniforme pèse plus ; la dilatation (a_i ≠ 1) modifie les poids."""
    res = solveurChaine(_probleme(lois=("uniforme", "normale", "normale"), tserv=120.0, alpha=20.0))
    a = 1 + 20e-6 * 100
    v = np.array([(a * 0.2 / math.sqrt(12)) ** 2, (0.1 / 6) ** 2, (0.1 / 6) ** 2])
    assert [i["indice"] for i in indicesSensibilite(res)] == pytest.approx(list(v / v.sum()), rel=1e-12)


def test_decentrage_sans_effet_sur_les_indices():
    a = indicesSensibilite(solveurChaine(_probleme()))
    b = indicesSensibilite(solveurChaine(_probleme(decentrage=2.0)))
    assert a == b


@pytest.mark.parametrize("lois", [("normale",) * 3, ("uniforme", "triangulaire", "normale")])
def test_indices_confirmes_par_monte_carlo(lois):
    res = solveurChaine(_probleme(lois=lois))
    exact = [i["indice"] for i in indicesSensibilite(res)]
    assert verifierSensibiliteMonteCarlo(res, n=400000, graine=3) == pytest.approx(exact, abs=0.01)


def test_gain_si_resserre_recalcul_independant():
    res = solveurChaine(_probleme())
    g = gainSiResserre(res)
    for i, ligne in enumerate(g):
        it = list(res["IT"])
        it[i] /= 2
        s = math.sqrt(sum((it[j] / 6) ** 2 for j in range(3)))
        assert ligne["sigma"] == pytest.approx(s, rel=1e-12)
        assert ligne["gainSigma"] == pytest.approx(res["CF_sigma"] - s, rel=1e-9)
        assert ligne["cpk"] == pytest.approx(0.1 / (3 * s), rel=1e-12)  # moyenne 1,0 : Jmin plus proche
        assert ligne["gainCpk"] > 0
        assert ligne["ppm"] == pytest.approx(1e6 * (norm.cdf(-0.1 / s) + norm.sf(0.3 / s)), rel=1e-6)
    assert g[0]["gainSigma"] > g[1]["gainSigma"]  # le plus gros contributeur rapporte le plus


def test_gain_cas_limites():
    res = solveurChaine(_probleme(jmin=None, jmax=None))
    g = gainSiResserre(res, 0.0)  # tolérance supprimée
    assert g[0]["sigma"] == pytest.approx(math.sqrt(2) * 0.1 / 6)
    assert math.isnan(g[0]["gainCpk"])  # aucune limite finie
    for mauvais in (1.0, -0.1, math.nan):
        with pytest.raises(ErreurChaine):
            gainSiResserre(res, mauvais)


def test_sigma_nul():
    p = _probleme()
    for m in p["maillons"]:
        m["es"] = m["ei"] = 0.0
    res = solveurChaine(p)
    assert [i["indice"] for i in indicesSensibilite(res)] == [0.0, 0.0, 0.0]
    assert verifierSensibiliteMonteCarlo(res, n=10) == [0.0, 0.0, 0.0]
    assert all(x["gainSigmaPct"] == 0.0 for x in gainSiResserre(res))
