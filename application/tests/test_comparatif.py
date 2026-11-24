"""Tests de la comparaison de chaînes en colonnes : valeurs, erreurs isolées, noms, écarts, exports, figures."""

import copy
import json
import math
import re

import pytest

from chainecotes.core.errors import ErreurChaine
from chainecotes.plots.comparatif import figuresComparatif
from chainecotes.services.calcul import calculerChaine
from chainecotes.services.comparatif import comparerColonnes
from chainecotes.services.exemples import chargerExemple, listeExemples

N = 2000


def _trois():
    return [
        {"nom": i, "probleme": chargerExemple(i)}
        for i in ("tableau_depart", "ajustements_h7_h6_n7", "validation_100_40_59")
    ]


def _ligne(r, libelle):
    return next(x for x in r["lignes"] if x["libelle"] == libelle)


def _sans_nan(r):
    textes = [v for x in r["lignes"] for v in x["valeurs"] if v is not None] + [r["csv"], r["texte"]]
    assert not any(re.search(r"\bnan\b", t, re.IGNORECASE) for t in textes)


def test_valeurs_coherentes_avec_calculerChaine():
    cols = _trois()
    r = comparerColonnes(cols, n=N)
    assert r["nTirages"] == N and len(r["colonnes"]) == 3
    for j, c in enumerate(cols):
        v = calculerChaine(copy.deepcopy(c["probleme"]), True, N)["verdicts"]
        assert _ligne(r, "Pire cas mini (mm)")["nombres"][j] == pytest.approx(v["pireCas"]["min"])
        assert _ligne(r, "Pire cas maxi (mm)")["nombres"][j] == pytest.approx(v["pireCas"]["max"])
        cpk = _ligne(r, "Cpk")["nombres"][j]
        if math.isfinite(v["cpk"]):
            assert cpk == pytest.approx(v["cpk"])
        else:
            assert cpk is None and _ligne(r, "Cpk")["valeurs"][j] == "—"
    _sans_nan(r)


def test_texte_a_la_francaise_sans_exposant():
    r = comparerColonnes(_trois(), n=N)
    for ligne in r["lignes"]:
        for v in ligne["valeurs"]:
            assert v is not None and "e+" not in v and "." not in v.replace("...", "")
    assert "+" not in "".join(_ligne(r, "Jmin exigé (mm)")["valeurs"][0])


def test_formes_et_groupes():
    r = comparerColonnes(_trois(), n=N)
    assert r["reference"] == 0
    assert {x["groupe"] for x in r["lignes"]} == {
        "Exigence",
        "Résultat au pire des cas",
        "Statistique",
        "Capabilité et risque",
        "Chaîne",
    }
    assert len(r["classes"]) == len(r["lignes"]) and all(len(c) == 3 for c in r["classes"])
    for c in r["colonnes"]:
        assert c["verdict"] in {"conforme", "non conforme", "indicatif", "erreur"}
        assert c["niveau"] in {"succes", "avertissement", "erreur", "info"}
    for ligne in r["lignes"]:
        assert len(ligne["valeurs"]) == len(ligne["nombres"]) == len(ligne["ecarts"]) == 3
        assert ligne["ecarts"][0] is None
    # sérialisable une fois _bundles retiré
    r.pop("_bundles")
    json.dumps(r)


def test_exemples_reels_plusieurs():
    ids = [e["id"] for e in listeExemples()][:6]
    r = comparerColonnes([{"nom": i, "probleme": chargerExemple(i)} for i in ids], n=N)
    assert len(r["colonnes"]) == len(ids)
    assert all(c["erreur"] is None for c in r["colonnes"])
    _sans_nan(r)


def test_colonne_en_erreur_narrete_pas_les_autres():
    cols = _trois()
    cols[1]["probleme"]["maillons"][0]["cote"] = "abc"
    r = comparerColonnes(cols, n=N)
    assert r["colonnes"][1]["erreur"] and r["colonnes"][1]["verdict"] == "erreur"
    assert r["colonnes"][0]["erreur"] is None and r["colonnes"][2]["erreur"] is None
    cpk = _ligne(r, "Cpk")
    assert cpk["valeurs"][1] is None and cpk["nombres"][1] is None and cpk["ecarts"][1] is None
    assert cpk["nombres"][0] is not None and cpk["nombres"][2] is not None
    assert r["classes"][0][1] == "erreur"
    assert r["_bundles"][1] is None and r["_bundles"][0] is not None
    assert "Erreur" in r["texte"]
    _sans_nan(r)


