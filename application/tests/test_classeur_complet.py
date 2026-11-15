"""Classeur Excel complet : formules vivantes et valeurs du calcul dans un seul fichier."""

import io

import pytest
from openpyxl import load_workbook

from chainecotes.core.nombres import ppmLisible
from chainecotes.services.calcul import calculerChaine
from chainecotes.services.classeur_complet import exporterClasseurComplet
from chainecotes.services.exemples import chargerExemple, listeExemples

IDS = [e["id"] for e in listeExemples()]


@pytest.mark.parametrize("ident", IDS)
def test_feuilles_et_formules(ident):
    p = chargerExemple(ident)
    classeur = load_workbook(io.BytesIO(exporterClasseurComplet(p, calculerChaine(p, n=5000))))
    assert classeur.sheetnames[0] == "Chaîne" and classeur.sheetnames[-1] == "Mode d'emploi"
    assert {"Synthèse", "Maillons", "Contributions"} <= set(classeur.sheetnames)
    formules = [c for ligne in classeur["Chaîne"].iter_rows() for c in ligne if isinstance(c.value, str) and c.value.startswith("=")]
    assert len(formules) > 50
    synthese = {ligne[0].value: ligne[1].value for ligne in classeur["Synthèse"].iter_rows(min_row=2)}
    assert isinstance(synthese["Jeu nominal"], int | float)


def test_un_nom_qui_commence_par_egal_reste_du_texte():
    p = chargerExemple(IDS[0])
    p["maillons"][0]["nom"] = "=1+1"
    classeur = load_workbook(io.BytesIO(exporterClasseurComplet(p, calculerChaine(p, n=5000))))
    for feuille in classeur.worksheets:
        if feuille.title == "Chaîne":
            continue  # ses formules sont voulues
        assert not any(isinstance(c.value, str) and c.value.startswith("=") for ligne in feuille.iter_rows() for c in ligne), feuille.title


def test_ppm_lisible():
    assert ppmLisible(2.887e-07) == "< 0,001 ppm"
    assert ppmLisible(0.0) == "< 0,001 ppm"
    assert ppmLisible(12.3456) == "12,35 ppm"
    assert ppmLisible(1234.5, unite=False) == "1234"
    assert ppmLisible(None) == "—" and ppmLisible(float("nan")) == "—" and ppmLisible(float("nan"), unite=False) == "—"
