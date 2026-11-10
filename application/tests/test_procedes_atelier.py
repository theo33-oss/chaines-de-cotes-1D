"""Procédés de l'atelier : enregistrement, lecture au lancement, import / export, valeurs invalides."""

import json

import pytest

from chainecotes.core.errors import ErreurChaine
from chainecotes.services import procedes_atelier as pa

VALEURS = {"tournage": {"c": 1.4, "n": 1.1, "itmin": 7, "itmax": 12}}


def test_aller_retour_fichier(tmp_path):
    chemin = tmp_path / "dossier neuf" / "p.json"  # le dossier est créé
    pa.ecrireFichier(VALEURS, chemin)
    valeurs, erreur = pa.lireFichier(chemin)
    assert erreur is None and valeurs == VALEURS


def test_seules_les_valeurs_modifiees_sont_gardees():
    texte = pa.exporterProcedes({"tournage": {"c": 1.0, "n": 1.0, "itmin": 6, "itmax": 13}, "fraisage": {"c": 2.0}})
    assert json.loads(texte)["procedes"] == {"fraisage": {"c": 2.0}}  # tournage = valeurs indicatives


def test_fichier_absent_ou_invalide_ne_plante_pas(tmp_path):
    assert pa.lireFichier(tmp_path / "absent.json") == ({}, None)
    casse = tmp_path / "casse.json"
    casse.write_text("{pas du json", encoding="utf-8")
    valeurs, erreur = pa.lireFichier(casse)
    assert valeurs == {} and "JSON" in erreur


@pytest.mark.parametrize("mauvais", [
    {"inconnu": {"c": 1.0}},
    {"tournage": {"c": -1.0}},
    {"tournage": {"n": 0}},
    {"tournage": {"itmin": 12, "itmax": 7}},
    {"tournage": {"itmax": 40}},
    {"tournage": {"c": "beaucoup"}},
    {"tournage": {"zzz": 1}},
])
def test_valeurs_invalides_refusees(mauvais):
    with pytest.raises(ErreurChaine):
        pa.exporterProcedes(mauvais)


def test_import_refuse_un_autre_fichier():
    with pytest.raises(ErreurChaine, match="enregistré"):
        pa.importerProcedes(json.dumps({"format": "autre", "version": 1, "procedes": {}}))


def test_page_poser_enregistrer_et_effacer(qtbot, tmp_path, monkeypatch):
    import main as application
    from chainecotes.bureau import state
    from chainecotes.bureau.pages import inverse

    state.v.clear()
    state.init()
    monkeypatch.setattr(pa, "cheminParDefaut", lambda: tmp_path / "p.json")
    inverse.poserValeursAtelier(VALEURS)
    assert state.v["opt.cout.atelier.tournage.c"] == 1.4 and inverse.valeursAtelier() == VALEURS
    f = application.Fenetre()
    qtbot.addWidget(f)
    f.aller("inverse")
    page = f.pages["inverse"][1]
    state.v["inv.methode"] = "cout_minimal"
    page.parametres.rafraichir()
    page._enregistrerAtelier()
    assert pa.lireFichier(tmp_path / "p.json")[0] == VALEURS
    page._effacerAtelier()
    assert inverse.valeursAtelier() == {}
    page._importerAtelier([("p.json", (tmp_path / "p.json").read_bytes())])
    assert inverse.valeursAtelier() == VALEURS
