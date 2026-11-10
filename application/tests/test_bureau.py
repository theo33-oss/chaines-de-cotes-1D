"""Interface de bureau : chaque page s'ouvre et les parcours utiles vont jusqu'au bout, sans exception."""

import copy
import json
import os

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: F401 : à importer avant QApplication
from PySide6.QtWidgets import QFileDialog, QPushButton, QTableWidget, QTabWidget

os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu")

import main as application  # noqa: E402
from chainecotes.bureau import editeur, state, tache, widgets  # noqa: E402
from chainecotes.bureau.pages import assistant as page_assistant  # noqa: E402
from chainecotes.bureau.pages import calcul as page_calcul  # noqa: E402
from chainecotes.bureau.pages import mecanisme as page_mecanisme  # noqa: E402
from chainecotes.bureau.pages import parcours as page_parcours  # noqa: E402
from chainecotes.services.exemples import chargerExemple  # noqa: E402


@pytest.fixture
def fenetre(qtbot):
    state.v.clear()
    state.init()
    f = application.Fenetre()
    qtbot.addWidget(f)
    f.show()
    return f


def page(f, ident):
    f.aller(ident)
    return f.pages[ident][1]


def attendre(qtbot):
    qtbot.waitUntil(lambda: not tache.occupe(), timeout=120000)
    qtbot.wait(30)


def textes(widget):
    return [b.text() for b in widget.findChildren(QPushButton)]


def bouton(widget, texte):
    return next(b for b in widget.findChildren(QPushButton) if b.text() == texte)


def test_toutes_les_pages_s_ouvrent(fenetre, qtbot):
    for ident in fenetre.pages:
        page(fenetre, ident)
        qtbot.wait(20)


@pytest.mark.parametrize("exemple", ["tableau_depart"])
def test_calcul_et_tous_les_onglets(fenetre, qtbot, exemple):
    p = page(fenetre, "calcul")
    state.definirProbleme(chargerExemple(exemple))
    p.tout()
    bouton(p, "Calculer").click()
    qtbot.wait(20)
    attendre(qtbot)
    assert state.resultat() is not None and len(state.historique()) == 1
    tabs = p.findChild(QTabWidget)
    for i in range(tabs.count()):
        tabs.setCurrentIndex(i)
        qtbot.wait(20)


def test_exemple_a_derive_ouvre_son_onglet(fenetre, qtbot):
    p = page(fenetre, "calcul")
    probleme = chargerExemple("tableau_depart")
    probleme["maillons"][0]["derive"] = 2.0
    state.definirProbleme(probleme)
    p.tout()
    p._calculer()
    attendre(qtbot)
    tabs = p.findChild(QTabWidget)
    noms = [tabs.tabText(i) for i in range(tabs.count())]
    tabs.setCurrentIndex(noms.index("Dérive et réglage"))
    qtbot.wait(20)


def test_edition_du_tableau_modifie_le_probleme(fenetre, qtbot):
    p = page(fenetre, "calcul")
    table = next(t for t in p.findChildren(widgets.TableauEditable))
    j = [c.cle for c in table.colonnes].index("cote")
    table.item(0, j).setText("120,5")
    qtbot.wait(20)
    assert state.probleme()["maillons"][0]["cote"] == 120.5
    table = next(t for t in p.findChildren(widgets.TableauEditable))
    table.item(0, j).setText("abc")  # saisie illisible : la case reprend sa valeur
    qtbot.wait(20)
    assert state.probleme()["maillons"][0]["cote"] == 120.5
    assert table.item(0, j).text() == "120,500"


def test_ecart_saisi_remplace_la_designation(fenetre):
    m = {"nom": "a", "cote": 50.0, "iso": "H7", "es": None, "ei": None}
    editeur.modifierCase(m, "es", 0.1)
    assert m["iso"] is None and m["es"] == 0.1 and m["ei"] == 0.0


def test_ajouter_supprimer_deplacer(fenetre, qtbot):
    p = page(fenetre, "calcul")
    n = len(state.probleme()["maillons"])
    bouton(p, "Ajouter").click()
    qtbot.wait(20)
    assert len(state.probleme()["maillons"]) == n + 1
    bouton(p, "Descendre").click()
    qtbot.wait(20)
    bouton(p, "Supprimer").click()
    qtbot.wait(20)
    assert len(state.probleme()["maillons"]) == n


def test_panneau_tolerance_applique_la_designation(fenetre, qtbot):
    page(fenetre, "calcul")
    i = state.v[editeur.CLE_SELECTION]
    assert editeur.decomposerIso("40 h7") == ("Arbre", "h", 7)
    assert editeur.decomposerIso("rien") is None
    assert state.probleme()["maillons"][i]["iso"] == "H7"


def test_enregistrer_puis_ouvrir_un_probleme(fenetre, qtbot, tmp_path, monkeypatch):
    p = page(fenetre, "calcul")
    chemin = tmp_path / "étude (1).json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(chemin), ""))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(chemin), ""))
    avant = copy.deepcopy(state.probleme())
    next(b for b in p.findChildren(QPushButton) if b.text() == "Enregistrer le problème (.json)").click()
    qtbot.wait(20)
    assert json.loads(chemin.read_text(encoding="utf-8"))
    state.probleme()["maillons"].pop()
    p.tout()
    next(b for b in p.findChildren(QPushButton) if b.text() == "Ouvrir un problème (.json)").click()
    qtbot.wait(20)
    assert len(state.probleme()["maillons"]) == len(avant["maillons"])


