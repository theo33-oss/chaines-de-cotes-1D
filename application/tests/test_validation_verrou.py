"""Étude « Validée » : empreinte du problème, verrouillage dans la fenêtre, fichier retouché à la main."""

import copy

import pytest

import main as application
from chainecotes.bureau import state
from chainecotes.services.cartouche import empreinte, etatValidation, lignesCartouche
from chainecotes.services.exemples import chargerExemple
from chainecotes.services.projet_io import exporterProbleme, importerProbleme


@pytest.fixture
def fenetre(qtbot):
    state.v.clear()
    state.init()
    f = application.Fenetre()
    qtbot.addWidget(f)
    f.show()
    return f


def _valider(f, qtbot):
    """Passe l'étude en « Validé » par le menu du cartouche (le vrai chemin de saisie)."""
    from PySide6.QtWidgets import QComboBox

    f.aller("parcours")
    state.v["guide.etape"] = "Dossier"
    f.pages["parcours"][1].afficher()
    liste = next(c for c in f.pages["parcours"][1].findChildren(QComboBox) if c.findText("Validé") >= 0)
    liste.setCurrentIndex(liste.findText("Validé"))
    liste.activated.emit(liste.currentIndex())
    qtbot.wait(50)  # le rappel de la liste est différé


def test_empreinte_ignore_le_cartouche_pas_le_reste():
    p = chargerExemple("tableau_depart")
    e = empreinte(p)
    p["cartouche"] = {"auteur": "X"}
    assert empreinte(p) == e
    p["maillons"][0]["cote"] += 0.001
    assert empreinte(p) != e


def test_etat_modifie_apres_retouche_a_la_main():
    p = chargerExemple("tableau_depart")
    p["cartouche"] = {"statut": "Validé", "empreinte": empreinte(p)}
    assert etatValidation(p) == "valide"
    relu = importerProbleme(exporterProbleme(p))
    assert etatValidation(relu) == "valide"
    relu["maillons"][1]["es"] = 0.5
    assert etatValidation(relu) == "modifie"
    assert any("changé depuis la validation" in t for _, t in lignesCartouche(relu))
    assert any(lib == "Empreinte du problème" for lib, _ in lignesCartouche(p))


def test_valider_pose_l_empreinte_et_le_titre(fenetre, qtbot):
    _valider(fenetre, qtbot)
    p = state.probleme()
    assert p["cartouche"]["statut"] == "Validé" and p["cartouche"]["empreinte"] == empreinte(p)
    fenetre._surveiller()
    assert "[validée]" in fenetre.windowTitle()


def test_modification_refusee_restaure_le_probleme(fenetre, qtbot, monkeypatch):
    _valider(fenetre, qtbot)
    fenetre._surveiller()
    garde = copy.deepcopy(state.probleme())
    monkeypatch.setattr(application, "_demanderDeverrouiller", lambda parent: False)
    state.probleme()["maillons"][0]["cote"] += 1.0
    fenetre._surveiller()
    assert state.probleme() == garde and etatValidation(state.probleme()) == "valide"


def test_modification_acceptee_repasse_en_brouillon(fenetre, qtbot):
    _valider(fenetre, qtbot)
    fenetre._surveiller()
    state.probleme()["maillons"][0]["cote"] += 1.0
    fenetre._surveiller()
    c = state.probleme()["cartouche"]
    assert c["statut"] == "Brouillon" and "empreinte" not in c