def test_probleme_absent_ou_incomplet():
    cols = [{"nom": "A", "probleme": chargerExemple("tableau_depart")}, {"nom": "B"}, {"nom": "C", "probleme": {}}]
    r = comparerColonnes(cols, n=N)
    assert r["colonnes"][0]["erreur"] is None
    assert r["colonnes"][1]["erreur"] and r["colonnes"][2]["erreur"]


def test_noms_vides_et_doublons():
    p = chargerExemple("tableau_depart")
    r = comparerColonnes(
        [{"nom": "Jeu J", "probleme": p}, {"nom": "Jeu J", "probleme": p}, {"nom": "  ", "probleme": p}, {"probleme": p}],
        n=N,
    )
    assert [c["nom"] for c in r["colonnes"]] == ["Jeu J", "Jeu J (2)", "Chaîne 3", "Chaîne 4"]


def test_nombre_de_colonnes():
    p = chargerExemple("tableau_depart")
    r1 = comparerColonnes([{"nom": "A", "probleme": p}], n=N)
    assert len(r1["colonnes"]) == 1 and _ligne(r1, "Cpk")["meilleur"] is None
    assert all(e is None for x in r1["lignes"] for e in x["ecarts"])
    r12 = comparerColonnes([{"nom": f"C{i}", "probleme": p} for i in range(12)], n=N)
    assert len(r12["colonnes"]) == 12
    with pytest.raises(ErreurChaine, match="12 au plus"):
        comparerColonnes([{"nom": f"C{i}", "probleme": p} for i in range(13)], n=N)
    with pytest.raises(ErreurChaine):
        comparerColonnes([], n=N)
    with pytest.raises(ErreurChaine, match="référence"):
        comparerColonnes([{"nom": "A", "probleme": p}], reference=3, n=N)


def test_tirages_partages():
    p = chargerExemple("tableau_depart")
    r = comparerColonnes([{"nom": f"C{i}", "probleme": p} for i in range(12)], n=1_000_000)
    assert r["nTirages"] == 2_000_000 // 12


def test_reference_change_les_ecarts():
    cols = _trois()
    r0 = comparerColonnes(cols, reference=0, n=N)
    r1 = comparerColonnes(cols, reference=1, n=N)
    assert r0["reference"] == 0 and r1["reference"] == 1
    nom = "Pire cas maxi (mm)"
    e0, e1 = _ligne(r0, nom)["ecarts"], _ligne(r1, nom)["ecarts"]
    assert e0[0] is None and e0[1] is not None
    assert e1[1] is None and e1[0] is not None
    n = _ligne(r0, nom)["nombres"]
    assert (e0[1] == "0") == (abs(n[1] - n[0]) < 5e-5)
    if n[1] - n[0] > 5e-5:
        assert e0[1].startswith("+")
    # un écart relatif en %
    assert any(e is None or e.endswith("%") or e == "0 %" for e in _ligne(r0, "Hors tolérance, formule (ppm)")["ecarts"])


def test_identique_et_meilleur():
    p = chargerExemple("tableau_depart")
    r = comparerColonnes([{"nom": "A", "probleme": p}, {"nom": "B", "probleme": copy.deepcopy(p)}], n=N)
    assert all(x["identique"] for x in r["lignes"])
    assert _ligne(r, "Cpk")["meilleur"] is None
    p2 = copy.deepcopy(p)
    for m in p2["maillons"]:
        m["iso"], m["es"], m["ei"] = None, 0.2, -0.2
    r2 = comparerColonnes([{"nom": "A", "probleme": p}, {"nom": "B", "probleme": p2}], n=N)
    cpk = _ligne(r2, "Cpk")
    assert not cpk["identique"]
    n = cpk["nombres"]
    assert cpk["meilleur"] == (0 if n[0] > n[1] else 1)
    assert _ligne(r2, "σ du jeu (mm)")["meilleur"] == (0 if _ligne(r2, "σ du jeu (mm)")["nombres"][0] < _ligne(r2, "σ du jeu (mm)")["nombres"][1] else 1)
    assert _ligne(r2, "Jmin exigé (mm)")["meilleur"] is None


