"""ppm exacts quand des maillons sont en loi uniforme ou triangulaire : valeurs de référence et Monte-Carlo."""

import pytest

from chainecotes.core.chaine import ppmExact, solveurChaine
from chainecotes.core.montecarlo import simulerMonteCarlo
from chainecotes.services.calcul import calculerChaine
from chainecotes.services.exemples import chargerExemple


def _chaine(lois, jmin, jmax, tols=(0.1, 0.1)):
    maillons = [{"nom": "A", "sens": "+", "cote": 1.0, "es": tols[0], "ei": -tols[0], "loi": lois[0]}]
    maillons.append({"nom": "B", "sens": "-", "cote": 0.0001, "es": tols[1], "ei": -tols[1], "loi": lois[1]})
    return {
        "condition": {"nom": "J", "jmin": jmin, "jmax": jmax},
        "reglages": {"kSigma": 3, "tref": 20.0, "modeT": "uniforme", "tservice": 20.0},
        "maillons": maillons,
    }


def test_deux_uniformes_limites_sur_le_support_donnent_zero():
    """J est triangulaire sur [0,8 ; 1,2] : il ne peut pas sortir de [0,7 ; 1,3] (la formule normale dit 238 ppm)."""
    res = solveurChaine(_chaine(("uniforme", "uniforme"), 0.7, 1.3))
    assert ppmExact(res) == pytest.approx(0.0, abs=1e-6)


def test_deux_uniformes_queue_connue():
    """Somme de deux uniformes ±0,1 : P(J > 1 + 0,19) = (0,2 − 0,19)² / (2·0,2²) = 1,25 e-3 par côté."""
    res = solveurChaine(_chaine(("uniforme", "uniforme"), 0.81, 1.19))
    attendu = 2 * (0.01**2) / (2 * 0.2**2) * 1e6  # 2 côtés, ppm
    assert ppmExact(res) == pytest.approx(attendu, rel=0.02)


def test_tout_normal_renvoie_none():
    assert ppmExact(solveurChaine(_chaine(("normale", "normale"), 0.7, 1.3))) is None


def test_accord_avec_monte_carlo():
    """Chaîne mixte (normale + triangulaire + uniforme) : l'exact et 4·10⁶ tirages donnent le même taux."""
    p = chargerExemple("boitier_electronique")
    res = solveurChaine(p)
    exact = ppmExact(res)
    assert exact is not None and 0 < exact < 1000
    # on resserre les limites pour avoir assez de tirages hors limites : exact et simulation à ± 3 écarts types
    c = res["condition"]
    demi = (c["jmax"] - c["jmin"]) / 2
    p["condition"]["jmin"], p["condition"]["jmax"] = c["jmin"] + 0.4 * demi, c["jmax"] - 0.4 * demi
    res = solveurChaine(p)
    exact = ppmExact(res)
    mc = simulerMonteCarlo(res, 4_000_000, 1)
    sigma = (exact * 1e-6 * (1 - exact * 1e-6) / 4_000_000) ** 0.5 * 1e6
    assert abs(exact - mc["ppm"]) < 4 * sigma + 1.0, (exact, mc["ppm"])


def test_boitier_electronique_bien_en_dessous_de_la_formule_normale():
    b = calculerChaine(chargerExemple("boitier_electronique"), monteCarlo=False)
    assert b["ppmExact"] is not None
    assert b["ppmExact"] < b["verdicts"]["ppm"] / 5  # l'audit : 2,9 ppm exacts contre 114,7 par la formule normale
