"""Capabilités mesurées à l'atelier : σ et moyenne mesurés remplacent le modèle de la loi."""

import math

import pytest

from chainecotes.core.chaine import capabilitesMaillons, solveurChaine
from chainecotes.services.calcul import calculerChaine
from chainecotes.services.controles import controlerProbleme
from chainecotes.services.exemples import chargerExemple, listeExemples
from chainecotes.services.explications import explicationsCalcul
from chainecotes.services.projet_io import exporterProbleme, importerProbleme
from chainecotes.services.validation import dossierValidation


def _probleme(**mesures):
    p = chargerExemple("ajustements_h7_h6_n7")
    p["maillons"][0].update(mesures)
    return p


def test_defaut_inchange_pour_tous_les_exemples():
    for e in listeExemples():
        res = solveurChaine(chargerExemple(e["id"]))
        assert res["decalage_reel"] == 0.0
        assert res["decalage"] == res["CF_moy_proc"] - res["CF_moy"]


def test_sigma_mesure_remplace_le_modele():
    res0, res = solveurChaine(_probleme()), solveurChaine(_probleme(sigma_reel=0.004))
    a = abs(res["coef"][0])
    assert res["sigma_i"][0] == pytest.approx(a * 0.004)
    attendu = math.sqrt(res0["CF_sigma"] ** 2 - res0["sigma_i"][0] ** 2 + (a * 0.004) ** 2)
    assert res["CF_sigma"] == pytest.approx(attendu)
    assert res["CF_min"] == res0["CF_min"]  # le pire des cas ne dépend pas des mesures


def test_moyenne_mesuree_decale_le_procede():
    res0 = solveurChaine(_probleme())
    decalage = 0.01
    res = solveurChaine(_probleme(moyenne_reelle=res0["C_moy"][0] + decalage))
    assert res["decalage_reel"] == pytest.approx(res["coef"][0] * decalage)
    assert res["CF_moy_proc"] == pytest.approx(res0["CF_moy_proc"] + res["decalage_reel"])
    assert res["CF_moy"] == res0["CF_moy"] and res["CF_max"] == res0["CF_max"]


def test_monte_carlo_suit_les_mesures():
    p = _probleme(sigma_reel=0.004, moyenne_reelle=None)
    b = calculerChaine(p, n=200_000)
    assert b["mc"]["ecartType"] == pytest.approx(b["res"]["CF_sigma"], rel=0.01)
    assert b["mc"]["moyenne"] == pytest.approx(
        b["res"]["CF_moy_proc"], abs=4 * b["res"]["CF_sigma"] / math.sqrt(200_000)
    )


def test_dossier_de_validation_concorde():
    p = _probleme(sigma_reel=0.004, moyenne_reelle=100.02)
    p["reglages"]["decentrage"] = 0.5
    d = dossierValidation(p, calculerChaine(p, n=50_000))
    assert d["nOk"] == d["nTotal"], [c for c in d["controles"] if c["statut"] != "OK"]
    assert "σ mesuré" in d["html"]


def test_capabilites_par_cote():
    res = solveurChaine(_probleme(sigma_reel=0.002, moyenne_reelle=100.0))
    c = capabilitesMaillons(res)
    m = res["maillons"][0]
    assert c[0]["mesure"] and not c[1]["mesure"]
    assert c[0]["cp"] == pytest.approx((m["es"] - m["ei"]) / (6 * 0.002))
    assert c[0]["cpk"] == pytest.approx(min(m["cote"] + m["es"] - 100.0, 100.0 - m["cote"] - m["ei"]) / (3 * 0.002))
    assert c[1]["cp"] == pytest.approx(res["k_sigma"] / 3)  # modèle : IT = 2kσ donc Cp = k / 3


def test_controles_et_fichier():
    p = _probleme(sigma_reel=0.004, moyenne_reelle=101.0)
    assert "moyenneMesureeHorsTolerance" in {c["code"] for c in controlerProbleme(p)}
    assert importerProbleme(exporterProbleme(p))["maillons"][0]["sigma_reel"] == 0.004
    assert any("5 ter" in s["titre"] for s in explicationsCalcul(calculerChaine(p, n=2000)))


def test_sigma_negatif_refuse():
    with pytest.raises(Exception, match="écart type"):
        solveurChaine(_probleme(sigma_reel=-0.1))
