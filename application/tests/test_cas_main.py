"""Cas refaits à la main : chaque valeur attendue est recalculée ici avec sa formule écrite, sans le solveur."""

import math

import pytest

from chainecotes.core import iso286
from chainecotes.core.chaine import capabilites, contributions, ppmHorsTolerance, solveurChaine
from chainecotes.services.exemples import chargerExemple

REL = 1e-9


def _maillon(nom, sens, cote, es=0.0, ei=0.0, loi="normale", alpha=None, iso=None):
    return {"nom": nom, "sens": sens, "cote": cote, "iso": iso, "es": es, "ei": ei, "loi": loi,
            "materiau": None, "alpha": alpha, "tservice": 20.0}  # fmt: skip


def _probleme(maillons, k=3, tservice=20.0, jmin=None, jmax=None):
    return {
        "condition": {"nom": "Jeu J", "jmin": jmin, "jmax": jmax},
        "reglages": {"kSigma": k, "tref": 20.0, "modeT": "uniforme", "tservice": tservice},
        "maillons": maillons,
    }


def test_chaine_100_40_59():
    """J = 100 − 40 − 59 = 1 ; pire cas ± (0,1 + 0,05 + 0,05) = ± 0,2 ; σ = √Σ (IT_i / 2k)²."""
    p = _probleme(
        [
            _maillon("Carter", "+", 100.0, 0.1, -0.1),
            _maillon("Bague", "-", 40.0, 0.05, -0.05),
            _maillon("Moyeu", "-", 59.0, 0.05, -0.05),
        ]  # fmt: skip
    )
    res = solveurChaine(p)
    assert res["CF_nom"] == pytest.approx(100 - 40 - 59, rel=REL)
    assert res["CF_moy"] == pytest.approx(1.0, rel=REL)
    assert res["CF_min"] == pytest.approx(1 - (0.1 + 0.05 + 0.05), rel=REL)
    assert res["CF_max"] == pytest.approx(1 + (0.1 + 0.05 + 0.05), rel=REL)
    sigma = math.sqrt((0.2 / 6) ** 2 + 2 * (0.1 / 6) ** 2)
    assert res["CF_sigma"] == pytest.approx(sigma, rel=REL)


def test_ajustement_h7_g6_sur_50():
    """Aide 03 : H7 sur 50 → ES = IT7 = 0,025, EI = 0 ; g6 sur 50 → es = −0,009, ei = es − IT6 = −0,025."""
    h7 = iso286.lireDesignation("50 H7")
    g6 = iso286.lireDesignation("g6", 50.0)
    assert (h7["es"], h7["ei"]) == pytest.approx((0.025, 0.0), abs=1e-12)
    assert (g6["es"], g6["ei"]) == pytest.approx((-0.009, -0.025), abs=1e-12)
    assert h7["es"] - h7["ei"] == pytest.approx(iso286.toleranceIT(50, 7) / 1000, abs=1e-12)
    assert g6["es"] - g6["ei"] == pytest.approx(iso286.toleranceIT(50, 6) / 1000, abs=1e-12)


def test_loi_uniforme_sigma_it_sur_racine_12():
    """Loi uniforme de largeur IT : σ_i = IT / √12 (et non IT / 2k)."""
    p = _probleme([_maillon("A", "+", 100.0, 0.1, -0.1, loi="uniforme"), _maillon("B", "-", 99.0, 0.03, -0.03)])
    res = solveurChaine(p)
    assert res["sigma_i"][0] == pytest.approx(0.2 / math.sqrt(12), rel=REL)
    assert res["sigma_i"][1] == pytest.approx(0.06 / 6, rel=REL)
    assert res["CF_sigma"] == pytest.approx(math.hypot(0.2 / math.sqrt(12), 0.06 / 6), rel=REL)


def test_thermique_alu_acier_1_1112():
    """Aide 13 : 100 alu (α 23e-6) − 50 et 49 acier (α 12e-6), de 20 à 120 °C : J = 1 + 0,23 − 0,06 − 0,0588."""
    p = _probleme(
        [
            _maillon("Carter", "+", 100.0, alpha=23.0),
            _maillon("Arbre", "-", 50.0, alpha=12.0),
            _maillon("Bague", "-", 49.0, alpha=12.0),
        ],  # fmt: skip
        tservice=120.0,
    )
    res = solveurChaine(p)
    attendu = 100 * (1 + 23e-6 * 100) - 50 * (1 + 12e-6 * 100) - 49 * (1 + 12e-6 * 100)
    assert attendu == pytest.approx(1.1112, rel=1e-12)
    assert res["CF_nom"] == pytest.approx(attendu, rel=REL)
    assert res["CF_nom_ref"] == pytest.approx(1.0, rel=REL)
    assert res["dJ_th"] == pytest.approx(0.1112, rel=REL)
    assert sum(res["dJ_th_i"]) == pytest.approx(0.1112, rel=REL)


def test_k4_donne_sigma_trois_quarts():
    """σ_i = IT / 2k : passer de k = 3 à k = 4 multiplie σ par 3/4."""
    p3 = chargerExemple("ajustements_h7_h6_n7")
    p4 = chargerExemple("ajustements_h7_h6_n7")
    p4["reglages"]["kSigma"] = 4
    assert solveurChaine(p4)["CF_sigma"] == pytest.approx(solveurChaine(p3)["CF_sigma"] * 3 / 4, rel=REL)


def test_cp_cpk_ppm_aide_05():
    """μ = 1,046, σ = 0,0076, [1,03 ; 1,06] : côté USL (1,06 − μ)/3σ ≈ 0,61, côté LSL ≈ 0,70, Cpk ≈ 0,61."""
    mu, s, lsl, usl = 1.046, 0.0076, 1.03, 1.06
    cap = capabilites(mu, s, lsl, usl)
    assert cap["cp"] == pytest.approx((usl - lsl) / (6 * s), rel=REL)
    assert cap["cpk"] == pytest.approx((usl - mu) / (3 * s), rel=REL)
    assert round(cap["cpk"], 2) == 0.61
    assert round((mu - lsl) / (3 * s), 2) == 0.70

    def phi(z):
        return 0.5 * math.erfc(-z / math.sqrt(2))

    ppm = 1e6 * (phi((lsl - mu) / s) + phi((mu - usl) / s))
    assert ppmHorsTolerance(mu, s, lsl, usl) == pytest.approx(ppm, rel=REL)


def test_contributions_somment_a_100():
    res = solveurChaine(chargerExemple("ajustements_h7_h6_n7"))
    c = contributions(res)
    assert sum(x["partPireCas"] for x in c) == pytest.approx(100, rel=REL)
    assert sum(x["partVariance"] for x in c) == pytest.approx(100, rel=REL)
    # aide 06 : IT 35, 16, 25 µm → parts pire cas 35/76, 16/76, 25/76
    assert [x["partPireCas"] for x in c] == pytest.approx([100 * 35 / 76, 100 * 16 / 76, 100 * 25 / 76], rel=REL)
