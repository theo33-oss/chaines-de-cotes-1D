"""Tests de la comparaison de scénarios et du dépôt de fichiers en lot."""

import copy

import pytest

from chainecotes.services.calcul import calculerChaine
from chainecotes.services.comparaison import comparerFichiers, comparerScenarios
from chainecotes.services.exemples import chargerExemple
from chainecotes.services.mecanisme import exporterMecanisme
from chainecotes.services.projet_io import exporterProbleme

N = 3000


def _b(p):
    return calculerChaine(p, True, N, 1)


def test_scenarios_identiques():
    p = chargerExemple("tableau_depart")
    r = comparerScenarios(_b(p), _b(copy.deepcopy(p)))
    assert r["identiques"]
    for k in ("jeuMini", "jeuMaxi", "cpk", "ppm"):
        assert r[k]["delta"] == pytest.approx(0.0, abs=1e-12)
    assert all(m["statut"] == "commun" and m["delta"] == 0 for m in r["maillons"])
    assert "identiques" in r["phrases"][0]


def test_tolerance_modifiee():
    p = chargerExemple("validation_100_40_59")
    q = copy.deepcopy(p)
    q["maillons"][0]["iso"] = None
    q["maillons"][0]["es"], q["maillons"][0]["ei"] = 0.2, -0.2
    a, b = _b(p), _b(q)
    r = comparerScenarios(a, b)
    assert not r["identiques"]
    m = r["maillons"][0]
    assert m["delta"] == pytest.approx(0.4 - a["res"]["IT"][0])
    assert r["jeuMaxi"]["delta"] == pytest.approx(b["verdicts"]["pireCas"]["max"] - a["verdicts"]["pireCas"]["max"])
    assert any("Tolérance de" in s for s in r["phrases"])


def test_maillon_ajoute_et_supprime():
    p = chargerExemple("tableau_depart")
    q = copy.deepcopy(p)
    supprime = q["maillons"].pop()
    nouveau = copy.deepcopy(p["maillons"][0])
    nouveau["nom"] = "Rondelle"
    nouveau["cote"] = nouveau["cote"] + 0.0
    q["maillons"].append(nouveau)
    # q perd le dernier maillon et en gagne un autre : on compare sans exiger la fermeture, via les bundles
    a = _b(p)
    b = _b(q)
    r = comparerScenarios(a, b)
    statuts = {m["nom"]: m["statut"] for m in r["maillons"]}
    assert statuts["Rondelle"] == "ajouté"
    assert statuts[supprime["nom"]] == "supprimé"
    assert any("Maillon ajouté : Rondelle" in s for s in r["phrases"])
    assert any(f"Maillon supprimé : {supprime['nom']}" in s for s in r["phrases"])


def test_lot_de_fichiers_avec_invalide():
    p = chargerExemple("tableau_depart")
    m = {"nom": "M", "chaines": [chargerExemple("validation_100_40_59"), chargerExemple("thermique_alu_acier")]}
    r = comparerFichiers({"a.json": exporterProbleme(p), "b.json": "pas du json", "c.json": exporterMecanisme(m)}, N, 1)
    assert [x["fichier"] for x in r["lignes"]] == ["a.json", "c.json", "c.json"]
    assert [e["fichier"] for e in r["erreurs"]] == ["b.json"] and r["erreurs"][0]["message"]
    assert r["lignes"][0]["jeuMini"] == pytest.approx(_b(p)["verdicts"]["pireCas"]["min"])


def test_lot_en_liste():
    r = comparerFichiers([exporterProbleme(chargerExemple("tableau_depart")), "{}"], N, 1)
    assert len(r["lignes"]) == 1 and r["erreurs"][0]["fichier"] == "Fichier 2"


def test_comparaison_limite_le_nombre_de_fichiers():
    from chainecotes.services.comparaison import MAX_FICHIERS, comparerFichiers
    from chainecotes.services.exemples import chargerExemple
    from chainecotes.services.projet_io import exporterProbleme

    texte = exporterProbleme(chargerExemple("tableau_depart"))
    r = comparerFichiers({f"f{i}.json": texte for i in range(MAX_FICHIERS + 3)}, 1000)
    assert len(r["lignes"]) == MAX_FICHIERS
    assert len(r["erreurs"]) == 3 and all("ignoré" in e["message"] for e in r["erreurs"])