@pytest.mark.parametrize("format_", ["HTML", "PDF", "Word"])
def test_dossier_et_exports(fenetre, qtbot, tmp_path, monkeypatch, format_):
    p = page(fenetre, "calcul")
    p._calculer()
    attendre(qtbot)
    fichier = page_calcul.fichierDossier(page_calcul.problemeAvecCartouche(state.resultat()), state.resultat(), format_)
    assert len(fichier["contenu"]) > 1000


def test_exports_resultats(fenetre, qtbot, tmp_path, monkeypatch):
    p = page(fenetre, "calcul")
    p._calculer()
    attendre(qtbot)
    tabs = p.findChild(QTabWidget)
    noms = [tabs.tabText(i) for i in range(tabs.count())]
    tabs.setCurrentIndex(noms.index("Fichiers"))
    qtbot.wait(20)
    for i, texte in enumerate(("Résultats Excel (.xlsx)", "Résultats tableur (.csv)", "Feuille de chaîne à formules (.xlsx)",
                               "Tableau de cotation (.xlsx)", "Tableau de cotation (.csv)")):  # fmt: skip
        chemin = tmp_path / f"f{i}.bin"
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, c=chemin, **k: (str(c), ""))
        bouton(p, texte).click()
        qtbot.wait(20)
        assert chemin.stat().st_size > 50


def test_probleme_inverse_applique(fenetre, qtbot):
    p = page(fenetre, "inverse")
    c = state.probleme()["condition"]
    c["jmin"], c["jmax"] = 0.1, 0.4
    p._calculer()
    qtbot.wait(20)
    assert "inv.resultat" in state.v
    p._appliquer()
    qtbot.wait(20)
    assert all(m["iso"] is None for m in state.probleme()["maillons"])


def test_repartition_au_cout_minimal_puis_annulation(fenetre, qtbot):
    """La répartition par coût est une méthode du mode Répartir ; Édition > Annuler remplace l'ancien bouton."""
    p = page(fenetre, "inverse")
    c = state.probleme()["condition"]
    c["jmin"], c["jmax"] = 0.1, 0.4
    state.v["inv.methode"] = "cout_minimal"
    p.tout()
    fenetre._surveiller()
    avant = copy.deepcopy(state.probleme())
    p._calculer()
    qtbot.wait(20)
    assert "cout" in state.v["inv.resultat"]["sortie"]
    p._appliquer()
    qtbot.wait(20)
    assert state.probleme() != avant
    fenetre.annuler()
    assert state.probleme() == avant


def test_comparaison_de_scenarios(fenetre, qtbot):
    # par défaut, B est le résultat de la répartition : on le calcule d'abord
    c = state.probleme()["condition"]
    c["jmin"], c["jmax"] = 0.1, 0.4
    page(fenetre, "inverse")._calculer()
    qtbot.wait(20)
    p = page(fenetre, "optimisation")
    p._calculerScenarios()
    attendre(qtbot)
    assert "opt.scen.resultat" in state.v
    tabs = p.findChild(QTabWidget)
    tabs.setCurrentIndex(1)
    qtbot.wait(20)


def test_mecanisme(fenetre, qtbot):
    p = page(fenetre, "mecanisme")
    p._ajouterCourante()
    p._ajouterCourante()
    assert [e["probleme"]["condition"]["nom"] for e in state.v["meca.chaines"]] == ["Jeu J", "Jeu J (2)"]
    state.v["meca.n"] = 20_000
    p._calculer()
    attendre(qtbot)
    assert state.v["meca.resultat"] is not None
    assert len(page_mecanisme.tableauDeBord(state.v["meca.resultat"]["resultat"]["lignes"])) == 2


def test_assistant_envoie_la_chaine_au_calcul(fenetre, qtbot):
    p = page(fenetre, "assistant")
    assert len(page_assistant.surfaces(state.v["asst.cotes"])) >= 2
    bouton(p, "Utiliser cette chaîne comme étude en cours").click()
    qtbot.wait(20)
    assert state.probleme()["condition"]["nom"] == state.v["asst.nom"]
    assert fenetre.pile.currentWidget() is fenetre.pages["calcul"][1]


def test_parcours_guide(fenetre, qtbot):
    p = page(fenetre, "parcours")
    for i in range(len(page_parcours.ETAPES) - 1):
        bouton(p, "Suivant").click()
        qtbot.wait(20)
        if i == 2:
            bouton(p, "Calculer").click()
            qtbot.wait(20)
            attendre(qtbot)
    assert page_parcours.CLE_BUNDLE in state.v


def test_exemples_charge_dans_calcul(fenetre, qtbot):
    p = page(fenetre, "exemples")
    next(b for b in p.findChildren(QPushButton) if b.text() == "Charger cet exemple").click()
    qtbot.wait(20)
    assert fenetre.pile.currentWidget() is fenetre.pages["calcul"][1]


def test_ajustement_ajoute_a_la_chaine(fenetre, qtbot):
    p = page(fenetre, "ajustement")
    n = len(state.probleme()["maillons"])
    bouton(p, "Utiliser dans la chaîne courante").click()
    qtbot.wait(20)
    assert len(state.probleme()["maillons"]) == n + 2


def test_formats_et_tableau_en_lecture_seule(fenetre):
    import pandas as pd

    t = widgets.TableauDonnees(pd.DataFrame({"a": [1.23456, None]}), {"a": "%.2f"})
    assert isinstance(t, QTableWidget)
    assert t.item(0, 0).text() == "1,23" and t.item(1, 0).text() == ""
    assert not t.item(0, 0).flags() & Qt.ItemFlag.ItemIsEditable
    assert widgets.lireNombre(" 1 000,5 ") == 1000.5 and widgets.lireNombre("") is None
    with pytest.raises(ValueError):
        widgets.lireNombre("abc")
