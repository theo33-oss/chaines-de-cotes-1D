"""Tableau de cotation : valeurs recalculées à la main, lecture du xlsx et du csv, caractères français."""

import io

import pytest
from openpyxl import load_workbook

from chainecotes.core import iso286
from chainecotes.core.errors import ErreurChaine
from chainecotes.services.calcul import calculerChaine
from chainecotes.services.cotation import NOTE_NORMES, exporterCotation, tableauCotation


def _probleme():
    return {
        "condition": {"nom": "Jeu J", "jmin": 0.5, "jmax": 2.0},
        "reglages": {"kSigma": 3},
        "maillons": [
            {"nom": "Alésage", "sens": "+", "cote": 100.0, "iso": "H7", "loi": "normale"},
            {"nom": "Arbre é", "sens": "-", "cote": 50.0, "es": 0.05, "ei": -0.05, "loi": "uniforme"},
            {"nom": "Cale", "sens": "-", "cote": 49.0, "es": 0.1, "ei": -0.02, "loi": "normale"},
        ],
    }


def test_lignes_valeurs_a_la_main():
    h7 = iso286.lireDesignation("H7", 100.0)
    L = tableauCotation(_probleme())
    assert [x["repere"] for x in L] == ["M1", "M2", "M3"]
    a, b, c = L
    assert a["designation"] == "H7" and a["es"] == pytest.approx(h7["es"]) and a["ei"] == 0
    assert a["cmax"] == pytest.approx(100 + h7["es"]) and a["cmin"] == pytest.approx(100.0)
    assert a["it"] == pytest.approx(0.035) and a["tolSym"] is None
    assert b["designation"] == "" and b["cmax"] == pytest.approx(50.05) and b["cmin"] == pytest.approx(49.95)
    assert b["it"] == pytest.approx(0.1) and b["tolSym"] == pytest.approx(0.05)
    assert "uniforme" in b["procede"] and "3 σ" in a["procede"]
    assert c["tolSym"] is None and c["it"] == pytest.approx(0.12) and "écarts saisis" in c["remarque"]
    assert "ISO 286" in a["remarque"]


def test_bundle_identique_au_calcul_direct():
    p = _probleme()
    assert tableauCotation(p, calculerChaine(p, monteCarlo=False)) == tableauCotation(p)


def test_xlsx_relu_avec_openpyxl():
    p = _probleme()
    wb = load_workbook(io.BytesIO(exporterCotation(p, calculerChaine(p, monteCarlo=False))))
    assert wb.sheetnames == ["Cotation", "Hypothèses"]
    ws = wb["Cotation"]
    entete = [c.value for c in ws[1]]
    assert entete[0] == "Repère" and "Désignation ISO 286" in entete and "Tolérance équivalente ± (mm)" in entete
    lignes = tableauCotation(p)
    assert ws["B2"].value == "Alésage" and ws["B3"].value == "Arbre é"
    assert ws["C2"].value == "H7" and ws["C3"].value in (None, "")
    assert ws["D2"].value == 100.0 and ws["E2"].value == pytest.approx(lignes[0]["es"])
    assert ws["G3"].value == pytest.approx(50.05) and ws["J3"].value == pytest.approx(0.05)
    assert ws["J2"].value is None
    assert ws["E2"].number_format != "General" and ws.column_dimensions["L"].width >= 40
    assert ws.freeze_panes == "A2"
    assert "ISO 129-1" in ws["A6"].value and "ISO 8015" in ws["A6"].value
    h = [(r[0].value, r[1].value) for r in wb["Hypothèses"].iter_rows(min_row=2)]
    textes = " ".join(t for _, t in h)
    assert "ISO 129-1" in textes and "ISO 8015" in textes and "ISO 1101" in textes
    assert any(r == "Jeu nominal Σ aᵢ·cᵢ" and t == "1 mm" for r, t in h)  # 100 − 50 − 49


def test_csv_francais_avec_bom():
    p = _probleme()
    brut = exporterCotation(p, None, "csv")
    assert brut.startswith(b"\xef\xbb\xbf")
    lignes = brut.decode("utf-8-sig").split("\r\n")
    assert lignes[0].split(";")[:3] == ["Repère", "Maillon", "Désignation ISO 286"]
    assert lignes[1].split(";")[:4] == ["M1", "Alésage", "H7", "100"] or lignes[1].startswith("M1;Alésage;H7;100")
    assert "0,05" in lignes[2] and "Arbre é" in lignes[2]
    assert lignes[-1] == NOTE_NORMES


def test_exemples_sans_designation_iso():
    p = _probleme()
    for m in p["maillons"]:
        m["iso"] = None
        m["es"], m["ei"] = m.get("es", 0.02), m.get("ei", -0.02)
    assert all(x["designation"] == "" for x in tableauCotation(p))
    ws = load_workbook(io.BytesIO(exporterCotation(p)))["Cotation"]
    assert ws["C2"].value in (None, "")


def test_formats_inconnus_et_probleme_invalide():
    with pytest.raises(ErreurChaine, match="Format d'export inconnu"):
        exporterCotation(_probleme(), None, "pdf")
    with pytest.raises(ErreurChaine):
        tableauCotation({"maillons": []})


def test_texte_commencant_par_signe_neutralise():
    p = _probleme()
    p["maillons"][0]["nom"] = "=SOMME(A1)"
    ws = load_workbook(io.BytesIO(exporterCotation(p)))["Cotation"]
    assert ws["B2"].value.startswith("'")


def test_csv_cotation_noms_piegeux_restent_une_seule_cellule_sans_formule():
    import csv
    import io

    from chainecotes.services.calcul import calculerChaine
    from chainecotes.services.cotation import exporterCotation
    from chainecotes.services.exemples import chargerExemple

    p = chargerExemple("tableau_depart")
    p["maillons"][0]["nom"] = "a;=1+1"
    p["maillons"][1]["nom"] = 'b"\nc'
    p["maillons"][2]["nom"] = "=HYPERLINK(1)"
    texte = exporterCotation(p, calculerChaine(p, n=2000), "csv").decode("utf-8-sig")
    lignes = list(csv.reader(io.StringIO(texte), delimiter=";"))
    entete, donnees = lignes[0], lignes[1:4]
    assert all(len(ligne) == len(entete) for ligne in donnees)  # aucune colonne en trop
    assert donnees[0][1] == "'a;=1+1" or donnees[0][1] == "a;=1+1"  # une seule cellule
    assert donnees[1][1] == 'b"\nc'
    assert donnees[2][1].startswith("'=")  # la formule est neutralisée
    assert not any(c.startswith(("=", "@")) for ligne in lignes for c in ligne)
