"""Statistique majorée de Bender et tolérancement inertiel (Pillet)."""

import math

import pytest

from chainecotes.core.chaine import solveurChaine, verdicts
from chainecotes.core.inertiel import analyseInertielle, verdictBender
from chainecotes.services.calcul import calculerChaine
from chainecotes.services.exemples import chargerExemple
from chainecotes.services.explications import explicationsCalcul


def _res(ident="validation_100_40_59", **mesures):
    p = chargerExemple(ident)
    p["maillons"][0].update(mesures)
    return solveurChaine(p)


def test_bender_entre_somme_quadratique_et_pire_cas():
    res = _res()
    b = verdictBender(res)
    t = [abs(a) * it / 2 for a, it in zip(res["coef"], res["IT"], strict=True)]
    assert b["demi"] == pytest.approx(1.5 * math.sqrt(sum(x * x for x in t)))
    assert math.sqrt(sum(x * x for x in t)) <= b["demi"] <= sum(t) * 1.5
    assert b["min"] == pytest.approx(res["CF_moy"] - b["demi"])
    assert b["ok"] == (b["min"] >= res["condition"]["jmin"] and b["max"] <= res["condition"]["jmax"])


def test_inertie_du_jeu_et_cpi():
    res = _res()
    r = analyseInertielle(res)
    c = res["condition"]
    assert r["cible"] == pytest.approx((c["jmin"] + c["jmax"]) / 2)
    assert r["inertieJeu"] == pytest.approx(math.hypot(res["CF_sigma"], res["CF_moy_proc"] - r["cible"]))
    assert r["inertieMax"] == pytest.approx((c["jmax"] - c["jmin"]) / 6)
    assert r["cpi"] == pytest.approx(r["inertieMax"] / r["inertieJeu"])
    assert r["cpi"] <= verdicts(res)["cp"] + 1e-12  # l'inertie compte le décentrage en plus de σ


def test_repartition_inertielle_gagne_racine_de_n():
    r = analyseInertielle(_res())
    n = len(r["liens"])
    for lien in r["liens"]:
        assert lien["itInertiel"] / lien["itPireCas"] == pytest.approx(math.sqrt(n))


def test_inertie_d_une_cote_mesuree():
    res = _res(sigma_reel=0.003, moyenne_reelle=None)
    assert analyseInertielle(res)["liens"][0]["sigma"] == pytest.approx(0.003)
    res = _res(sigma_reel=0.003, moyenne_reelle=100.0)
    lien = analyseInertielle(res)["liens"][0]
    assert lien["ecart"] == pytest.approx(100.0 - res["C_moy"][0])
    assert lien["inertie"] == pytest.approx(math.hypot(0.003, lien["ecart"]))


def test_sans_deux_limites():
    p = chargerExemple("validation_100_40_59")
    p["condition"]["jmax"] = None
    r = analyseInertielle(solveurChaine(p))
    assert math.isnan(r["inertieMax"]) and math.isnan(r["cpi"]) and math.isfinite(r["inertieJeu"])


def test_explications_contiennent_la_section():
    sections = explicationsCalcul(calculerChaine(chargerExemple("validation_100_40_59"), n=2000))
    assert any("Bender" in s["titre"] for s in sections)
