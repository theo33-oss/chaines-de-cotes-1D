"""Allocation au coût minimal : comparaison à scipy (SLSQP), saturation par les bornes, maillons figés, erreurs."""

import numpy as np
import pytest
from scipy.optimize import minimize

from chainecotes.core import cout, iso286
from chainecotes.core.errors import ErreurChaine
from chainecotes.core.inverse import repartirTolerances
from chainecotes.services.exemples import chargerExemple

EXEMPLE = "ajustements_h7_h6_n7"


def _p(jmax=1.2):
    p = chargerExemple(EXEMPLE)
    p["condition"]["jmax"] = jmax
    return p


def _ref(r):
    """Données indépendantes du moteur de coût : a_i, IT_i (mm), k, lois, à partir de la vérification."""
    v = r["verification"]
    return np.abs(v["coef"]), np.array([m["IT"] for m in r["maillons"]]), v["k_sigma"], v["loi"]


def _bornes(r, mod, libres):
    return tuple(
        [iso286.toleranceIT(r["maillons"][i]["cote"], mod[i][k]) / 1000 for i in libres] for k in ("itmin", "itmax")
    )


def _slsqp(r, critere, mod, libres):
    """Optimum numérique du même problème (maillons libres seulement), contrainte écrite à la main."""
    a, it, k, loi = _ref(r)
    cs = np.array([1 / (2 * k) if x == "normale" else 1 / np.sqrt(12) for x in loi])
    c = np.array([mod[i]["c"] for i in libres])
    n = np.array([mod[i]["n"] for i in libres])
    lo, hi = _bornes(r, mod, libres)

    def g(x):
        full = it.copy()
        full[libres] = x
        if critere == "pire_cas":
            return r["budget"] - float(np.sum(a * full))
        return r["budget"] - 2 * k * float(np.sqrt(np.sum((a * full * cs) ** 2)))

    s = minimize(
        lambda y: float(np.sum(c * (np.exp(y) / cout.refIT()) ** (-n))) / 10,
        np.log((np.array(lo) + np.array(hi)) / 2),
        bounds=list(zip(np.log(lo), np.log(hi), strict=True)),
        constraints=[{"type": "ineq", "fun": lambda y: g(np.exp(y)) * 100}],
        method="SLSQP",
        options={"ftol": 1e-14, "maxiter": 500},
    )
    x = np.exp(s.x)
    return x, float(np.sum(c * (x / cout.refIT()) ** (-n)))


def _modeles(specs):
    return [cout.modeleMaillon(s) for s in specs]


@pytest.mark.parametrize("critere", ["pire_cas", "statistique"])
@pytest.mark.parametrize(
    "specs",
    [
        None,
        [{"c": 1.0, "n": 1.0}, {"c": 4.0, "n": 1.0}, {"c": 2.0, "n": 1.0}],
        [{"c": 1.0, "n": 0.7}, {"c": 3.0, "n": 1.5}, {"c": 2.0, "n": 1.1}],
    ],
)
def test_comparaison_slsqp(specs, critere):
    r = repartirTolerances(_p(), "cout_minimal", critere, couts=specs)
    assert r["tenue"]
    x, f = _slsqp(r, critere, _modeles(specs or [None] * 3), [0, 1, 2])
    assert r["cout"]["total"] == pytest.approx(f, rel=1e-5)
    assert [m["IT"] for m in r["maillons"]] == pytest.approx(list(x), rel=1e-3)


def test_forme_fermee_pire_cas_n_identique():
    """n identique : IT_i proportionnel à (c_i/|a_i|)^(1/(n+1)), contrainte tenue à l'égalité."""
    specs = [{"c": 1.0, "n": 1.5}, {"c": 5.0, "n": 1.5}, {"c": 2.0, "n": 1.5}]
    r = repartirTolerances(_p(), "cout_minimal", "pire_cas", couts=specs)
    a, it, _, _ = _ref(r)
    attendu = (np.array([1.0, 5.0, 2.0]) / a) ** (1 / 2.5)
    assert it / attendu == pytest.approx([it[0] / attendu[0]] * 3, rel=1e-9)
    assert float(np.sum(a * it)) == pytest.approx(r["budget"], rel=1e-9)


def test_gain_positif_et_optimalite():
    specs = [{"c": 1.0, "n": 1.0}, {"c": 8.0, "n": 1.0}, {"c": 1.0, "n": 1.0}]
    r = repartirTolerances(_p(), "cout_minimal", "pire_cas", couts=specs)
    assert r["cout"]["gainEgale"] > 0 and r["cout"]["gainProportionnelle"] > 0
    assert r["cout"]["total"] <= min(r["cout"]["egale"], r["cout"]["proportionnelle"])


