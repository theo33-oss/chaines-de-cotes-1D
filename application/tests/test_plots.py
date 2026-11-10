"""Tests des figures Plotly : chaque figure se construit sur chaque exemple ; couleurs et échelle du schéma."""

import copy

import plotly.graph_objects as go
import pytest

from chainecotes.plots import (
    figureComparaison,
    figureDistribution,
    figureEffetThermique,
    figureJeuTemperature,
    figureMonteCarlo,
    figurePareto,
    figureRisqueCp,
    figureSchema,
)
from chainecotes.plots._common import GRIS, ROUGE, VERT
from chainecotes.services.calcul import calculerChaine
from chainecotes.services.exemples import chargerExemple, listeExemples

IDS = [e["id"] for e in listeExemples()]
GRAPHIQUES = [
    figurePareto,
    figureMonteCarlo,
    figureComparaison,
    figureDistribution,
    figureRisqueCp,
    figureEffetThermique,
    figureJeuTemperature,
]


@pytest.fixture(scope="module")
def bundles():
    return {i: calculerChaine(chargerExemple(i), n=20_000) for i in IDS}


def _nonVide(fig, legende):
    assert isinstance(fig, go.Figure)
    assert fig.data or fig.layout.annotations or fig.layout.shapes
    assert isinstance(legende, str) and legende.strip()


def _fleche(fig, nom):
    return next(a for a in fig.layout.annotations if a.name == nom)


@pytest.mark.parametrize("ident", IDS)
@pytest.mark.parametrize("fonction", GRAPHIQUES, ids=lambda f: f.__name__)
def test_graphique_sur_chaque_exemple(bundles, ident, fonction):
    _nonVide(*fonction(bundles[ident]))


@pytest.mark.parametrize("ident", IDS)
def test_schema_sur_chaque_exemple(ident):
    _nonVide(*figureSchema(chargerExemple(ident)))


def test_schema_vert_si_conforme():
    fig, legende = figureSchema(chargerExemple("validation_100_40_59"))
    assert _fleche(fig, "condition").arrowcolor == VERT
    assert " dans " in legende


def test_schema_rouge_si_non_conforme():
    fig, legende = figureSchema(chargerExemple("ajustements_h7_h6_n7"))
    assert _fleche(fig, "condition").arrowcolor == ROUGE
    assert "1,0080" in legende and "1,0840" in legende and "hors de" in legende


def test_schema_gris_si_saisie_invalide():
    p = chargerExemple("ajustements_h7_h6_n7")
    p["maillons"][1]["sens"] = "+"
    p["maillons"][2]["sens"] = "+"
    fig, legende = figureSchema(p)
    assert _fleche(fig, "condition").arrowcolor == GRIS
    assert "non fermée" in legende
    assert any("non fermée" in (a.text or "") for a in fig.layout.annotations)


def test_fleches_proportionnelles_aux_cotes():
    p = chargerExemple("validation_100_40_59")
    fig, _ = figureSchema(p)
    for i, m in enumerate(p["maillons"]):
        a = _fleche(fig, f"maillon:{i}")
        attendu = m["cote"] if m["sens"] == "+" else -m["cote"]
        assert a.x - a.ax == pytest.approx(attendu)
    # bout à bout : chaque flèche part de la fin de la précédente, la condition va de l'origine à la fin
    fins = [_fleche(fig, f"maillon:{i}").x for i in range(len(p["maillons"]))]
    assert [_fleche(fig, f"maillon:{i}").ax for i in range(1, len(fins))] == pytest.approx(fins[:-1])
    cond = _fleche(fig, "condition")
    assert (cond.ax, cond.x) == pytest.approx((0.0, fins[-1]))


def test_schema_cinquante_maillons_cote_nulle_et_serrage():
    base = chargerExemple("validation_100_40_59")
    m = base["maillons"][0]
    maillons = [dict(copy.deepcopy(m), nom=f"M{i}", sens="+" if i % 2 else "-", cote=float(i % 7)) for i in range(50)]
    fig, legende = figureSchema({**base, "maillons": maillons})
    _nonVide(fig, legende)
    assert _fleche(fig, "maillon:0").x == _fleche(fig, "maillon:0").ax  # cote nulle
    serrage = copy.deepcopy(base)
    serrage["maillons"][0]["cote"] = 50.0
    fig, legende = figureSchema(serrage)
    assert _fleche(fig, "condition").x < 0
    assert "serrage" in legende


def test_schema_signale_zone_elargie_et_thermique():
    _, legende = figureSchema(chargerExemple("ajustements_h7_h6_n7"))
    assert "élargie" in legende
    _, legende = figureSchema(chargerExemple("cryogenie_azote"))
    assert "en service" in legende


def test_legende_pareto_cite_le_maillon_dominant(bundles):
    for ident in IDS:
        b = bundles[ident]
        dominant = max(b["contributions"], key=lambda c: c["partVariance"])
        if dominant["variance"] > 0:
            assert dominant["nom"] in figurePareto(b)[1]


def test_figures_explicatives_sans_monte_carlo_ni_thermique():
    b = calculerChaine(chargerExemple("validation_100_40_59"), monteCarlo=False)
    assert b["mc"] is None and b["jeuT"] is None
    for f in (figureMonteCarlo, figureEffetThermique, figureJeuTemperature):
        _nonVide(*f(b))
    assert "Monte-Carlo" in figureMonteCarlo(b)[1]


def test_comparaison_verdict_hors_tolerance(bundles):
    _, legende = figureComparaison(bundles["ajustements_h7_h6_n7"])
    assert "pire des cas non conforme" in legende
