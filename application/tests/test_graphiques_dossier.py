"""Graphiques des dossiers de validation : liste, images PNG, annexes HTML, PDF et Word."""

import io

import pytest
from docx import Document
from pypdf import PdfReader

from chainecotes.services.calcul import calculerChaine
from chainecotes.services.dossier_word import dossierWord
from chainecotes.services.exemples import chargerExemple
from chainecotes.services.graphiques_dossier import graphiquesDossier
from chainecotes.services.rapport_pdf import rapportPdf
from chainecotes.services.validation import dossierValidation


def _bundle(exemple="reducteur_jeu_axial", **modif):
    p = chargerExemple(exemple)
    for i, d in modif.get("derive", {}).items():
        p["maillons"][i]["derive"] = d
    return p, calculerChaine(p, n=20_000)


def test_tous_les_graphiques_sont_listes_avec_leur_legende():
    _, b = _bundle()
    g = graphiquesDossier(b, avecImages=False)
    titres = [x["titre"] for x in g]
    assert titres[0] == "Schéma de la chaîne" and "Histogramme Monte-Carlo" in titres
    assert "Sensibilité (indices de Sobol)" in titres and "Effet thermique" not in titres
    assert all(x["legende"] and x["fig"] is not None and x["png"] is None for x in g)


def test_graphiques_thermique_et_derive_ajoutes_quand_ils_existent():
    _, b = _bundle("boite_vitesses_chaude", derive={0: 5.0})
    titres = [x["titre"] for x in graphiquesDossier(b, avecImages=False)]
    assert "Effet thermique" in titres and "Dérive et re-réglage" in titres


def test_annexe_html_sans_image_garde_les_graphiques_interactifs():
    p, b = _bundle()
    g = graphiquesDossier(b, avecImages=False)
    html = dossierValidation(p, b, g)["html"]
    assert "8. Annexe : graphiques du calcul" in html
    assert html.count("<figure>") == len(g) and "plotly-graph-div" in html
    assert "Annexe" not in dossierValidation(p, b)["html"]  # sans graphiques : pas d'annexe


def test_images_png_dans_html_pdf_et_word():
    p, b = _bundle()
    g = graphiquesDossier(b)
    if not all(x["png"] for x in g):
        pytest.skip("export d'images indisponible (kaleido ou navigateur absent)")
    assert all(x["png"][:4] == b"\x89PNG" for x in g)
    html = dossierValidation(p, b, g)["html"]
    assert html.count("data:image/png;base64,") == len(g) and "plotly-graph-div" not in html
    pdf = PdfReader(io.BytesIO(rapportPdf(p, b, "03/11/2026", g)))
    assert sum(len(page.images) for page in pdf.pages) == len(g)
    word = Document(io.BytesIO(dossierWord(p, b, "03/11/2026", g)))
    assert len(word.inline_shapes) == len(g)


def test_pdf_et_word_sans_image_le_signalent_sans_planter():
    p, b = _bundle()
    g = graphiquesDossier(b, avecImages=False)
    pdf = PdfReader(io.BytesIO(rapportPdf(p, b, "03/11/2026", g)))
    assert "navigateur absent" in " ".join(page.extract_text() for page in pdf.pages)
    texte = "\n".join(par.text for par in Document(io.BytesIO(dossierWord(p, b, "03/11/2026", g))).paragraphs)
    assert "navigateur absent" in texte and "Annexe : graphiques du calcul" in texte
