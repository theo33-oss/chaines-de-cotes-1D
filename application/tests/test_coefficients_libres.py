"""Coefficients de projection libres : facteur (levier) et angle, sans effet quand ils sont absents."""

import math

import pytest

from chainecotes.core.chaine import solveurChaine
from chainecotes.core.errors import ErreurChaine
from chainecotes.services.calcul import calculerChaine
from chainecotes.services.controles import controlerProbleme
from chainecotes.services.exemples import chargerExemple
from chainecotes.services.projet_io import exporterProbleme, importerProbleme
from chainecotes.services.validation import dossierValidation


def _probleme(**plus):
    """Levier de 40 mm contre une bague de 20 mm ; `plus` complète le premier maillon."""
    return {
        "condition": {"nom": "Jeu", "jmin": 0.0, "jmax": 2.0},
        "reglages": {"kSigma": 3, "tref": 20.0, "modeT": "uniforme", "tservice": 20.0},
        "maillons": [
            {"nom": "Levier", "sens": "+", "cote": 40.0, "es": 0.1, "ei": -0.1, **plus},
            {"nom": "Bague", "sens": "-", "cote": 20.0, "es": 0.05, "ei": -0.05},
        ],
    }


def test_defaut_inchange():
    p = chargerExemple("ajustements_h7_h6_n7")
    avec = {**p, "maillons": [{**m, "facteur": 1.0, "angle": 0.0} for m in p["maillons"]]}
    a, b = solveurChaine(p), solveurChaine(avec)
    assert list(a["coef"]) == list(b["coef"])
    assert a["CF_min"] == b["CF_min"] and a["CF_sigma"] == b["CF_sigma"]


def test_facteur_multiplie_le_coefficient():
    res = solveurChaine(_probleme(facteur=0.5))
    assert list(res["coef"]) == pytest.approx([0.5, -1.0])
    assert res["CF_nom"] == pytest.approx(0.5 * 40 - 20)
    assert res["CF_max"] - res["CF_moy"] == pytest.approx(0.5 * 0.1 + 0.05)  # Σ |a|·IT/2


def test_angle_donne_cosinus():
    res = solveurChaine(_probleme(angle=60.0))
    assert res["coef"][0] == pytest.approx(math.cos(math.radians(60)))
    sens_moins = _probleme()
    sens_moins["maillons"][1]["angle"] = 60.0
    assert solveurChaine(sens_moins)["coef"][1] == pytest.approx(-0.5)  # θ = 180° + 60°, cos = −0,5


def test_facteur_invalide():
    for mauvais in (0.0, -1.0):
        with pytest.raises(ErreurChaine, match="facteur"):
            solveurChaine(_probleme(facteur=mauvais))


def test_angle_droit_signale():
    codes = {c["code"] for c in controlerProbleme(_probleme(angle=90.0))}
    assert "coefficientNul" in codes
    assert "coefficientLibre" in {c["code"] for c in controlerProbleme(_probleme(facteur=2.0))}
    assert not {"coefficientNul", "coefficientLibre"} & {c["code"] for c in controlerProbleme(_probleme())}


def test_dossier_de_validation_concorde():
    p = _probleme(facteur=2.0, angle=30.0)
    d = dossierValidation(p, calculerChaine(p, n=20000))
    assert d["nOk"] == d["nTotal"], [c for c in d["controles"] if c["statut"] != "OK"]
    assert "Facteur" in d["html"]


def test_enregistrement_aller_retour():
    p = _probleme(facteur=2.0, angle=30.0)
    assert importerProbleme(exporterProbleme(p))["maillons"][0]["facteur"] == 2.0