def test_satures_par_les_bornes():
    """Une rectification limitée à IT4-IT5 sature sa borne haute ; l'optimum reste celui de SLSQP."""
    specs = [{"procede": "rectification", "itmin": 4, "itmax": 5}, None, None]
    r = repartirTolerances(_p(), "cout_minimal", "pire_cas", couts=specs)
    cote0 = r["maillons"][0]["cote"]
    assert r["maillons"][0]["IT"] == pytest.approx(iso286.toleranceIT(cote0, 5) / 1000, rel=1e-9)
    assert r["tenue"]
    _, f = _slsqp(r, "pire_cas", _modeles(specs), [0, 1, 2])
    assert r["cout"]["total"] == pytest.approx(f, rel=1e-5)


def test_tout_au_plus_large_si_budget_enorme():
    """Si tout à ITmax tient déjà, on s'arrête à ITmax (le coût ne baisse plus)."""
    r = repartirTolerances(_p(50.0), "cout_minimal", "pire_cas", couts=[{"itmax": 7}] * 3)
    for m in r["maillons"]:
        assert m["IT"] == pytest.approx(iso286.toleranceIT(m["cote"], 7) / 1000, rel=1e-9)
    assert r["tenue"]


def test_maillon_fige():
    r = repartirTolerances(_p(), "cout_minimal", "pire_cas", figes=[1])
    arbre = iso286.lireDesignation("h6", 50.0)
    assert r["maillons"][1]["fige"] and r["maillons"][1]["es"] == pytest.approx(arbre["es"], abs=1e-12)
    assert r["tenue"] and len(r["cout"]["procedes"]) == 2
    a, it, _, _ = _ref(r)
    assert float(np.sum(a * it)) == pytest.approx(r["budget"], rel=1e-9)
    x, f = _slsqp(r, "pire_cas", _modeles([None] * 3), [0, 2])
    assert r["cout"]["total"] == pytest.approx(f, rel=1e-5)
    assert [r["maillons"][0]["IT"], r["maillons"][2]["IT"]] == pytest.approx(list(x), rel=1e-3)


def test_arrondi_iso():
    r = repartirTolerances(_p(), "cout_minimal", "pire_cas", arrondi=True)
    assert r["tenue"]
    a, it, _, _ = _ref(r)
    assert float(np.sum(a * it)) <= r["budget"] * (1 + 1e-12)
    for m in r["maillons"]:
        q = int(m["designation"][2:])
        assert m["IT"] == pytest.approx(iso286.toleranceIT(m["cote"], q) / 1000, rel=1e-9)
    libre = repartirTolerances(_p(), "cout_minimal", "pire_cas")
    assert r["cout"]["total"] >= libre["cout"]["total"] * (1 - 1e-12)  # l'arrondi ne bat pas l'optimum continu


def test_statistique_moins_cher_que_pire_cas():
    pc = repartirTolerances(_p(), "cout_minimal", "pire_cas")
    st = repartirTolerances(_p(), "cout_minimal", "statistique")
    assert st["cout"]["total"] < pc["cout"]["total"]


def test_procedes_json_et_modele():
    ids = {p["id"] for p in cout.listeProcedes()}
    assert {"tournage", "rectification", "injection_plastique", "tolerie_laser", "generique"} <= ids
    m = cout.modeleMaillon({"procede": "tournage", "c": 2.5})
    assert m["c"] == 2.5 and m["itmin"] == 6


@pytest.mark.parametrize(
    ("spec", "ident"),
    [
        ({"c": 0}, "Chaine:Cout:c"),
        ({"c": -1}, "Chaine:Cout:c"),
        ({"n": 0}, "Chaine:Cout:n"),
        ({"procede": "inconnu"}, "Chaine:Cout:procede"),
        ({"itmin": 9, "itmax": 7}, "Chaine:Cout:qualites"),
    ],
)
def test_erreurs_modele(spec, ident):
    with pytest.raises(ErreurChaine) as e:
        repartirTolerances(_p(), "cout_minimal", couts=[spec, None, None])
    assert e.value.identifiant == ident


def test_erreur_aucune_solution():
    """Procédés grossiers (IT12 minimum) sur un jeu visible étroit : aucune solution."""
    with pytest.raises(ErreurChaine) as e:
        repartirTolerances(_p(1.04), "cout_minimal", couts=[{"itmin": 12, "itmax": 14}] * 3)
    assert e.value.identifiant == "Chaine:Cout:infaisable"


def test_erreur_nombre_de_couts():
    with pytest.raises(ErreurChaine) as e:
        repartirTolerances(_p(), "cout_minimal", couts=[None])
    assert e.value.identifiant == "Chaine:Inverse:couts"


def test_defaut_inchange():
    """Les méthodes existantes ne changent pas (pas de clé « cout »)."""
    assert "cout" not in repartirTolerances(_p(), "egale")
