"""Lot 3 : un seul vocabulaire de verdict, décimales à la française, verdict en tête, mode Répartir, navigation."""

import copy
import re

import pytest
from PySide6.QtWidgets import QLabel

import main as application
from chainecotes.bureau import state, tache
from chainecotes.core.chaine import libelleVerdict
from chainecotes.services.calcul import calculerChaine
from chainecotes.services.comparaison import comparerScenarios
from chainecotes.services.controles import controlerProbleme
from chainecotes.services.exemples import chargerExemple

POINT_DECIMAL = re.compile(r"\d\.\d")


@pytest.fixture
def fenetre(qtbot):
    state.v.clear()
    state.init()
    f = application.Fenetre()
    qtbot.addWidget(f)
    f.show()
    return f


def _textes(widget) -> str:
    return "\n".join(x.text() for x in widget.findChildren(QLabel))


def _deuxLimites() -> None:
    c = state.probleme()["condition"]
    c["jmin"], c["jmax"] = 0.1, 0.4


def test_libelle_verdict_trois_textes():
    limites, aucune = {"jmin": 0.0, "jmax": 1.0}, {"jmin": float("-inf"), "jmax": float("inf")}
    assert libelleVerdict(True, limites) == "Conforme"
    assert libelleVerdict(False, limites) == "Non conforme"
    assert libelleVerdict(True, aucune) == "Sans limite"


def test_historique_porte_le_vocabulaire_unique():
    state.v.clear()
    state.init()
    state.ajouterHistorique(calculerChaine(chargerExemple("reducteur_jeu_axial"), monteCarlo=False), 0, 1)
    assert state.historique()[-1]["verdict"] in ("Conforme", "Non conforme")


def test_messages_sans_point_decimal():
    p = chargerExemple("tableau_depart")
    p["maillons"][2]["cote"] = 4900.5  # cote aberrante : déclenche les contrôles qui citent des nombres
    p["condition"]["jmax"] = 0.25
    messages = [c["message"] for c in controlerProbleme(p)]
    assert messages and not any(POINT_DECIMAL.search(m) for m in messages), messages
    a = calculerChaine(chargerExemple("tableau_depart"), monteCarlo=False)
    b = chargerExemple("tableau_depart")
    b["maillons"][2].update(es=0.025, ei=-0.025)
    phrases = comparerScenarios(a, calculerChaine(b, monteCarlo=False))["phrases"]
    assert phrases and not any(POINT_DECIMAL.search(x) for x in phrases), phrases


def test_analyse_verdict_en_tete_avant_et_apres_calcul(fenetre, qtbot):
    fenetre.aller("calcul")
    p = fenetre.pages["calcul"][1]
    avant = _textes(p.droite)
    assert "Pire des cas : conforme" in avant and avant.count("Jeu mini") == 1
    p._calculer()
    qtbot.waitUntil(lambda: not tache.occupe(), timeout=120000)
    qtbot.wait(30)
    apres = _textes(p.droite)
    assert "tient les limites dans tous les cas" in apres  # titre de conclusionEtude
    assert "OK" not in apres.split() and "HORS TOLÉRANCE" not in apres


@pytest.mark.parametrize("critere", ["pire_cas", "statistique"])
@pytest.mark.parametrize("methode", ["egale", "proportionnelle", "iso", "cout_minimal"])
def test_repartir_toutes_les_methodes(fenetre, qtbot, methode, critere):
    _deuxLimites()
    state.v["inv.methode"], state.v["inv.critere"] = methode, critere
    fenetre.aller("inverse")
    p = fenetre.pages["inverse"][1]
    p._calculer()
    qtbot.wait(20)
    sortie = state.v["inv.resultat"]["sortie"]
    assert sortie["tenue"] and ("cout" in sortie) == (methode == "cout_minimal")
    assert "Schéma de la chaîne avec les tolérances réparties" in _textes(p.droite)


def test_repartir_appliquer_puis_annuler(fenetre, qtbot):
    _deuxLimites()
    fenetre.aller("inverse")
    fenetre._surveiller()
    avant = copy.deepcopy(state.probleme())
    p = fenetre.pages["inverse"][1]
    p._calculer()
    qtbot.wait(20)
    p._appliquer()
    assert state.probleme() != avant
    fenetre.annuler()
    assert state.probleme() == avant


def test_etude_en_cours_rouvre_le_dernier_mode(fenetre, qtbot):
    rang = fenetre.pages["calcul"][0]
    assert fenetre.pages["inverse"][0] == fenetre.pages["optimisation"][0] == rang
    fenetre.aller("inverse")
    assert fenetre.pile.currentWidget() is fenetre.pages["inverse"][1]
    fenetre.aller("materiaux")
    fenetre.menu.setCurrentRow(rang)  # clic sur « Étude en cours »
    assert fenetre.pile.currentWidget() is fenetre.pages["inverse"][1]
    fenetre.aller("optimisation")  # même ligne du menu, autre mode
    assert fenetre.pile.currentWidget() is fenetre.pages["optimisation"][1]
    assert fenetre.menu.currentRow() == rang
