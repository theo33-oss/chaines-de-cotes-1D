"""Feuille Excel à formules vivantes : chaque formule, évaluée, redonne le résultat du site."""

import io

import pytest
from openpyxl import load_workbook

from chainecotes.services.calcul import calculerChaine
from chainecotes.services.exemples import chargerExemple, listeExemples
from chainecotes.services.feuille_chaine import exporterFeuilleChaine
from tests.mini_excel import Feuille

IDS = [e["id"] for e in listeExemples()]


def _feuille(probleme):
    bundle = calculerChaine(probleme, n=20000)
    classeur = load_workbook(io.BytesIO(exporterFeuilleChaine(probleme, bundle)))
    return classeur, Feuille(classeur["Chaîne"]), bundle


def _controles(ws, feuille):
    """Valeurs de la colonne Contrôle (G) et couples (libellé, formule, valeur du site) des lignes comparées."""
    return [
        (ws.cell(r, 2).value, feuille.valeur(f"G{r}"), ws.cell(r, 4).value)
        for r in range(1, ws.max_row + 1)
        if ws.cell(r, 7).value and str(ws.cell(r, 7).value).startswith("=IF(ABS")
    ]


@pytest.mark.parametrize("ident", IDS)
def test_formules_redonnent_le_site(ident):
    classeur, feuille, _ = _feuille(chargerExemple(ident))
    controles = _controles(classeur["Chaîne"], feuille)
    assert len(controles) >= 8
    assert [c[:2] for c in controles if c[1] != "OK"] == []


def test_cas_difficiles():
    """Coefficient libre, décentrage, limite absente, lois mixtes et dilatation par cote."""
    p = chargerExemple("boite_vitesses_chaude")
    p["reglages"]["decentrage"] = 1.5
    p["maillons"][0].update(facteur=1.5, angle=20.0)
    p["maillons"][1]["loi"] = "triangulaire"
    p["condition"]["jmax"] = None
    classeur, feuille, _ = _feuille(p)
    controles = _controles(classeur["Chaîne"], feuille)
    assert all(c[1] == "OK" for c in controles), controles


def test_modifier_une_saisie_recalcule():
    """La feuille est vivante : élargir un ES dans le classeur déplace le jeu maxi du pire des cas."""
    p = chargerExemple("tableau_depart")
    classeur, feuille, bundle = _feuille(p)
    ws = classeur["Chaîne"]
    ligne = next(r for r in range(1, ws.max_row) if ws.cell(r, 2).value == "Jeu maxi au pire des cas")
    avant = feuille.valeur(f"D{ligne}")
    premiere = next(r for r in range(1, ws.max_row) if ws.cell(r, 1).value == 1)
    ws.cell(premiere, 5).value += 0.5  # ES + 0,5 mm
    apres = Feuille(ws).valeur(f"D{ligne}")
    assert avant == pytest.approx(bundle["verdicts"]["pireCas"]["max"])
    assert apres == pytest.approx(avant + 0.5)  # premier maillon de sens « + » : le jeu maxi suit son ES


def test_noms_dangereux_neutralises():
    p = chargerExemple("tableau_depart")
    p["maillons"][0]["nom"] = "=1+1"
    ws = load_workbook(io.BytesIO(exporterFeuilleChaine(p)))["Chaîne"]
    assert any(c.value == "'=1+1" for ligne in ws.iter_rows() for c in ligne)


def _mesures():
    p = chargerExemple("boite_vitesses_chaude")
    p["reglages"]["decentrage"] = 1.0
    p["maillons"][0].update(sigma_reel=0.004)
    p["maillons"][1].update(moyenne_reelle=p["maillons"][1]["cote"] + 0.01)
    p["maillons"][2].update(sigma_reel=0.003, moyenne_reelle=p["maillons"][2]["cote"] - 0.005)
    return p


def test_mesures_d_atelier_dans_la_feuille():
    """σ mesuré et moyenne mesurée : la feuille redonne le site, le contrôle ne dit plus « ÉCART »."""
    classeur, feuille, bundle = _feuille(_mesures())
    assert bundle["res"]["decalage_reel"] != 0
    controles = _controles(classeur["Chaîne"], feuille)
    assert len(controles) >= 8 and all(c[1] == "OK" for c in controles), controles


def test_mesures_survivent_a_la_reimportation():
    from chainecotes.services import import_maillons

    p = _mesures()
    bundle = calculerChaine(p, n=1000)
    texte = exporterFeuilleChaine(p, bundle)
    lu = import_maillons.lireMaillons(texte)
    assert not lu["erreurs"]
    sigma = [m.get("sigma_reel") for m in lu["maillons"]]
    moy = [m.get("moyenne_reelle") for m in lu["maillons"]]
    assert sigma[0] == pytest.approx(0.004) and sigma[2] == pytest.approx(0.003) and sigma[1] in (None, "")
    assert moy[1] == pytest.approx(p["maillons"][1]["moyenne_reelle"])
