"""Décentrage du procédé, loi triangulaire et dérive : recalculs à la main et Monte-Carlo (1e6 tirages)."""

import copy
import math

import numpy as np
import pytest

from chainecotes.core.chaine import coefficientSigma, decalageDecentrage, solveurChaine, verdicts
from chainecotes.core.errors import ErreurChaine
from chainecotes.core.montecarlo import simulerMonteCarlo
from chainecotes.services.calcul import calculerChaine
from chainecotes.services.explications import explicationsCalcul
from chainecotes.services.projet_io import exporterProbleme, exporterResultatsCsv, importerProbleme
from chainecotes.services.validation import dossierValidation


def _probleme(decentrage=None, lois=("normale", "normale", "normale"), jmin=0.9, jmax=1.3, derive=None):
    """J = 100 − 40 − 59 = 1 mm ; IT = 0,2 ; 0,1 ; 0,1 mm."""
    reglages = {"kSigma": 3, "tref": 20.0, "modeT": "uniforme", "tservice": 20.0}
    if decentrage is not None:
        reglages["decentrage"] = decentrage
    donnees = [("A", "+", 100.0, 0.1), ("B", "-", 40.0, 0.05), ("C", "-", 59.0, 0.05)]
    maillons = [
        {"nom": n, "sens": s, "cote": c, "iso": None, "es": e, "ei": -e, "loi": loi}
        for (n, s, c, e), loi in zip(donnees, lois, strict=True)
    ]
    if derive is not None:
        maillons[0]["derive"] = derive
    return {"condition": {"nom": "Jeu J", "jmin": jmin, "jmax": jmax}, "reglages": reglages, "maillons": maillons}


def _phi(z):
    return 0.5 * math.erfc(-z / math.sqrt(2))


SIGMA_J = math.sqrt((0.2 / 6) ** 2 + (0.1 / 6) ** 2 * 2)


# ------------------------------------------------------------------ défaut = comportement actuel


def test_defaut_sans_decentrage_ni_derive():
    res = solveurChaine(_probleme())
    assert res["decentrage"] == 0.0 and res["decalage"] == 0.0
    assert res["CF_moy_proc"] == res["CF_moy"]
    assert all(m["derive"] == 0.0 for m in res["maillons"])
    avec0 = solveurChaine(_probleme(decentrage=0, derive=0))
    assert avec0["CF_moy_proc"] == res["CF_moy_proc"]
    assert verdicts(avec0) == verdicts(res)


# ------------------------------------------------------------------ décentrage


@pytest.mark.parametrize("d", [0.5, 1.0, 2.5])
def test_decentrage_vers_jmin(d):
    """Jeu moyen 1,0 mm, Jmin = 0,9 plus proche que Jmax = 1,3 : la moyenne descend de d·σ_J."""
    res = solveurChaine(_probleme(d))
    assert res["CF_sigma"] == pytest.approx(SIGMA_J, rel=1e-12)
    assert res["decalage"] == pytest.approx(-d * SIGMA_J, rel=1e-12)
    assert res["CF_moy_proc"] == pytest.approx(1.0 - d * SIGMA_J, rel=1e-12)
    v = verdicts(res)
    mu = 1.0 - d * SIGMA_J
    assert v["cpk"] == pytest.approx(min(mu - 0.9, 1.3 - mu) / (3 * SIGMA_J), rel=1e-12)
    assert v["ppm"] == pytest.approx(1e6 * (_phi((0.9 - mu) / SIGMA_J) + _phi((mu - 1.3) / SIGMA_J)), rel=1e-9)
    # Cp, pire cas et plages statistiques centrées ne changent pas
    ref = verdicts(solveurChaine(_probleme()))
    assert v["cp"] == ref["cp"] and v["pireCas"] == ref["pireCas"] and v["rssK"] == ref["rssK"]
    assert v["ppm"] > ref["ppm"] and v["cpk"] < ref["cpk"]


def test_decentrage_vers_jmax_si_plus_proche():
    res = solveurChaine(_probleme(1.0, jmin=0.5, jmax=1.1))
    assert res["decalage"] == pytest.approx(+SIGMA_J, rel=1e-12)


def test_decentrage_limite_unique_et_sans_limite():
    assert solveurChaine(_probleme(1.0, jmin=None, jmax=1.2))["decalage"] == pytest.approx(SIGMA_J)
    assert solveurChaine(_probleme(1.0, jmin=0.8, jmax=None))["decalage"] == pytest.approx(-SIGMA_J)
    sans = solveurChaine(_probleme(3.0, jmin=None, jmax=None))
    assert sans["decalage"] == 0.0 and sans["CF_moy_proc"] == sans["CF_moy"]
    assert any(
        "Décentrage sans effet" in t for t in calculerChaine(_probleme(3.0, jmin=None, jmax=None))["avertissements"]
    )


