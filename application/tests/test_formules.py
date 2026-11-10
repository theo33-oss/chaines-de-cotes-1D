"""Formules en vrais caractères : conversion LaTeX vers HTML, aucune image ni script distant dans les formules."""

import html as html_lib
import re

import pytest

from chainecotes.core.formules import texVersHtml
from chainecotes.services.calcul import calculerChaine
from chainecotes.services.exemples import chargerExemple, listeExemples
from chainecotes.services.explications import explicationsCalcul
from chainecotes.services.validation import dossierValidation

BS = chr(92)  # barre oblique inverse, écrite sans chaîne brute pour éviter les pièges d'échappement


def _texte(fragment: str) -> str:
    """Texte visible d'un fragment : balises retirées, entités décodées."""
    return html_lib.unescape(re.sub(r"<[^>]+>", "", fragment))


@pytest.mark.parametrize(
    "tex, attendu",
    [
        (BS + "sum_{i=1}^{n} a_i", "∑i=1n ai"),
        (BS + "sigma_J = " + BS + "sqrt{" + BS + "sum " + BS + "sigma_i^2}", "σJ = √(∑σi2)"),
        (BS + "frac{" + BS + "Delta J}{2}", "(ΔJ) / (2)"),
        ("2k" + BS + ",x", "2k x"),
        (BS + "min" + BS + "left(a, b" + BS + "right) " + BS + "pm 2", "min(a, b) ± 2"),
        (BS + "text{ppm}_{simul}", "ppmsimul"),
        ("10^6 " + BS + "times 3", "106 × 3"),
        (BS + "bar C_1", "C̄1"),
    ],
)
def test_conversion_en_caracteres(tex, attendu):
    obtenu = re.sub(r"\s+", " ", _texte(texVersHtml(tex))).strip()
    assert obtenu == attendu, obtenu


def test_fraction_ecrite_sur_une_ligne():
    rendu = texVersHtml(BS + "frac{a}{b}")
    assert "(a)&thinsp;/&thinsp;(b)" in rendu
    assert "<table" not in rendu


def test_syntaxe_inattendue_ne_plante_pas():
    assert texVersHtml("{ouvert") is not None
    assert BS not in texVersHtml("a " + BS + "b c")


def test_explications_sans_latex_brut_ni_image():
    for ident in ("tableau_depart", "boitier_electronique", "reducteur_jeu_axial"):
        bundle = calculerChaine(chargerExemple(ident), monteCarlo=True, n=20_000)
        for section in explicationsCalcul(bundle):
            for formule in section["formules"]:
                texte = _texte(texVersHtml(formule))
                assert BS not in texte, (ident, formule)
                assert "<img" not in texVersHtml(formule) and "$" not in texte, (ident, formule)


def test_dossier_html_sans_mathjax_ni_script_distant():
    p = chargerExemple("tableau_depart")
    page = dossierValidation(p, calculerChaine(p, n=20_000))["html"]
    assert "cdnjs" not in page and "MathJax" not in page and "mjwarn" not in page
    assert "&thinsp;/&thinsp;" in page  # les fractions des formules sont écrites en ligne


def test_tous_les_exemples_ont_des_formules_lisibles():
    for e in listeExemples():
        bundle = calculerChaine(chargerExemple(e["id"]), monteCarlo=False)
        assert all(BS not in _texte(texVersHtml(f)) for s in explicationsCalcul(bundle) for f in s["formules"])
