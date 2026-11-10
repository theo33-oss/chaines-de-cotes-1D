"""Contrôles de cohérence : chaque contrôle sur un cas fait à la main, jamais d'exception."""

import copy

import pytest

from chainecotes.services.controles import controlerProbleme
from chainecotes.services.exemples import chargerExemple, listeExemples


def _maillon(nom, sens, cote, es=0.05, ei=-0.05, **kw):
    return {"nom": nom, "sens": sens, "cote": cote, "iso": None, "es": es, "ei": ei, "loi": "normale", **kw}


def _probleme(maillons, jmin=0.8, jmax=1.2, **reglages):
    return {"condition": {"nom": "Jeu J", "jmin": jmin, "jmax": jmax}, "reglages": reglages, "maillons": maillons}


BON = [_maillon("Carter", "+", 100), _maillon("Bague", "-", 40), _maillon("Moyeu", "-", 59)]  # jeu nominal 1


def _codes(p, niveau=None):
    return {c["code"] for c in controlerProbleme(p) if niveau in (None, c["niveau"])}


def test_probleme_sain_sans_erreur_ni_avertissement():
    assert controlerProbleme(_probleme(BON)) == []


@pytest.mark.parametrize("ident", [e["id"] for e in listeExemples()])
def test_exemples_sans_erreur(ident):
    assert _codes(chargerExemple(ident), "erreur") == set()


def test_condition_inatteignable_est_une_erreur():
    p = _probleme(BON, jmin=5, jmax=6)  # pire des cas [0,8 ; 1,2] hors de [5 ; 6]
    (c,) = [c for c in controlerProbleme(p) if c["code"] == "conditionInatteignable"]
    assert c["niveau"] == "erreur" and c["maillon"] is None


def test_jeu_moyen_hors_condition_mais_pire_cas_qui_recouvre():
    # moyen 1, demi-dispersion 0,15 : pire des cas [0,85 ; 1,15] ; condition [1,1 ; 3] : recouvrement partiel
    assert "moyenneHorsCondition" in _codes(_probleme(BON, jmin=1.1, jmax=3), "avertissement")


def test_nominal_hors_condition_seul_est_une_info():
    m = [_maillon("A", "+", 100, es=0.4, ei=0.2), _maillon("B", "-", 99, es=0, ei=0)]  # nominal 1, moyen 1,3
    c = controlerProbleme(_probleme(m, jmin=1.1, jmax=1.5))
    assert {x["code"]: x["niveau"] for x in c}["nominalHorsCondition"] == "info"
    assert "moyenneHorsCondition" not in {x["code"] for x in c}


def test_chaine_non_fermee_et_maillon_invalide_sont_listes():
    p = _probleme([_maillon("A", "+", 10), _maillon("B", "+", 5)])
    assert "nonFermee" in _codes(p, "erreur")
    p = _probleme([_maillon("A", "+", 10), _maillon("B", "-", "abc")])
    (c,) = [c for c in controlerProbleme(p) if c["niveau"] == "erreur"]
    assert c["maillon"] == "B" and "nombre" in c["message"]


def test_unite_aberrante_et_tolerance_superieure_a_la_cote():
    m = [_maillon("A", "+", 100), _maillon("B", "-", 0.4), _maillon("C", "-", 99.6)]
    c = [x for x in controlerProbleme(_probleme(m)) if x["code"] == "uniteAberrante"]
    assert [x["maillon"] for x in c] == ["B"]  # 100 / 99,8 et 99,6 / 99,8 ne sont pas aberrants
    m = [_maillon("A", "+", 100), _maillon("B", "-", 1, es=1.5, ei=-1.5), _maillon("C", "-", 99)]
    assert "toleranceSuperieureCote" in _codes(_probleme(m, jmin=-9, jmax=9), "avertissement")


def test_tolerance_nulle_et_ecarts_inverses():
    m = [_maillon("A", "+", 100, es=0, ei=0), _maillon("B", "-", 99)]
    assert "toleranceNulle" in _codes(_probleme(m, jmin=0, jmax=2))
    m = [_maillon("A", "+", 100, es=-0.1, ei=0.1), _maillon("B", "-", 99)]
    (c,) = [x for x in controlerProbleme(_probleme(m)) if x["niveau"] == "erreur"]
    assert c["code"] == "ecartsInverses" and c["maillon"] == "A"


def test_sens_douteux_en_info_seulement():
    m = [_maillon("A", "-", 100), _maillon("B", "+", 99)]  # jeu nominal -1 pour une condition positive
    c = [x for x in controlerProbleme(_probleme(m, jmin=0.5, jmax=1.5)) if x["code"] == "sensDouteux"]
    assert len(c) == 1 and c[0]["niveau"] == "info"


def test_loi_k_et_iso():
    m = copy.deepcopy(BON)
    m[0]["loi"] = "triangle"
    assert "loi" in _codes(_probleme(m), "erreur")
    assert "kAtypique" in _codes(_probleme(BON, kSigma=1), "avertissement")
    assert "kAtypique" not in _codes(_probleme(BON, kSigma=3))
    assert "kSigma" in _codes(_probleme(BON, kSigma=-1), "erreur")
    m = copy.deepcopy(BON)
    m[0]["iso"] = "Z99"
    assert "isoNonReconnue" in _codes(_probleme(m), "erreur")
    m[0]["iso"] = "H7"
    m[0]["cote"] = 100  # H7 sans cote dans le texte : lue sur la cote saisie, donc cohérente
    assert "isoNonReconnue" not in _codes(_probleme(m))
    m[0]["iso"] = "50H7"
    assert "isoCoteDifferente" in _codes(_probleme(m), "erreur")


def test_thermique_hors_domaine_et_dilatation_absente():
    m = copy.deepcopy(BON)
    m[0]["materiau"] = "Acier C45"
    c = controlerProbleme(_probleme(m, tref=20, modeT="uniforme", tservice=5000))
    assert "temperatureHorsDomaine" in {x["code"] for x in c}
    assert "dilatationAbsente" not in {x["code"] for x in c}
    assert "dilatationAbsente" in _codes(_probleme(BON, tref=20, modeT="uniforme", tservice=80))
    m = copy.deepcopy(BON)
    m[1]["tservice"] = 90
    c = [x for x in controlerProbleme(_probleme(m, modeT="par_cote")) if x["code"] == "dilatationAbsente"]
    assert [x["maillon"] for x in c] == ["Bague"]


def test_condition_sans_limite():
    assert "conditionSansLimite" in _codes(_probleme(BON, jmin=None, jmax=None), "info")


@pytest.mark.parametrize(
    "p",
    [None, 3, "x", {}, {"maillons": 4}, {"maillons": [None, 3, {}]}, {"condition": 5, "reglages": [], "maillons": []},
     {"maillons": [{"sens": "+", "cote": float("nan")}]}],
)  # fmt: skip
def test_ne_leve_jamais(p):
    c = controlerProbleme(p)
    assert c and all(x["niveau"] in ("erreur", "avertissement", "info") and x["message"] for x in c)
