"""Fichiers : aller-retour JSON des problèmes, refus des fichiers invalides, exports xlsx et csv."""

import copy
import io
import json

import pandas as pd
import pytest

from chainecotes.core.errors import ErreurChaine
from chainecotes.services.calcul import calculerChaine
from chainecotes.services.exemples import chargerExemple, listeExemples
from chainecotes.services.projet_io import (
    exporterProbleme,
    exporterResultatsCsv,
    exporterResultatsXlsx,
    importerProbleme,
)

IDS = [e["id"] for e in listeExemples()]


@pytest.mark.parametrize("ident", IDS)
def test_aller_retour_exact(ident):
    p = chargerExemple(ident)
    texte = exporterProbleme(p)
    d = json.loads(texte)
    assert d["application"] == "chaines-de-cotes-1d" and d["version"] == 1
    assert importerProbleme(texte) == p


def test_nan_exporte_en_null():
    p = chargerExemple("ajustements_h7_h6_n7")
    p["maillons"][0]["es"] = float("nan")
    assert importerProbleme(exporterProbleme(p))["maillons"][0]["es"] is None


def _enveloppe(**modif):
    d = {"application": "chaines-de-cotes-1d", "version": 1, "probleme": chargerExemple("tableau_depart")}
    d.update(modif)
    return d


def _avec(chemin, valeur):
    """Enveloppe valide dont le champ « chemin » (liste de clés) vaut valeur (supprimé si valeur est _SUPPR)."""
    d = _enveloppe()
    cible = d["probleme"]
    for cle in chemin[:-1]:
        cible = cible[cle]
    if valeur is _SUPPR:
        del cible[chemin[-1]]
    else:
        cible[chemin[-1]] = valeur
    return d


_SUPPR = object()

CAS_INVALIDES = {
    "json_illisible": "{pas du json",
    "pas_un_dict": json.dumps([1, 2]),
    "autre_application": json.dumps(_enveloppe(application="MecaStruct RdM Pro")),
    "version_future": json.dumps(_enveloppe(version=2)),
    "version_texte": json.dumps(_enveloppe(version="1")),
    "cle_inconnue_enveloppe": json.dumps(_enveloppe(extra=1)),
    "cle_inconnue_probleme": json.dumps(_avec(["id"], "x")),
    "probleme_absent": json.dumps({"application": "chaines-de-cotes-1d", "version": 1}),
    "condition_absente": json.dumps(_avec(["condition"], _SUPPR)),
    "reglages_absents": json.dumps(_avec(["reglages"], _SUPPR)),
    "maillons_absents": json.dumps(_avec(["maillons"], _SUPPR)),
    "condition_liste": json.dumps(_avec(["condition"], [1])),
    "reglages_texte": json.dumps(_avec(["reglages"], "x")),
    "maillons_dict": json.dumps(_avec(["maillons"], {"a": 1})),
    "maillon_pas_dict": json.dumps(_avec(["maillons", 0], 3)),
    "trop_de_maillons": json.dumps(_avec(["maillons"], [chargerExemple("tableau_depart")["maillons"][0]] * 201)),
    "nan": json.dumps(_avec(["maillons", 0, "cote"], float("nan"))),
    "infini": json.dumps(_avec(["condition", "jmin"], float("inf"))),
    "cote_texte": json.dumps(_avec(["maillons", 0, "cote"], "100")),
    "cote_booleen": json.dumps(_avec(["maillons", 0, "cote"], True)),
    "cote_absente": json.dumps(_avec(["maillons", 0, "cote"], _SUPPR)),
    "cote_vide": json.dumps(_avec(["maillons", 0, "cote"], None)),
    "sens": json.dumps(_avec(["maillons", 0, "sens"], "x")),
    "loi": json.dumps(_avec(["maillons", 0, "loi"], "gaussienne")),
    "modeT": json.dumps(_avec(["reglages", "modeT"], "variable")),
    "kSigma_texte": json.dumps(_avec(["reglages", "kSigma"], "3")),
    "texte_long": json.dumps(_avec(["maillons", 0, "nom"], "x" * 201)),
    "nom_condition_nombre": json.dumps(_avec(["condition", "nom"], 3)),
    "cle_inconnue_maillon": json.dumps(_avec(["maillons", 0, "couleur"], "rouge")),
}


