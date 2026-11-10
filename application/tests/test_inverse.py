"""Problème inverse : repartirTolerances tient la cote condition, à l'égalité du critère pour les méthodes continues."""

import math

import numpy as np
import pytest

from chainecotes.core import iso286
from chainecotes.core.errors import ErreurChaine
from chainecotes.core.inverse import CRITERES, repartirTolerances
from chainecotes.services.exemples import chargerExemple

EXEMPLE = "ajustements_h7_h6_n7"
REL = 1e-9


def _probleme() -> dict:
    return chargerExemple(EXEMPLE)


def _critere(res: dict, critere: str) -> float:
    """Largeur consommée : Σ |a_i|·IT_i au pire des cas, 2·k·σ_J en statistique (mm)."""
    if critere == "pire_cas":
        return float(np.sum(np.abs(res["coef"]) * res["IT"]))
    return 2 * res["k_sigma"] * res["CF_sigma"]


@pytest.mark.parametrize("critere", CRITERES)
@pytest.mark.parametrize("methode", ["egale", "proportionnelle"])
def test_methodes_continues_a_l_egalite(methode, critere):
    r = repartirTolerances(_probleme(), methode, critere)
    assert r["tenue"]
    assert _critere(r["verification"], critere) == pytest.approx(r["budget"], rel=REL)
    c = r["verification"]["condition"]
    assert r["verification"]["CF_moy"] == pytest.approx((c["jmin"] + c["jmax"]) / 2, rel=REL)
    if methode == "egale":
        its = [m["IT"] for m in r["maillons"]]
        assert its == pytest.approx([its[0]] * len(its), rel=REL)


@pytest.mark.parametrize("critere", CRITERES)
def test_iso_qualite_la_plus_grossiere(critere):
    """La qualité choisie tient ; la qualité juste au-dessus (plus grossière) ne tient pas."""
    p = _probleme()
    r = repartirTolerances(p, "iso", critere)
    assert r["tenue"]
    q = r["qualite"]
    assert _critere(r["verification"], critere) <= r["budget"] + 1e-12
    if q < max(iso286.QUALITES):
        res = r["verification"]
        it = np.array([iso286.toleranceIT(m["cote"], q + 1) / 1000 for m in r["maillons"]])
        a = np.abs(res["coef"])
        k = res["k_sigma"]
        large = (
            float(np.sum(a * it))
            if critere == "pire_cas"
            else 2 * k * math.sqrt(float(np.sum((a * it / (2 * k)) ** 2)))
        )
        assert large > r["budget"]


@pytest.mark.parametrize("critere", CRITERES)
@pytest.mark.parametrize("methode", ["egale", "proportionnelle", "iso"])
def test_maillon_fige_conserve(methode, critere):
    p = _probleme()
    p["condition"]["jmax"] = 1.2  # budget assez large pour garder l'arbre h6 figé
    r = repartirTolerances(p, methode, critere, figes=[1])
    arbre = iso286.lireDesignation("h6", 50.0)
    assert r["maillons"][1]["fige"]
    assert r["maillons"][1]["es"] == pytest.approx(arbre["es"], abs=1e-12)
    assert r["maillons"][1]["ei"] == pytest.approx(arbre["ei"], abs=1e-12)
    assert r["tenue"]


def test_erreur_tout_fige():
    with pytest.raises(ErreurChaine) as e:
        repartirTolerances(_probleme(), "egale", "pire_cas", figes=[0, 1, 2])
    assert e.value.identifiant == "Chaine:Inverse:figes"


def test_erreur_limite_manquante():
    p = _probleme()
    p["condition"]["jmax"] = None
    with pytest.raises(ErreurChaine) as e:
        repartirTolerances(p, "egale", "pire_cas")
    assert e.value.identifiant == "Chaine:Inverse:limites"


def test_erreur_budget_consomme():
    """L'alésage H7 (IT 0,035 mm) figé dépasse déjà le budget 1,06 − 1,03 = 0,03 mm."""
    with pytest.raises(ErreurChaine) as e:
        repartirTolerances(_probleme(), "egale", "pire_cas", figes=[0])
    assert e.value.identifiant == "Chaine:Inverse:budget"
