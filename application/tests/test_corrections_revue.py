"""Non-régressions des constats de la revue indépendante (inverse, coût, saisie, graphiques, pages, PDF)."""

import io
import math
import time
from pathlib import Path

import numpy as np
import pypdf
import pytest

from chainecotes.core import cout
from chainecotes.core.chaine import ZERO_ABSOLU_C, coefficientSigma, solveurChaine
from chainecotes.core.derive import deriveSerie
from chainecotes.core.errors import ErreurChaine
from chainecotes.core.inverse import repartirTolerances
from chainecotes.core.montecarlo import simulerMonteCarlo
from chainecotes.plots import graphiques
from chainecotes.plots.schema import figureSchema
from chainecotes.services.calcul import apercuChaine, calculerChaine
from chainecotes.services.exemples import chargerExemple
from chainecotes.services.projet_io import exporterProbleme, importerProbleme
from chainecotes.services.rapport_pdf import rapportPdf
from chainecotes.services.validation import dossierValidation

RACINE = Path(__file__).resolve().parents[1]


def _p(loi="normale", n=3, jmax=1.0):
    ms = [
        {"nom": f"M{i}", "sens": "+" if i % 2 == 0 else "-", "cote": 10.0 + i, "es": 0.0, "ei": 0.0, "loi": loi}
        for i in range(n)
    ]
    j = sum(m["cote"] * (1 if m["sens"] == "+" else -1) for m in ms)
    return {"condition": {"nom": "J", "jmin": j, "jmax": j + jmax}, "reglages": {}, "maillons": ms}


@pytest.mark.parametrize("loi", ["normale", "uniforme", "triangulaire"])
@pytest.mark.parametrize("methode", ["egale", "proportionnelle", "cout_minimal"])
def test_statistique_tient_exactement_le_budget_pour_toutes_les_lois(loi, methode):
    r = repartirTolerances(_p(loi), methode, "statistique")
    v = r["verification"]
    assert 2 * v["k_sigma"] * v["CF_sigma"] == pytest.approx(r["budget"], rel=1e-9)


def test_gains_du_cout_minimal_jamais_negatifs_avec_bornes_de_procede():
    p = chargerExemple("ajustements_h7_h6_n7")
    p["condition"]["jmax"] = 1.2
    procedes = ["tournage", "rectification", "fraisage", "generique"]
    couts = [{"procede": procedes[i % 4]} for i in range(len(p["maillons"]))]
    for critere in ("pire_cas", "statistique"):
        c = repartirTolerances(p, "cout_minimal", critere, couts=couts)["cout"]
        assert c["gainEgale"] >= -1e-9 and c["gainProportionnelle"] >= -1e-9


def test_repartirBorne_respecte_les_bornes_et_la_contrainte():
    h, lo, hi = np.array([1.0, 1.0, 2.0]), np.array([0.01, 0.2, 0.01]), np.array([0.5, 0.5, 0.5])
    x = cout.repartirBorne(h, 1, np.ones(3), lo, hi, 0.9)
    assert np.all(x >= lo) and np.all(x <= hi)
    assert float(np.sum(h * x)) == pytest.approx(0.9, rel=1e-9)
    assert np.array_equal(cout.repartirBorne(h, 1, np.ones(3), lo, hi, 100.0), hi)


def test_allouerCout_cible_a_la_limite_numerique_retourne_lo():
    x = cout.allouerCout([1, 1], 1, [1, 1], [1, 1], [0.01, 0.01], [1, 1], 0.02 * (1 - 1e-13))
    assert np.allclose(x, 0.01)


def test_allouerCout_exposant_tres_grand():
    x = cout.allouerCout([1, 2], 1, [1, 1], [100, 100], [0.001, 0.001], [10, 10], 0.01)
    assert float(np.sum(np.array([1, 2]) * x)) == pytest.approx(0.01, rel=1e-6)


def test_decentrage_signale_dans_le_message_statistique():
    p = _p()
    p["reglages"]["decentrage"] = 2
    assert "décentrage" in repartirTolerances(p, "egale", "statistique")["message"]
    assert "décentrage" not in repartirTolerances(p, "egale", "pire_cas")["message"]


def test_validation_et_coeur_d_accord_sur_les_entrees_vides():
    p = chargerExemple("tableau_depart")
    p["reglages"] = {"tref": None}
    assert "0 / " not in dossierValidation(p, calculerChaine(p, n=1000))["bilan"]
    p2 = chargerExemple("tableau_depart")
    p2["maillons"][0]["loi"] = float("nan")
    assert solveurChaine(p2)["loi"][0] == "normale"
    p2["reglages"] = {"decentrage": ""}
    with pytest.raises(ErreurChaine):
        solveurChaine(p2)


def test_api_directe_gardes():
    with pytest.raises(ErreurChaine):
        coefficientSigma("normale", 0)
    assert coefficientSigma("triangulaire", 3) == pytest.approx(1 / (2 * math.sqrt(6)))
    res = solveurChaine(chargerExemple("tableau_depart"))
    with np.errstate(all="raise"):
        assert math.isnan(simulerMonteCarlo(res, n=0)["moyenne"])
    with pytest.raises(ErreurChaine):
        deriveSerie(chargerExemple("tableau_depart"), True, 1)


def test_temperature_sous_le_zero_absolu_refusee():
    p = chargerExemple("tableau_depart")
    p["reglages"] = {"tservice": ZERO_ABSOLU_C - 1}
    with pytest.raises(ErreurChaine):
        solveurChaine(p)


def test_schema_200_maillons_rapide_et_complet():
    p = _p(n=200)
    t = time.perf_counter()
    fig, _ = figureSchema(p, apercuChaine(p))
    assert time.perf_counter() - t < 5
    assert len(fig.layout.annotations) == 2 * 200 + 2
    assert len(fig.layout.shapes) >= 200


def test_monte_carlo_grand_jeu_conserve_la_dispersion_et_trace():
    p = {
        "condition": {"nom": "J", "jmin": 999.5, "jmax": 1000.5},
        "reglages": {},
        "maillons": [
            {"nom": "a", "sens": "+", "cote": 1000.0, "es": 0.0005, "ei": -0.0005},
            {"nom": "b", "sens": "-", "cote": 500.0, "es": 0.0005, "ei": -0.0005},
            {"nom": "c", "sens": "+", "cote": 500.0, "es": 0.0005, "ei": -0.0005},
        ],
    }
    b = calculerChaine(p, n=20000)
    assert len(np.unique(b["mc"]["J"])) > 5000
    fig, _ = graphiques.figureMonteCarlo(b)
    assert fig is not None


def test_histogramme_non_fini_donne_un_message():
    b = calculerChaine(chargerExemple("tableau_depart"), n=2000)
    b["mc"]["J"] = np.full(2000, np.inf)
    _, legende = graphiques.figureMonteCarlo(b)
    assert "impossible" in legende


def test_nom_trop_long_et_grammaire_import():
    p = chargerExemple("tableau_depart")
    p["maillons"][0]["nom"] = "x" * 300
    with pytest.raises(ErreurChaine) as e:
        importerProbleme(exporterProbleme(p))
    assert "du maillon 1" in e.value.message and "de le" not in e.value.message


def test_pdf_signale_les_caracteres_absents_de_la_police():
    p = chargerExemple("tableau_depart")
    p["maillons"][0]["nom"] = "直径\tx"
    pdf = rapportPdf(p, calculerChaine(p, n=1000), "2026")
    texte = " ".join(" ".join(pg.extract_text() for pg in pypdf.PdfReader(io.BytesIO(pdf)).pages).split())
    assert "remplacés par" in texte
