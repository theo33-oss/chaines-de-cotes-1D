"""Tests du mécanisme (plusieurs chaînes) : aller-retour JSON, validation, calcul avec erreur isolée."""

import copy
import json

import numpy as np
import pytest

from chainecotes.core.errors import ErreurChaine
from chainecotes.services.calcul import calculerChaine
from chainecotes.services.exemples import chargerExemple
from chainecotes.services.mecanisme import calculerMecanisme, exporterMecanisme, importerMecanisme
from chainecotes.services.projet_io import exporterProbleme

N = 3000


def _trois():
    return [chargerExemple(i) for i in ("tableau_depart", "validation_100_40_59", "thermique_alu_acier")]


def test_aller_retour_json():
    m = {"nom": "Réducteur", "chaines": _trois()}
    r = importerMecanisme(exporterMecanisme(m))
    assert r["nom"] == "Réducteur"
    assert json.loads(exporterMecanisme(r)) == json.loads(exporterMecanisme(m))
    assert json.loads(exporterMecanisme(m))["format"] == "mecanisme"


def test_probleme_simple_promu():
    p = chargerExemple("tableau_depart")
    r = importerMecanisme(exporterProbleme(p))
    assert len(r["chaines"]) == 1 and r["chaines"][0] == p


def test_chaine_invalide_numero():
    ch = _trois()
    ch[1]["maillons"][0]["sens"] = "x"
    with pytest.raises(ErreurChaine, match="chaîne 2"):
        exporterMecanisme({"nom": "M", "chaines": ch})
    texte = exporterMecanisme({"nom": "M", "chaines": _trois()})
    d = json.loads(texte)
    d["chaines"][2]["maillons"][0]["loi"] = "bizarre"
    with pytest.raises(ErreurChaine, match="chaîne 3"):
        importerMecanisme(json.dumps(d))


@pytest.mark.parametrize(
    "texte", ["pas du json", "[]", '{"format": "autre"}', '{"format": "mecanisme", "version": 1, "chaines": []}',
              '{"format": "mecanisme", "version": 9, "chaines": [{}]}'],
)  # fmt: skip
def test_fichiers_refuses(texte):
    with pytest.raises(ErreurChaine):
        importerMecanisme(texte)


def test_calcul_trois_chaines_conforme_au_bundle():
    r = calculerMecanisme({"nom": "M", "chaines": _trois()}, N, 1)
    assert len(r["lignes"]) == 3 and r["global"]["ok"]
    for ligne, p in zip(r["lignes"], _trois(), strict=True):
        b = calculerChaine(p, True, N, 1)
        assert ligne["jeuMini"] == pytest.approx(b["verdicts"]["pireCas"]["min"])
        assert ligne["jeuMaxi"] == pytest.approx(b["verdicts"]["pireCas"]["max"])
        assert ligne["ppmMonteCarlo"] == (b["mc"]["ppm"] if b["mc"] else None)
        cont = b["contributions"]
        assert ligne["dominant"] == cont[int(np.argmax([c["partVariance"] for c in cont]))]["nom"]
    avec = [x for x in r["lignes"] if x["cpk"] is not None]  # Cpk indéfini si σ = 0 : ignoré
    pire = min(avec, key=lambda x: x["cpk"])
    assert r["global"]["pireCpk"] == pire["cpk"] and r["global"]["chainePireCpk"] == pire["nom"]


def test_erreur_isolee_et_hors_tolerance():
    ch = _trois()
    cassee = copy.deepcopy(ch[0])
    cassee["maillons"][0]["iso"] = "ZZ99"
    serree = copy.deepcopy(ch[1])
    serree["condition"]["jmin"], serree["condition"]["jmax"] = 50.0, 51.0
    r = calculerMecanisme({"nom": "M", "chaines": [cassee, serree, ch[2]]}, N, 1)
    assert r["lignes"][0]["erreur"] and r["lignes"][0]["verdict"] == "erreur de calcul"
    assert r["lignes"][1]["verdict"] == "non conforme"
    assert r["lignes"][2]["erreur"] is None and r["lignes"][2]["jeuMini"] is not None
    g = r["global"]
    assert g["enErreur"] == [r["lignes"][0]["nom"]] and g["horsTolerance"] == [r["lignes"][1]["nom"]]
    assert not g["ok"]


def test_tirages_reduits_quand_le_mecanisme_a_beaucoup_de_chaines():
    from chainecotes.services import mecanisme as meca

    p = chargerExemple("tableau_depart")
    m = {"nom": "M", "chaines": [copy.deepcopy(p) for _ in range(10)]}
    assert meca.calculerMecanisme(m, 1_000_000, 1)["nTirages"] == meca.TIRAGES_TOTAUX_MAX // 10
    assert meca.calculerMecanisme(m, 1_000, 1)["nTirages"] == 1_000  # rien n'est augmenté
    m["chaines"] = [copy.deepcopy(p) for _ in range(50)]
    assert meca.calculerMecanisme(m, 1_000_000, 1)["nTirages"] == meca.TIRAGES_TOTAUX_MAX // 50


def _meca():
    from chainecotes.services.exemples import chargerExemple

    return {"nom": "Boîte", "chaines": [chargerExemple("tableau_depart"), chargerExemple("reducteur_jeu_axial")]}


def test_seuil_de_cpk_decide_du_verdict_global():
    from chainecotes.services.mecanisme import calculerMecanisme, verdictGlobal

    haut = calculerMecanisme(_meca(), 20_000, 1, seuilCpk=50.0)
    assert haut["global"]["sousSeuil"] and not haut["global"]["okSeuil"]
    assert verdictGlobal(haut)[0] in ("erreur", "avertissement")
    bas = calculerMecanisme(_meca(), 20_000, 1, seuilCpk=0.0)
    assert not bas["global"]["sousSeuil"] and bas["global"]["okSeuil"] == bas["global"]["ok"]
    assert calculerMecanisme(_meca(), 20_000, 1)["global"]["seuilCpk"] is None


def test_exports_du_tableau_de_bord(tmp_path):
    import io
    from datetime import date

    from openpyxl import load_workbook

    from chainecotes.services.mecanisme import calculerMecanisme, exporterRapportPdf, exporterTableauDeBord

    res = calculerMecanisme(_meca(), 20_000, 1, seuilCpk=1.33)
    classeur = load_workbook(io.BytesIO(exporterTableauDeBord(res)))
    assert classeur.sheetnames == ["Tableau de bord", "Synthèse"]
    feuille = classeur["Tableau de bord"]
    noms = [feuille.cell(r, 1).value for r in range(2, feuille.max_row + 1)]
    assert noms == [x["nom"] for x in res["lignes"]]
    assert "Cpk ≥ seuil" in [c.value for c in feuille[1]]
    pdf = exporterRapportPdf(res, date(2026, 11, 10))
    assert pdf.startswith(b"%PDF") and len(pdf) > 2000