def test_decalageDecentrage_cas_limites():
    assert decalageDecentrage(1.0, 0.1, 0.9, 1.1, 2) == pytest.approx(-0.2)  # égalité : Jmin
    assert decalageDecentrage(1.0, 0.1, 0.9, 1.1, 0) == 0.0
    assert decalageDecentrage(1.0, 0.0, 0.9, 1.1, 2) == 0.0
    assert decalageDecentrage(1.0, 0.1, -math.inf, math.inf, 2) == 0.0


@pytest.mark.parametrize("valeur", [-0.1, math.inf, math.nan, "abc"])
def test_decentrage_invalide_refuse(valeur):
    with pytest.raises(ErreurChaine):
        solveurChaine(_probleme(valeur))


def test_bundle_expose_decentrage():
    b = calculerChaine(_probleme(1.5), n=1000)
    assert b["decentrage"] == 1.5 and b["decalage"] == pytest.approx(-1.5 * SIGMA_J)


def test_risque_selon_cp_utilise_la_moyenne_decalee():
    b = calculerChaine(_probleme(1.0), monteCarlo=False)
    sg1 = SIGMA_J * 3 / 3
    mu = 1.0 - SIGMA_J
    attendu = 1e6 * (_phi((0.9 - mu) / (sg1 / 2)) + _phi((mu - 1.3) / (sg1 / 2)))
    assert b["risque"]["ppm"][3] == pytest.approx(attendu, rel=1e-9)


# ------------------------------------------------------------------ lois


def test_sigma_des_trois_lois():
    """σ = |a| IT/(2k) ; |a| IT/√12 ; |a| (IT/2)/√6."""
    assert coefficientSigma("normale", 3) == pytest.approx(1 / 6)
    assert coefficientSigma("uniforme", 3) == pytest.approx(1 / math.sqrt(12))
    assert coefficientSigma("triangulaire", 3) == pytest.approx(0.1 / 0.2 / math.sqrt(6))
    with pytest.raises(ErreurChaine):
        coefficientSigma("autre", 3)
    res = solveurChaine(_probleme(lois=("triangulaire", "uniforme", "normale")))
    attendu = [0.1 / math.sqrt(6), 0.1 / math.sqrt(12), 0.1 / 6]
    assert list(res["sigma_i"]) == pytest.approx(attendu, rel=1e-12)
    assert res["CF_sigma"] == pytest.approx(math.sqrt(sum(x * x for x in attendu)), rel=1e-12)


def test_triangulaire_nom_de_loi_insensible_a_la_casse_et_avertissement():
    res = solveurChaine(_probleme(lois=("Triangulaire",) * 3))
    assert res["loi"] == ["triangulaire"] * 3
    textes = calculerChaine(_probleme(lois=("triangulaire", "normale", "normale")), n=1000)["avertissements"]
    assert any("Loi non normale" in t and "triangulaire" in t for t in textes)
    textes = calculerChaine(_probleme(), n=1000)["avertissements"]
    assert not any("Loi non normale" in t for t in textes)


def test_loi_inconnue_refusee():
    with pytest.raises(ErreurChaine):
        solveurChaine(_probleme(lois=("gaussienne", "normale", "normale")))


# ------------------------------------------------------------------ Monte-Carlo (1e6 tirages)


def test_montecarlo_triangulaire_moyenne_ecart_type_et_bornes():
    res = solveurChaine(_probleme(lois=("triangulaire", "triangulaire", "triangulaire")))
    mc = simulerMonteCarlo(res, 1_000_000, 7)
    n = mc["n"]
    assert abs(mc["moyenne"] - res["CF_moy"]) < 5 * res["CF_sigma"] / math.sqrt(n)
    assert mc["ecartType"] == pytest.approx(res["CF_sigma"], rel=5e-3)
    assert float(np.max(mc["J"])) <= res["CF_max"] + 1e-6 and float(np.min(mc["J"])) >= res["CF_min"] - 1e-6


def test_montecarlo_decentre_suit_la_formule():
    """Trois lois normales : le jeu est exactement normal, le ppm simulé doit suivre erfc avec la moyenne décalée."""
    res = solveurChaine(_probleme(1.5, jmin=0.95, jmax=1.3))
    mc = simulerMonteCarlo(res, 1_000_000, 11)
    n = mc["n"]
    v = verdicts(res)
    assert abs(mc["moyenne"] - res["CF_moy_proc"]) < 5 * res["CF_sigma"] / math.sqrt(n)
    assert mc["ecartType"] == pytest.approx(res["CF_sigma"], rel=5e-3)
    p = v["ppm"] / 1e6
    assert abs(mc["ppm"] - v["ppm"]) < 1e6 * (5 * math.sqrt(p * (1 - p) / n) + 1 / n)
    assert mc["cpk"] == pytest.approx(v["cpk"], rel=2e-2)


