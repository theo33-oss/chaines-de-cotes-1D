"""Tolérances générales ISO 2768-1 : table, maillon sans écarts, réglage, aller-retour fichier, tableau de cotation."""

import pytest

from chainecotes.core.chaine import solveurChaine
from chainecotes.core.errors import ErreurChaine
from chainecotes.core.iso2768 import tolGenerale
from chainecotes.services.cotation import tableauCotation
from chainecotes.services.projet_io import exporterProbleme, importerProbleme
from chainecotes.services.validation import dossierValidation


def _probleme(classe=None):
    reglages = {"kSigma": 3, "tref": 20.0, "modeT": "uniforme", "tservice": 20.0}
    if classe:
        reglages["tolGenerale"] = classe
    return {
        "condition": {"nom": "J", "jmin": 0.2, "jmax": 1.5},
        "reglages": reglages,
        "maillons": [
            {"nom": "A", "sens": "+", "cote": 50.0},  # sans écarts : tolérance générale
            {"nom": "B", "sens": "-", "cote": 40.0, "iso": "h7"},
            {"nom": "C", "sens": "-", "cote": 9.0, "es": 0.05, "ei": -0.05},
        ],
    }


@pytest.mark.parametrize("cote, classe, attendu", [(50, "m", 0.3), (50, "f", 0.15), (2, "c", 0.2), (3, "m", 0.1),
                                                   (3.1, "c", 0.3), (500, "v", 4.0), (1000, "v", 4.0), (6, "v", 0.5)])
def test_table(cote, classe, attendu):
    assert tolGenerale(cote, classe) == attendu


@pytest.mark.parametrize("cote, classe", [(0.3, "m"), (1000.5, "m"), (5000, "m"), (2, "v"), (3000, "f"), (50, "z")])
def test_hors_table_refuse(cote, classe):
    with pytest.raises(ErreurChaine):
        tolGenerale(cote, classe)


def test_maillon_sans_ecarts_prend_la_classe():
    res = solveurChaine(_probleme("m"))
    a = res["maillons"][0]
    assert (a["es"], a["ei"], a["origine"]) == (0.3, -0.3, "2768-m")
    assert res["maillons"][1]["origine"] == "" and res["maillons"][2]["origine"] == ""  # ISO 286 et écarts saisis


def test_sans_reglage_l_erreur_reste():
    with pytest.raises(ErreurChaine, match="écart supérieur"):
        solveurChaine(_probleme())


def test_cote_hors_table_dit_le_maillon():
    p = _probleme("m")
    p["maillons"][0]["cote"] = 0.2
    with pytest.raises(ErreurChaine, match="Maillon 1 .*A"):
        solveurChaine(p)


def test_aller_retour_fichier_cotation_et_dossier():
    p = importerProbleme(exporterProbleme(_probleme("c")))
    assert p["reglages"]["tolGenerale"] == "c"
    ligne = tableauCotation(p)[0]
    assert "ISO 2768-c" in ligne["remarque"] and "0,8" in ligne["remarque"]
    d = dossierValidation(p)
    assert d["nOk"] == d["nTotal"]
