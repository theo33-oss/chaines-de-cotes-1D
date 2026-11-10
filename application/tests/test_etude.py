"""État de l'étude dans la fenêtre : fichier courant, « modifié », annulation, confirmation avant de perdre un travail."""

import copy
import json

import pytest
from PySide6.QtWidgets import QFileDialog

import main as application
from chainecotes.bureau import state


@pytest.fixture
def fenetre(qtbot):
    state.v.clear()
    state.init()
    f = application.Fenetre()
    qtbot.addWidget(f)
    f.show()
    return f


def _modifier():
    state.probleme()["maillons"][0]["cote"] += 1.0


def test_modifiee_suit_la_saisie_et_l_enregistrement(fenetre, tmp_path, monkeypatch):
    assert not state.modifiee() and state.chemin() is None
    _modifier()
    fenetre._surveiller()
    assert state.modifiee() and fenetre.isWindowModified()
    chemin = tmp_path / "étude.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(chemin), ""))
    assert fenetre.enregistrer()
    assert not state.modifiee() and not fenetre.isWindowModified()
    assert "étude.json" in fenetre.windowTitle()
    # Ctrl+S suivant : réécrit le même fichier sans redemander où
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: pytest.fail("dialogue inattendu"))
    _modifier()
    assert fenetre.enregistrer()
    assert json.loads(chemin.read_text(encoding="utf-8")) and not state.modifiee()


def test_annuler_puis_retablir(fenetre):
    avant = copy.deepcopy(state.probleme())
    _modifier()
    apres = copy.deepcopy(state.probleme())
    fenetre.annuler()
    assert state.probleme() == avant
    fenetre.retablir()
    assert state.probleme() == apres
    fenetre.retablir()  # plus rien à rétablir : sans effet
    assert state.probleme() == apres


def test_une_autre_etude_vide_l_annulation(fenetre):
    _modifier()
    fenetre._surveiller()
    assert fenetre.actionAnnuler.isEnabled()
    fenetre.aller("calcul")
    fenetre.pages["calcul"][1]._chargerExemple()
    fenetre._surveiller()
    assert not fenetre.actionAnnuler.isEnabled() and not state.modifiee()


def test_refuser_la_confirmation_garde_l_etude(fenetre, monkeypatch):
    _modifier()
    garde = copy.deepcopy(state.probleme())
    monkeypatch.setattr(application, "_demander", lambda parent: "annuler")
    fenetre.aller("calcul")
    fenetre.pages["calcul"][1]._chargerExemple()
    assert state.probleme() == garde
    assert not fenetre.close()  # la fermeture est refusée elle aussi
    monkeypatch.setattr(application, "_demander", lambda parent: "abandonner")


def test_ouvrir_par_le_menu_retient_le_fichier(fenetre, tmp_path, monkeypatch):
    chemin = tmp_path / "a.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(chemin), ""))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(chemin), ""))
    assert fenetre.enregistrerSous()
    enregistre = copy.deepcopy(state.probleme())
    _modifier()
    fenetre.ouvrir()
    assert state.probleme() == enregistre and state.chemin() == str(chemin) and not state.modifiee()