def test_csv_et_texte():
    r = comparerColonnes(_trois(), n=N)
    assert r["csv"].startswith("﻿")
    premiere = r["csv"].lstrip("﻿").splitlines()[0].split(";")
    assert premiere == ["Grandeur"] + [c["nom"] for c in r["colonnes"]]
    assert all(len(rang.split(";")) >= 4 for rang in r["csv"].lstrip("﻿").splitlines())
    rangs = r["texte"].split("\n")
    assert all(rang.count("\t") == 3 for rang in rangs)
    assert "·10" not in r["texte"] and "·10" not in r["csv"]
    assert "﻿" not in r["texte"]
    assert any(rang.startswith("Cpk\t") for rang in rangs)


def test_exposant_lisible_par_tableur():
    p = chargerExemple("tableau_depart")
    p2 = copy.deepcopy(p)
    for m in p2["maillons"]:
        m["iso"], m["es"], m["ei"] = None, 0.0, -1e-9
    r = comparerColonnes([{"nom": "A", "probleme": p2}, {"nom": "B", "probleme": p}], n=N)
    assert "·10" not in r["texte"] and "e+" not in r["texte"]


def test_noms_neutralises_pour_tableur():
    p = chargerExemple("tableau_depart")
    r = comparerColonnes([{"nom": "=SOMME(A1)", "probleme": p}], n=N)
    assert "'=SOMME(A1)" in r["csv"] and r["colonnes"][0]["nom"] == "=SOMME(A1)"


def test_figures_serialisables():
    r = comparerColonnes(_trois(), n=N)
    figs = figuresComparatif(r)
    assert [f["id"] for f in figs] == ["plages", "cpk", "distributions"]
    for f in figs:
        assert f["titre"] and f["description"]
        j = json.loads(f["fig"].to_json())
        assert j["data"] and any(len(t.get("x", [])) or len(t.get("y", [])) for t in j["data"])
        assert j["layout"]["separators"] == ", "
    # trois colonnes : trois barres Cpk, un histogramme par colonne
    assert sum(1 for t in figs[1]["fig"].data if t.type == "bar") == 3
    assert sum(1 for t in figs[2]["fig"].data if t.type == "bar") == 3


def test_figures_colonne_en_erreur_ignoree_et_toutes_en_erreur():
    cols = _trois()
    cols[0]["probleme"]["maillons"][0]["cote"] = "abc"
    r = comparerColonnes(cols, n=N)
    figs = figuresComparatif(r)
    assert sum(1 for t in figs[1]["fig"].data if t.type == "bar") == 2
    r2 = comparerColonnes([{"nom": "A", "probleme": {}}, {"nom": "B", "probleme": {}}], n=N)
    assert figuresComparatif(r2) == []


def test_figures_sans_cpk_ni_monte_carlo():
    p = chargerExemple("tableau_depart")
    for m in p["maillons"]:
        m["iso"], m["es"], m["ei"] = None, 0.0, 0.0  # tolérances nulles : pas de dispersion
    r = comparerColonnes([{"nom": "A", "probleme": p}], n=N)
    figs = figuresComparatif(r)
    assert [f["id"] for f in figs] == ["plages", "cpk", "distributions"]
    for f in figs:
        json.loads(f["fig"].to_json())
    _sans_nan(r)


def test_figures_exigent_les_bundles():
    r = comparerColonnes(_trois(), n=N)
    r.pop("_bundles")
    with pytest.raises(ValueError, match="_bundles"):
        figuresComparatif(r)


def test_cpk_absent_affiche_tiret_et_figure_ignoree():
    cols = [{"nom": i, "probleme": chargerExemple(i)} for i in ("tableau_depart", "thermique_alu_acier")]
    r = comparerColonnes(cols, n=N)
    cpk = _ligne(r, "Cpk")
    assert cpk["valeurs"][1] == "—" and cpk["nombres"][1] is None and cpk["ecarts"][1] is None
    assert r["classes"][r["lignes"].index(cpk)][1] == "vide"
    assert sum(1 for t in figuresComparatif(r)[1]["fig"].data if t.type == "bar") == 1
    _sans_nan(r)