def test_montecarlo_sans_decentrage_inchange():
    a = simulerMonteCarlo(solveurChaine(_probleme()), 5000, 3)["J"]
    b = simulerMonteCarlo(solveurChaine(_probleme(0)), 5000, 3)["J"]
    assert np.array_equal(a, b)


def test_montecarlo_triangulaire_tolerance_nulle():
    p = _probleme(lois=("triangulaire", "normale", "normale"))
    p["maillons"][0]["es"] = p["maillons"][0]["ei"] = 0.0
    mc = simulerMonteCarlo(solveurChaine(p), 2000, 1)
    assert np.isfinite(mc["J"]).all()


# ------------------------------------------------------------------ dérive et fichiers


def test_derive_stockee_validee_et_sans_effet_sur_le_calcul():
    ref = solveurChaine(_probleme())
    res = solveurChaine(_probleme(derive=12.5))
    assert res["maillons"][0]["derive"] == 12.5 and res["maillons"][1]["derive"] == 0.0
    assert res["CF_moy"] == ref["CF_moy"] and res["CF_sigma"] == ref["CF_sigma"]
    for mauvais in ("x", math.inf):
        with pytest.raises(ErreurChaine):
            solveurChaine(_probleme(derive=mauvais))


def test_aller_retour_projet_io():
    p = _probleme(1.25, lois=("triangulaire", "uniforme", "normale"), derive=3.5)
    relu = importerProbleme(exporterProbleme(p))
    assert relu == p
    assert relu["reglages"]["decentrage"] == 1.25 and relu["maillons"][0]["derive"] == 3.5
    assert solveurChaine(relu)["decalage"] == solveurChaine(p)["decalage"]


@pytest.mark.parametrize("champ", ["decentrage", "derive"])
def test_import_refuse_valeurs_invalides(champ):
    p = copy.deepcopy(_probleme(1.0, derive=1.0))
    cible = p["reglages"] if champ == "decentrage" else p["maillons"][0]
    for mauvais in ("abc", True, -1.0 if champ == "decentrage" else "x"):
        cible[champ] = mauvais
        with pytest.raises(ErreurChaine):
            importerProbleme(exporterProbleme(p))


def test_csv_donne_le_decentrage_seulement_s_il_est_actif():
    avec = exporterResultatsCsv(calculerChaine(_probleme(1.0), n=2000)).decode("utf-8-sig")
    sans = exporterResultatsCsv(calculerChaine(_probleme(), n=2000)).decode("utf-8-sig")
    assert "Décentrage du procédé" in avec and "Décentrage du procédé" not in sans


# ------------------------------------------------------------------ dossier de validation et explications


@pytest.mark.parametrize(
    "p",
    [
        _probleme(),
        _probleme(1.5),
        _probleme(2.0, lois=("triangulaire", "normale", "normale"), derive=4.0),
        _probleme(1.0, lois=("triangulaire",) * 3, jmin=None, jmax=1.2),
    ],
    ids=["defaut", "decentre", "decentre+triangulaire", "limite unique"],
)
def test_dossier_validation_sans_ecart(p):
    d = dossierValidation(p, calculerChaine(p, n=100_000))
    ecarts = [c["nom"] for c in d["controles"] if c["statut"] != "OK"]
    assert not ecarts
    noms = [c["nom"] for c in d["controles"]]
    assert ("Décalage de la moyenne" in noms) == (p["reglages"].get("decentrage", 0) > 0)


def test_dossier_detecte_un_decalage_errone():
    p = _probleme(1.5)
    b = calculerChaine(p, n=1000)
    b["res"]["decalage"] += 1e-3
    d = dossierValidation(p, b)
    assert any(c["nom"] == "Décalage de la moyenne" and c["statut"] == "ÉCART" for c in d["controles"])


def test_explications_section_decentrage_seulement_si_actif():
    titres = [s["titre"] for s in explicationsCalcul(calculerChaine(_probleme(), n=1000))]
    assert not any("Décentrage" in t for t in titres)
    sections = explicationsCalcul(calculerChaine(_probleme(1.5), n=1000))
    dec = [s for s in sections if "Décentrage" in s["titre"]]
    assert len(dec) == 1 and "1,5" in dec[0]["texte"] and dec[0]["formules"]
    assert any("triangulaire" in f for f in explicationsCalcul(calculerChaine(_probleme(), n=1000))[4]["formules"])
