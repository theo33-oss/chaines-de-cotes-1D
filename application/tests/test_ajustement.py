"""Tests de l'assistant de choix d'ajustement."""

import pytest

from chainecotes.core.ajustement import choisirAjustement, fonctionsDisponibles
from chainecotes.core.errors import ErreurChaine
from chainecotes.core.iso286 import holeDeviations, shaftDeviations, toleranceIT


def test_jeuxRecalculesIso286():
    # H7/g6 à 25 mm : H7 = 0/+21 µm, g6 = -7/-20 µm -> jeu 0,007 à 0,041 mm (valeurs ISO 286-2)
    r = {c["designation"]: c for c in choisirAjustement(25, "glissant")}["H7/g6"]
    assert (r["jeuMini"], r["jeuMaxi"]) == pytest.approx((0.007, 0.041))
    h, a = holeDeviations(25, "H", 7), shaftDeviations(25, "g", 6)
    assert r["jeuMini"] == pytest.approx((h["EI"] - a["es"]) / 1000)
    assert r["jeuMaxi"] == pytest.approx((h["ES"] - a["ei"]) / 1000)
    assert (r["ITAlesage"], r["ITArbre"]) == (toleranceIT(25, 7), toleranceIT(25, 6))


@pytest.mark.parametrize("cote", [4, 12, 25, 60, 150, 300])
@pytest.mark.parametrize("systeme", ["alesage", "arbre"])
def test_coherenceNatureEtRang(cote, systeme):
    for fonction in fonctionsDisponibles():
        liste = choisirAjustement(cote, fonction, systeme)
        assert [c["rang"] for c in liste] == list(range(1, len(liste) + 1))
        for c in liste:
            assert c["jeuMini"] <= c["jeuMaxi"]
            assert c["nature"] == ("avec jeu" if c["jeuMini"] >= 0 else "serré" if c["jeuMaxi"] <= 0 else "incertain")


def test_fonctionsDonnentLeBonTypeDAjustement():
    assert choisirAjustement(40, "libre")[0]["designation"] == "H11/c11"
    assert choisirAjustement(40, "pressage_fort")[0]["nature"] == "serré"
    assert choisirAjustement(40, "tournant", "arbre")[0]["designation"] == "F8/h7"
    assert choisirAjustement(40, "libre", "arbre")[0]["nature"] == "avec jeu"


def test_jsImpairArrondi():
    # IT7 = 21 µm à 25 mm (impair) : JS7 = ±10,5 (MATLAB) ou ±10 (ISO arrondi)
    k = lambda a: {c["designation"]: c for c in choisirAjustement(25, "main", "arbre", a)}["JS7/h6"]  # noqa: E731
    assert k(False)["jeuMini"] == pytest.approx(-0.0105)
    assert k(True)["jeuMini"] == pytest.approx(-0.010)
    assert k(False)["avertissement"]


def test_pieceInexistanteEcartee():
    # H11/c11 : c n'existe pas au-delà de 500 mm dans ce cas ; on vérifie qu'aucune erreur ne sort
    assert isinstance(choisirAjustement(900, "libre"), list)


@pytest.mark.parametrize(
    "args",
    [(0, "libre"), (-5, "libre"), (5000, "libre"), (25, "inconnue"), (25, "libre", "autre")],
)
def test_erreurs(args):
    with pytest.raises(ErreurChaine):
        choisirAjustement(*args)
