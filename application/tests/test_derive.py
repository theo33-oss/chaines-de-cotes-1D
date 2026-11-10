"""Dérive : série du jeu moyen, ppm, Cpk et intervalle de re-réglage."""

import math

import pytest
from scipy.stats import norm

from chainecotes.core.chaine import ppmHorsTolerance
from chainecotes.core.derive import deriveSerie
from chainecotes.core.errors import ErreurChaine

SIGMA = math.sqrt((0.2 / 6) ** 2 + 2 * (0.1 / 6) ** 2)


def _probleme(deriveA=None, deriveB=None, jmin=0.9, jmax=1.3, decentrage=None):
    """J = 100 − 40 − 59 = 1 mm ; la dérive (µm / 1000 pièces) s'applique à A (+) et B (−)."""
    reglages = {"kSigma": 3}
    if decentrage is not None:
        reglages["decentrage"] = decentrage
    donnees = [("A", "+", 100.0, 0.1, deriveA), ("B", "-", 40.0, 0.05, deriveB), ("C", "-", 59.0, 0.05, None)]
    maillons = [{"nom": n, "sens": s, "cote": c, "es": e, "ei": -e, "derive": d} for n, s, c, e, d in donnees]
    return {"condition": {"jmin": jmin, "jmax": jmax}, "reglages": reglages, "maillons": maillons}


def test_un_maillon_cas_analytique():
    """A dérive de +20 µm / 1000 pièces : v = 0,02 mm / 1000 ; la moyenne atteint Jmax = 1,3 à 15 000 pièces."""
    s = deriveSerie(_probleme(deriveA=20.0), 20000, 5000)
    assert s["vitesse"] == pytest.approx(0.02)
    assert s["n"] == [0, 5000, 10000, 15000, 20000]
    assert s["mu"] == pytest.approx([1.0, 1.1, 1.2, 1.3, 1.4])
    assert s["piecesSortieMoyenne"] == pytest.approx(15000)
    assert s["cpk"][3] == pytest.approx(0.0, abs=1e-12) and s["cpk"][4] < 0
    assert s["piecesSeuilPpm"] is None
    assert s["intervalleRecalage"] in (14999, 15000)


def test_comparaison_calcul_direct():
    s = deriveSerie(_probleme(deriveA=20.0), 20000, 2500)
    for n, mu, ppm, cpk in zip(s["n"], s["mu"], s["ppm"], s["cpk"], strict=True):
        m = 1.0 + 0.02 * n / 1000
        assert mu == pytest.approx(m)
        assert ppm == pytest.approx(ppmHorsTolerance(m, SIGMA, 0.9, 1.3), rel=1e-12)
        assert ppm == pytest.approx(1e6 * (norm.cdf((0.9 - m) / SIGMA) + norm.sf((1.3 - m) / SIGMA)), rel=1e-9)
        assert cpk == pytest.approx(min(m - 0.9, 1.3 - m) / (3 * SIGMA), rel=1e-12)


def test_derive_maillon_negatif_et_compensation():
    """B (sens −) dérive de +10 µm : le jeu baisse de 0,01 mm / 1000 ; sortie par Jmin = 0,9 à 10 000 pièces."""
    s = deriveSerie(_probleme(deriveB=10.0), 1000, 1000)
    assert s["vitesse"] == pytest.approx(-0.01)
    assert s["piecesSortieMoyenne"] == pytest.approx(10000)
    c = deriveSerie(_probleme(deriveA=10.0, deriveB=10.0), 1000, 500)
    assert c["vitesse"] == pytest.approx(0.0, abs=1e-15)


def test_seuil_ppm_franchi_au_bon_moment():
    s = deriveSerie(_probleme(deriveA=20.0), 20000, 1000, seuilPpm=20000.0)
    n = s["piecesSeuilPpm"]
    assert 0 < n < s["piecesSortieMoyenne"]
    assert ppmHorsTolerance(1.0 + 0.02 * n / 1000, SIGMA, 0.9, 1.3) == pytest.approx(20000.0, rel=1e-6)
    assert s["intervalleRecalage"] == math.floor(n)


def test_seuil_deja_depasse_ou_sortie_deja_faite():
    assert deriveSerie(_probleme(deriveA=20.0), 0, 1, seuilPpm=0.0)["piecesSeuilPpm"] == 0.0
    s = deriveSerie(_probleme(deriveA=20.0, jmin=1.05, jmax=1.3), 10, 5)  # moyenne déjà sous Jmin
    assert s["piecesSortieMoyenne"] == 0.0 and s["intervalleRecalage"] == 0


def test_decentrage_pris_en_compte():
    s = deriveSerie(_probleme(deriveA=20.0, decentrage=1.0), 10, 10)
    assert s["mu"][0] == pytest.approx(1.0 - SIGMA)  # plus proche de Jmin (0,9)


def test_derive_vers_limite_absente_les_ppm_baissent():
    s = deriveSerie(_probleme(deriveA=20.0, jmax=None), 20000, 10000, seuilPpm=1e5)
    assert s["piecesSortieMoyenne"] is None and s["piecesSeuilPpm"] is None and s["intervalleRecalage"] is None
    assert s["ppm"][2] < s["ppm"][0]


def test_derive_nulle_et_sans_limite_series_plates():
    plat = deriveSerie(_probleme(), 3000, 1000, seuilPpm=50.0)
    assert len(set(plat["mu"])) == len(set(plat["ppm"])) == len(set(plat["cpk"])) == 1
    assert plat["intervalleRecalage"] is None
    libre = deriveSerie(_probleme(deriveA=20.0, jmin=None, jmax=None), 3000, 1000, seuilPpm=50.0)
    assert all(math.isnan(x) for x in libre["cpk"]) and libre["ppm"] == [0.0] * 4
    assert libre["intervalleRecalage"] is None


def test_pas_superieur_a_nPieces_et_sigma_nul():
    assert deriveSerie(_probleme(deriveA=1.0), 0, 100)["n"] == [0]
    p = _probleme(deriveA=20.0)
    for m in p["maillons"]:
        m["es"] = m["ei"] = 0.0
    s = deriveSerie(p, 20000, 10000, seuilPpm=1e5)
    assert all(math.isnan(x) for x in s["ppm"]) and s["piecesSeuilPpm"] is None
    assert s["piecesSortieMoyenne"] == pytest.approx(15000)


@pytest.mark.parametrize(
    ("n", "pas", "seuil"),
    [(-1, 1, None), (10, 0, None), (10, -5, None), (10.5, 1, None), (10, 1, -1.0), (10, 1, math.nan)],
)
def test_parametres_invalides(n, pas, seuil):
    with pytest.raises(ErreurChaine):
        deriveSerie(_probleme(), n, pas, seuil)
