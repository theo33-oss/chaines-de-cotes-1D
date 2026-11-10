"""Import des maillons depuis un csv, un classeur Excel ou un texte collé."""

import io

import pytest
from openpyxl import Workbook

from chainecotes.core.chaine import solveurChaine
from chainecotes.core.errors import ErreurChaine
from chainecotes.services.exemples import chargerExemple
from chainecotes.services.feuille_chaine import exporterFeuilleChaine
from chainecotes.services.import_maillons import MODELE_CSV, lireMaillons

COLLE = (
    "Maillon\tSens\tCote nominale (mm)\tISO 286\tES (mm)\tEI (mm)\tLoi\n"
    "Alésage\t+\t40\tH7\t\t\tnormale\n"
    "Cale\t-\t1,5\t\t0,02\t-0,02\tuniforme\n"
    "Arbre\t−\t38,5\t\t0\t−0,1\t\n"
)


def test_texte_colle_depuis_excel():
    r = lireMaillons(COLLE)
    assert r["erreurs"] == []
    a, c, b = r["maillons"]
    assert (a["nom"], a["sens"], a["cote"], a["iso"], a["es"]) == ("Alésage", "+", 40.0, "H7", None)
    assert (c["sens"], c["cote"], c["es"], c["ei"], c["loi"]) == ("-", 1.5, 0.02, -0.02, "uniforme")
    assert (b["sens"], b["ei"], b["loi"]) == ("-", -0.1, "normale")  # signe moins typographique, loi vide


def test_modele_csv_calcule():
    r = lireMaillons(MODELE_CSV)
    assert r["erreurs"] == [] and len(r["maillons"]) == 3 and r["maillons"][2]["materiau"] == "Acier C45"
    res = solveurChaine({"condition": {"jmin": 0, "jmax": 1}, "reglages": {}, "maillons": r["maillons"]})
    assert res["CF_nom"] == pytest.approx(40 - 1.5 - 38.5)


def test_csv_windows_et_virgule_decimale():
    texte = "Nom;Sens;Cote;ES;EI\r\nA;+;12,5;0,1;-0,1\r\nB;-;12,4;0,05;-0,05\r\n"
    r = lireMaillons(texte.encode("cp1252"))
    assert r["erreurs"] == [] and r["maillons"][0]["cote"] == 12.5


def test_tolerance_symetrique_et_cote_signee():
    r = lireMaillons("Maillon;Cote;± tolérance\nA;10;0,2\nB;-4;0,1\n")
    assert [(m["sens"], m["cote"], m["es"], m["ei"]) for m in r["maillons"]] == [
        ("+", 10.0, 0.2, -0.2),
        ("-", 4.0, 0.1, -0.1),
    ]
    assert lireMaillons("Maillon;Cote;IT\nA;10;0,2\n")["maillons"][0]["es"] == pytest.approx(0.1)


def test_feuille_exportee_se_relit():
    p = chargerExemple("reducteur_jeu_axial")
    relus = lireMaillons(exporterFeuilleChaine(p))
    assert relus["erreurs"] == [] and len(relus["maillons"]) == len(p["maillons"])
    res = solveurChaine(p)
    neuf = solveurChaine({**p, "maillons": relus["maillons"]})
    assert neuf["CF_min"] == pytest.approx(res["CF_min"]) and neuf["CF_max"] == pytest.approx(res["CF_max"])


def test_classeur_avec_titre_au_dessus():
    wb = Workbook()
    ws = wb.active
    ws.append(["Étude du jeu axial"])
    ws.append([])
    ws.append(["Désignation", "Sens", "Dimension", "Écart sup", "Écart inf"])
    ws.append(["A", "plus", 10, 0.1, -0.1])
    ws.append(["B", "moins", 9.5, 0.05, -0.05])
    ws.append([])
    ws.append(["Total", None, "ne pas lire"])
    tampon = io.BytesIO()
    wb.save(tampon)
    r = lireMaillons(tampon.getvalue())
    assert r["erreurs"] == [] and [m["nom"] for m in r["maillons"]] == ["A", "B"]


def test_erreurs_par_ligne():
    r = lireMaillons("Maillon;Sens;Cote;ES;EI;Loi;Matériau\nA;x;abc;0;0;;\nB;+;5;0;;gamma;Cuivre magique\nC;+;5;;;;\n")
    texte = " ".join(r["erreurs"])
    for attendu in ("Ligne 2", "sens", "abc", "Ligne 3", "loi", "matériau", "Ligne 4"):
        assert attendu in texte


@pytest.mark.parametrize("mauvais", ["", "Nom;Poids\nA;1\n", "Cote\n", b"PK\x03\x04pas un classeur", b"x" * 2_000_001])
def test_contenu_refuse(mauvais):
    with pytest.raises(ErreurChaine):
        lireMaillons(mauvais)


def test_limite_de_maillons():
    lignes = "Cote;ES;EI\n" + "5;0,1;-0,1\n" * 201
    with pytest.raises(ErreurChaine, match="Trop de maillons"):
        lireMaillons(lignes)
