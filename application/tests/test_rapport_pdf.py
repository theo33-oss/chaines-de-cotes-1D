"""Dossier PDF : en-tête valide, valeurs clés extraites du texte, caractères spéciaux, saut de page."""

import io
from datetime import date

import pytest
from pypdf import PdfReader

from chainecotes.services.calcul import calculerChaine
from chainecotes.services.exemples import chargerExemple
from chainecotes.services.rapport_pdf import rapportPdf


def _pdf(probleme, d=date(2026, 11, 3)):
    b = calculerChaine(probleme)
    data = rapportPdf(probleme, b, d)
    r = PdfReader(io.BytesIO(data))
    return data, r, "\n".join(p.extract_text() for p in r.pages), b


def test_exemple_valeurs_cles():
    data, r, txt, b = _pdf(chargerExemple("ajustements_h7_h6_n7"))
    assert data.startswith(b"%PDF")
    assert 3 <= len(r.pages) <= 8
    assert "03/11/2026" in txt and "Dossier de calcul" in txt
    v, res = b["verdicts"], b["res"]
    assert f"{v['cpk']:.3f}".replace(".", ",") in txt  # Cpk ≈ 0,610
    assert f"{res['CF_min']:.4f}".replace(".", ",") in txt  # 1,0080
    assert "Alésage" in txt and "Monte-Carlo" in txt and "contrôles de calcul concordent" in txt
    assert "Non conforme" in txt  # pire cas hors limites 1,03 à 1,06


def test_caracteres_speciaux():
    p = chargerExemple("ajustements_h7_h6_n7")
    p["condition"]["nom"] = "Jeu σ ≤ Δ – « test » ±"
    _, _, txt, _ = _pdf(p, "3 novembre 2026")
    assert "σ" in txt and "Δ" in txt and "3 novembre 2026" in txt


def test_chaine_minimale_deux_maillons():  # le solveur exige au moins deux maillons
    p = {
        "condition": {"nom": "J", "jmin": None, "jmax": None},
        "reglages": {"kSigma": 3, "tref": 20.0, "modeT": "uniforme", "tservice": 20.0},
        "maillons": [
            {"nom": "Seul", "sens": "+", "cote": 10.0, "iso": None, "es": 0.1, "ei": -0.1, "loi": "normale"},
            {"nom": "Autre", "sens": "-", "cote": 9.0, "iso": None, "es": 0.1, "ei": -0.1, "loi": "normale"},
        ],
    }
    data, _, txt, _ = _pdf(p)
    assert data.startswith(b"%PDF") and "Seul" in txt


def test_trente_maillons_saut_de_page():
    p = chargerExemple("ajustements_h7_h6_n7")
    base = p["maillons"][0]
    p["maillons"] = [
        dict(base, nom=f"Maillon{i:02d}", sens="+" if i % 2 else "-", cote=10.0 + i, iso=None, es=0.05, ei=-0.05)
        for i in range(30)
    ]
    p["condition"].update(jmin=None, jmax=None)
    _, r, txt, _ = _pdf(p)
    assert "Maillon00" in txt and "Maillon29" in txt
    assert len(r.pages) > len(_pdf(chargerExemple("ajustements_h7_h6_n7"))[1].pages)


def test_bundle_invalide():
    with pytest.raises(KeyError):
        rapportPdf(chargerExemple("ajustements_h7_h6_n7"), {}, date(2026, 1, 1))


def test_dossier_word_valide_et_contient_le_bilan():
    import io

    from docx import Document

    from chainecotes.services.calcul import calculerChaine
    from chainecotes.services.dossier_word import dossierWord
    from chainecotes.services.exemples import chargerExemple

    p = chargerExemple("tableau_depart")
    data = dossierWord(p, calculerChaine(p), "03/11/2026")
    assert data[:2] == b"PK"
    texte = "\n".join(par.text for par in Document(io.BytesIO(data)).paragraphs)
    assert "Dossier de validation" in texte and "03/11/2026" in texte
    assert "contrôles de calcul concordent" in texte
