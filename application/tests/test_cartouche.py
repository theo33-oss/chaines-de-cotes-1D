"""Cartouche des dossiers : lecture tolérante, fichier .json, dossiers HTML, PDF et Word."""

import io
import json

import pytest
from docx import Document
from pypdf import PdfReader

from chainecotes.core.errors import ErreurChaine
from chainecotes.services.calcul import calculerChaine
from chainecotes.services.cartouche import lignesCartouche, revisions
from chainecotes.services.dossier_word import dossierWord
from chainecotes.services.exemples import chargerExemple
from chainecotes.services.projet_io import exporterProbleme, importerProbleme
from chainecotes.services.rapport_pdf import rapportPdf
from chainecotes.services.validation import dossierValidation

CARTOUCHE = {
    "projet": "Réducteur R12",
    "indice": "B",
    "statut": "En revue",
    "auteur": "T. Brun",
    "revisions": [
        {"indice": "A", "date": "2026-10-01", "auteur": "T. Brun", "objet": "Création"},
        {"indice": "B", "date": "2026-11-03", "auteur": "T. Brun", "objet": "IT de la bague resserré"},
        {},
    ],
}


@pytest.fixture
def probleme():
    return {**chargerExemple("ajustements_h7_h6_n7"), "cartouche": CARTOUCHE}


def test_lecture_tolerante():
    assert lignesCartouche({}) == []
    assert lignesCartouche({"cartouche": "n'importe quoi"}) == []
    assert revisions({"cartouche": {"revisions": [3, None]}}) == []
    assert lignesCartouche({"cartouche": CARTOUCHE})[:2] == [("Projet", "Réducteur R12"), ("Indice de révision", "B")]
    assert len(revisions({"cartouche": CARTOUCHE})) == 2  # la ligne vide est écartée


def test_fichier_json_aller_retour(probleme):
    relu = importerProbleme(exporterProbleme(probleme))
    assert relu["cartouche"]["projet"] == "Réducteur R12"
    assert len(relu["cartouche"]["revisions"]) == 3


@pytest.mark.parametrize(
    "mauvais",
    [
        {"statut": "Presque fini"},
        {"projet": 12},
        {"inconnu": "x"},
        {"revisions": "A"},
        {"revisions": [{"indice": "A", "dessin": "x"}]},
        {"revisions": [{}] * 51},
    ],
)
def test_fichier_refuse_cartouche_invalide(probleme, mauvais):
    d = json.loads(exporterProbleme(probleme))
    d["probleme"]["cartouche"] = mauvais
    with pytest.raises(ErreurChaine):
        importerProbleme(json.dumps(d))


def test_dossier_html(probleme):
    html = dossierValidation(probleme)["html"]
    assert "Réducteur R12" in html and "IT de la bague resserré" in html
    assert 'class="cartouche"' not in dossierValidation({k: v for k, v in probleme.items() if k != "cartouche"})["html"]


def test_dossier_pdf_et_word(probleme):
    bundle = calculerChaine(probleme, n=20000)
    pdf = "".join(p.extract_text() for p in PdfReader(io.BytesIO(rapportPdf(probleme, bundle, "2026-11-03"))).pages)
    assert "Réducteur R12" in pdf and "IT de la bague resserré" in pdf
    word = Document(io.BytesIO(dossierWord(probleme, bundle, "2026-11-03")))
    texte = " ".join(c.text for t in word.tables for r in t.rows for c in r.cells)
    assert "Réducteur R12" in texte and "IT de la bague resserré" in texte