@pytest.mark.parametrize("cas", CAS_INVALIDES)
def test_import_refuse(cas):
    with pytest.raises(ErreurChaine) as e:
        importerProbleme(CAS_INVALIDES[cas])
    assert e.value.message.startswith("Fichier non reconnu : ")


def test_import_accepte_vides_et_200_maillons():
    d = _enveloppe()
    d["probleme"]["condition"]["jmin"] = None
    d["probleme"]["reglages"]["tservice"] = None
    d["probleme"]["maillons"] = [copy.deepcopy(d["probleme"]["maillons"][0]) for _ in range(200)]
    d["probleme"]["maillons"][0].update(nom=None, iso=None, es=None, materiau=None, alpha=None, tservice=None)
    d["probleme"]["maillons"][1]["nom"] = "x" * 200
    assert importerProbleme(json.dumps(d)) == d["probleme"]


@pytest.fixture(scope="module")
def bundles():
    return {i: calculerChaine(chargerExemple(i), n=5000) for i in ("ajustements_h7_h6_n7", "thermique_alu_acier")}


def test_xlsx_relu(bundles):
    b = bundles["ajustements_h7_h6_n7"]
    feuilles = pd.read_excel(io.BytesIO(exporterResultatsXlsx(b)), sheet_name=None)
    assert list(feuilles) == ["Synthèse", "Maillons", "Contributions", "Monte-Carlo"]
    m = feuilles["Maillons"]
    assert list(m["Maillon"]) == b["res"]["Nom"]
    assert m["Cote moyenne (mm)"].tolist() == pytest.approx(list(b["res"]["C_moy"]))
    assert m["Intervalle de tolérance IT (mm)"].tolist() == pytest.approx(list(b["res"]["IT"]))
    s = feuilles["Synthèse"].set_index("Grandeur")["Valeur"]
    assert float(s["Jeu moyen"]) == pytest.approx(b["res"]["CF_moy"])
    assert float(s["Cpk"]) == pytest.approx(b["verdicts"]["cpk"])
    assert s["Verdict au pire des cas"] == "non conforme"
    c = feuilles["Contributions"]
    assert c["Part de la variance (%)"].sum() == pytest.approx(100)
    mc = feuilles["Monte-Carlo"].set_index("Grandeur")["Valeur"]
    assert int(mc["Nombre de tirages"]) == 5000
    assert float(mc["Hors tolérance simulé"]) == pytest.approx(b["mc"]["ppm"])


def test_xlsx_sans_monte_carlo(bundles):
    b = bundles["thermique_alu_acier"]
    assert b["mc"] is None
    feuilles = pd.read_excel(io.BytesIO(exporterResultatsXlsx(b)), sheet_name=None)
    assert "non calculé" in str(feuilles["Monte-Carlo"]["Valeur"][0])


def test_xlsx_neutralise_formule():
    p = chargerExemple("ajustements_h7_h6_n7")
    p["maillons"][0]["nom"] = "=1+1"
    b = calculerChaine(p, monteCarlo=False)
    m = pd.read_excel(io.BytesIO(exporterResultatsXlsx(b)), sheet_name="Maillons")
    assert m["Maillon"][0] == "'=1+1"


def test_csv_relu(bundles):
    b = bundles["ajustements_h7_h6_n7"]
    brut = exporterResultatsCsv(b)
    assert brut.startswith(b"\xef\xbb\xbf")
    texte = brut.decode("utf-8-sig")
    maillons, synthese = texte.split("\r\n\r\n")
    m = pd.read_csv(io.StringIO(maillons), sep=";", decimal=",")
    assert list(m["Maillon"]) == b["res"]["Nom"]
    assert m["Cote moyenne (mm)"].tolist() == pytest.approx(list(b["res"]["C_moy"]))
    s = pd.read_csv(io.StringIO(synthese), sep=";").set_index("Grandeur")["Valeur"]
    assert float(s["Jeu moyen"].replace(",", ".")) == pytest.approx(b["res"]["CF_moy"])
    assert "Limite basse Jmin" in s.index


def test_import_refuse_une_chaine_sans_maillon():
    import pytest

    from chainecotes.core.errors import ErreurChaine
    from chainecotes.services.exemples import chargerExemple
    from chainecotes.services.projet_io import exporterProbleme, importerProbleme

    p = chargerExemple("tableau_depart")
    p["maillons"] = []
    with pytest.raises(ErreurChaine, match="aucun maillon"):
        importerProbleme(exporterProbleme(p))
