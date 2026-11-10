"""Tolérances géométriques ISO 1101 comme maillons de la chaîne."""

import pytest

from chainecotes.core.chaine import solveurChaine
from chainecotes.core.errors import ErreurChaine
from chainecotes.core.geometrie import TYPES, maillonGeometrique
from chainecotes.plots.schema import figureSchema
from chainecotes.services.calcul import calculerChaine
from chainecotes.services.cotation import tableauCotation
from chainecotes.services.exemples import chargerExemple
from chainecotes.services.projet_io import exporterProbleme, importerProbleme
from chainecotes.services.validation import dossierValidation


def _avec(type_="planeite", t=0.05, **kw):
    p = chargerExemple("ajustements_h7_h6_n7")
    p["maillons"].append(maillonGeometrique(type_, t, **kw))
    return p


def test_maillon_geometrique():
    m = maillonGeometrique("parallelisme", 0.04, sens="-", bonus=0.01)
    assert (m["cote"], m["es"], m["ei"], m["sens"], m["geometrie"]) == (0.0, 0.025, -0.025, "-", "parallelisme")
    assert "Ⓜ" in m["nom"] and "∥" in m["nom"]


@pytest.mark.parametrize("mauvais", [{"type_": "rond"}, {"t": 0}, {"t": float("nan")}, {"bonus": -1}])
def test_entrees_refusees(mauvais):
    with pytest.raises(ErreurChaine):
        _avec(**mauvais)


@pytest.mark.parametrize("type_", list(TYPES))
def test_chaque_type_se_calcule_et_se_valide(type_):
    p = _avec(type_)
    ref = solveurChaine(chargerExemple("ajustements_h7_h6_n7"))
    res = solveurChaine(p)
    assert res["CF_nom"] == ref["CF_nom"]  # cote nulle : le jeu nominal ne bouge pas
    assert res["CF_max"] - res["CF_min"] == pytest.approx(ref["CF_max"] - ref["CF_min"] + 0.05)  # + IT = t
    d = dossierValidation(p, calculerChaine(p, n=20000))
    assert d["nOk"] == d["nTotal"]


def test_schema_fichier_et_cotation():
    p = _avec("planeite", 0.05)
    fig, _ = figureSchema(p)
    assert fig is not None
    assert importerProbleme(exporterProbleme(p))["maillons"][-1]["geometrie"] == "planeite"
    derniere = tableauCotation(p)[-1]
    assert "ISO 1101" in derniere["remarque"] and derniere["it"] == pytest.approx(0.05)


def test_geometrie_inconnue_dans_un_fichier():
    p = _avec()
    p["maillons"][-1]["geometrie"] = "rond"
    with pytest.raises(ErreurChaine):
        importerProbleme(exporterProbleme(p))
