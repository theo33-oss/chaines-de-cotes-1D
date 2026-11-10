"""Écarts ISO 286 : lireDesignation redonne ajustementISO.m (tests/golden/golden_iso286.json, en mm).

Écart connu (docs/ECARTS_MATLAB.md) : pour js/JS d'IT impair en qualités 7 à 11, MATLAB garde ± IT/2 alors que
ISO 286-1 arrondit au pair inférieur. Le site garde la valeur MATLAB par défaut et affiche un avertissement ;
arrondiJs=True donne la valeur normalisée de MecaStruct.
"""

import pytest

from chainecotes.core import iso286
from chainecotes.core.errors import ErreurChaine
from tests.golden_tools import casGolden, chargerGolden

GOLDEN = "golden_iso286.json"
CAS = casGolden(GOLDEN)
CAS_OK = [c for c in CAS if not c["erreur"]]
CAS_REFUS = [c for c in CAS if c["erreur"]]
TOL = 1e-12  # mm


def _id(c: dict) -> str:
    return f"{c['cote']:g}_{c['ajustement']}"


def _jsImpair(c: dict) -> bool:
    lettre = c["ajustement"].rstrip("0123456789")
    q = int(c["ajustement"][len(lettre) :])
    return lettre.lower() == "js" and 7 <= q <= 11 and iso286.toleranceIT(c["cote"], q) % 2 == 1


@pytest.mark.parametrize("c", CAS_OK, ids=_id)
def test_ecarts_comme_matlab(c):
    r = iso286.lireDesignation(c["ajustement"], c["cote"], arrondiJs=False)
    assert abs(r["es"] - c["ES"]) <= TOL, f"es {r['es']} contre MATLAB {c['ES']}"
    assert abs(r["ei"] - c["EI"]) <= TOL, f"ei {r['ei']} contre MATLAB {c['EI']}"
    assert bool(r["avertissement"]) == _jsImpair(c)


def test_nombre_de_js_impairs():
    """80 cas sur 2800 portent l'écart MATLAB / ISO 286-1 de js / JS."""
    chargerGolden(GOLDEN)
    assert len(CAS_OK) == 2800
    assert sum(_jsImpair(c) for c in CAS_OK) == 80


@pytest.mark.parametrize("c", [c for c in CAS_OK if _jsImpair(c)], ids=_id)
def test_js_impair_arrondi_iso(c):
    """arrondiJs=True : IT ramené au pair inférieur puis divisé par 2 (ISO 286-1, comme MecaStruct)."""
    q = int(c["ajustement"][2:])
    it = iso286.toleranceIT(c["cote"], q)
    r = iso286.lireDesignation(c["ajustement"], c["cote"], arrondiJs=True)
    assert abs(r["es"] - (it - 1) / 2 / 1000) <= TOL
    assert abs(r["ei"] + (it - 1) / 2 / 1000) <= TOL
    assert r["avertissement"] == ""
    # MATLAB : ± IT/2 exactement
    assert abs(c["ES"] - it / 2 / 1000) <= TOL


@pytest.mark.parametrize("c", CAS_REFUS, ids=_id)
def test_refus_matlab_calcules_par_le_site(c):
    """MATLAB refuse K, M, N, P hors IT7 et k au-delà de IT7 ; le site lit toute la table ISO 286 de MecaStruct.

    Pas d'échec attendu ici : soit le site calcule des écarts cohérents (ES ≥ EI, IT de la table), soit il
    refuse à son tour avec une ErreurChaine claire.
    """
    try:
        r = iso286.lireDesignation(c["ajustement"], c["cote"])
    except ErreurChaine as e:
        assert e.message
        return
    q = r["qualite"]
    assert r["es"] >= r["ei"]
    assert abs((r["es"] - r["ei"]) * 1000 - iso286.toleranceIT(c["cote"], q)) <= 1e-9
