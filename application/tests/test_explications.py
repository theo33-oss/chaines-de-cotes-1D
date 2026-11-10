"""Explications du calcul : sections attendues, valeurs du calcul dans les formules, LaTeX équilibré."""

import pytest

from chainecotes.services.calcul import calculerChaine
from chainecotes.services.exemples import chargerExemple, listeExemples
from chainecotes.services.explications import _tex, explicationsCalcul

IDS = [e["id"] for e in listeExemples()]
COMMUNES = ["1. Projection", "2. Cote moyenne", "3. Jeu nominal", "4. Pire des cas", "5. Calcul statistique"]


@pytest.fixture(scope="module")
def calculs():
    return {i: calculerChaine(chargerExemple(i), n=5000) for i in IDS}


def _titres(sections):
    return [s["titre"] for s in sections]


def _present(titres, debut):
    return any(t.startswith(debut) for t in titres)


@pytest.mark.parametrize("ident", IDS)
def test_sections_attendues(calculs, ident):
    b = calculs[ident]
    sections = explicationsCalcul(b)
    titres = _titres(sections)
    for debut in COMMUNES:
        assert _present(titres, debut), debut
    assert _present(titres, "7. ") == (b["mc"] is not None)
    assert _present(titres, "8. Effet thermique") == b["res"]["thermique_actif"]
    assert _present(titres, "9. Avertissements") == bool(b["avertissements"])
    for s in sections:
        assert set(s) == {"titre", "texte", "formules"}
        for f in s["formules"]:
            assert f.count("{") == f.count("}"), f
            assert f.count(r"\left") == f.count(r"\right"), f


def test_valeurs_dans_formules(calculs):
    b = calculs["ajustements_h7_h6_n7"]
    sections = {s["titre"][:2]: s for s in explicationsCalcul(b)}
    res, v = b["res"], b["verdicts"]
    f3 = " ".join(sections["3."]["formules"])
    assert _tex(res["CF_nom"]) in f3 and _tex(res["CF_moy"]) in f3
    assert "100{,}0175" in f3  # cote moyenne de 100 H7
    f4 = " ".join(sections["4."]["formules"])
    assert _tex(res["CF_min"]) in f4 and _tex(res["CF_max"]) in f4
    assert "1{,}008" in f4 and "1{,}084" in f4  # valeurs de l'aide MATLAB, page 04
    f5 = " ".join(sections["5."]["formules"])
    assert _tex(res["CF_sigma"], 6) in f5
    f6 = " ".join(sections["6."]["formules"])
    assert _tex(v["cp"], 3) in f6 and _tex(v["cpk"], 3) in f6 and _tex(v["ppm"], 1) in f6
    f7 = " ".join(sections["7."]["formules"])
    assert str(b["mc"]["nHors"]) in f7 and _tex(b["mc"]["ppm"], 1) in f7
    assert "IT7 = 35 µm" in sections["2."]["texte"]
    assert "1,046" in sections["3."]["texte"]  # virgule décimale dans le texte


def test_thermique(calculs):
    b = calculs["cryogenie_azote"]
    s8 = next(s for s in explicationsCalcul(b) if s["titre"].startswith("8."))
    f8 = " ".join(s8["formules"])
    assert _tex(b["res"]["dJ_th"], 6) in f8
    for x in b["res"]["dJ_th_i"]:
        assert _tex(x, 6) in f8


def test_sans_thermique_ni_limites():
    p = chargerExemple("ajustements_h7_h6_n7")
    p["condition"].update(jmin=None, jmax=None)
    b = calculerChaine(p, monteCarlo=False)
    titres = _titres(explicationsCalcul(b))
    assert not _present(titres, "6.") and not _present(titres, "7.") and not _present(titres, "8.")
    assert _present(titres, "9. Avertissements")


def test_somme_resumee_au_dela_de_8():
    p = chargerExemple("validation_100_40_59")
    p["maillons"] = p["maillons"] + [dict(p["maillons"][1], nom=f"Cale {i}", cote=0.0) for i in range(8)]
    b = calculerChaine(p, monteCarlo=False)
    s3 = next(s for s in explicationsCalcul(b) if s["titre"].startswith("3."))
    assert r"\sum_{i=1}^{11}" in s3["formules"][0]
    assert _tex(b["res"]["CF_nom"]) in s3["formules"][0]
