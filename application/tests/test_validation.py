"""Dossier de validation : bilan honnête, contrôles indépendants, page HTML bien formée."""

from html.parser import HTMLParser

import pytest

from chainecotes.core.donnees import chargerJson
from chainecotes.services.calcul import calculerChaine
from chainecotes.services.exemples import chargerExemple
from chainecotes.services.validation import dossierValidation

IDS = [e["id"] for e in chargerJson("exemples.json")["exemples"]]  # exemples MATLAB : seuls à avoir un golden


@pytest.mark.parametrize("ident", IDS)
def test_exemples_sans_ecart(ident):
    d = dossierValidation(chargerExemple(ident))
    assert d["nTotal"] > 0
    assert d["nOk"] == d["nTotal"], [c for c in d["controles"] if c["statut"] != "OK"]
    assert d["bilan"] == f"{d['nTotal']} / {d['nTotal']} contrôles de calcul concordent"
    assert "ÉCART" not in d["html"]
    assert any(c["section"] == "matlab" for c in d["controles"])


def test_loi_uniforme_et_hors_bibliotheque():
    p = chargerExemple("ajustements_h7_h6_n7")
    p["maillons"][2]["loi"] = "uniforme"
    d = dossierValidation(p)
    assert d["nOk"] == d["nTotal"]
    assert not any(c["section"] == "matlab" for c in d["controles"])
    assert "informatif" in d["html"] and "identique à aucun exemple" in d["html"]


def test_bundle_fausse_donne_ecart():
    p = chargerExemple("ajustements_h7_h6_n7")
    b = calculerChaine(p, n=20000)
    b["res"] = dict(b["res"], CF_max=b["res"]["CF_max"] * 1.01)
    d = dossierValidation(p, b)
    assert d["nOk"] < d["nTotal"]
    assert "ÉCART" in d["html"]
    assert {c["nom"] for c in d["controles"] if c["statut"] == "ÉCART"} >= {"J max", "CF_max"}


def test_controle_impossible_compte_comme_ecart():
    p = chargerExemple("validation_100_40_59")
    b = calculerChaine(p, n=20000)
    b["res"] = {k: v for k, v in b["res"].items() if k != "CF_sigma"}
    d = dossierValidation(p, b)
    impossibles = [c for c in d["controles"] if "impossible" in c["nom"]]
    assert impossibles and all(c["statut"] == "ÉCART" for c in impossibles)
    assert d["nOk"] < d["nTotal"] and "ÉCART" in d["html"]


def test_nan_inattendu_est_un_ecart():
    p = chargerExemple("validation_100_40_59")
    b = calculerChaine(p, monteCarlo=False)
    b["verdicts"] = dict(b["verdicts"], cpk=float("nan"))
    d = dossierValidation(p, b)
    assert [c["nom"] for c in d["controles"] if c["statut"] == "ÉCART"] == ["Cpk", "cpk"]


class _Balises(HTMLParser):
    VIDES = {"meta", "br", "img", "hr", "input", "link"}

    def __init__(self):
        super().__init__()
        self.pile, self.erreurs, self.vues, self.titre = [], [], set(), ""

    def handle_starttag(self, tag, attrs):
        self.vues.add(tag)
        if tag not in self.VIDES:
            self.pile.append(tag)

    def handle_endtag(self, tag):
        if not self.pile or self.pile.pop() != tag:
            self.erreurs.append(tag)

    def handle_data(self, data):
        if self.pile and self.pile[-1] == "title":
            self.titre += data


def test_html_bien_forme():
    d = dossierValidation(chargerExemple("tableau_depart"))
    assert d["html"].lstrip().lower().startswith("<!doctype html>")
    b = _Balises()
    b.feed(d["html"])
    assert not b.erreurs and not b.pile
    assert {"html", "head", "title", "body", "main", "h1", "h2", "table"} <= b.vues
    assert b.titre.startswith("Dossier de validation")
    assert d["html"].count("<h2 ") == 7
