"""Un bouton « Calculer (F5) » est dans l'en-tête des pages Analyser et Répartir, hors de toute zone qui défile."""

from PySide6.QtWidgets import QPushButton, QScrollArea

import main as application
from chainecotes.bureau import state


def test_bouton_en_tete_hors_zone_defilante(qtbot):
    state.v.clear()
    state.init()
    f = application.Fenetre()
    qtbot.addWidget(f)
    f.show()
    for ident in ("calcul", "inverse"):
        f.aller(ident)
        page = f.pages[ident][1]
        boutons = [b for b in page.findChildren(QPushButton) if b.text() == "Calculer (F5)"]
        assert len(boutons) == 1, ident
        parent = boutons[0].parent()
        dans_defilement = False
        while parent is not None and parent is not page:
            dans_defilement = dans_defilement or isinstance(parent, QScrollArea)
            parent = parent.parent()
        assert not dans_defilement, ident


def test_appliquer_a_cote_de_calculer(qtbot):
    state.v.clear()
    state.init()
    f = application.Fenetre()
    qtbot.addWidget(f)
    f.show()
    c = state.probleme()["condition"]
    c["jmin"], c["jmax"] = 0.1, 0.4
    f.aller("inverse")
    page = f.pages["inverse"][1]

    def bouton():
        return next(b for b in page.findChildren(QPushButton) if b.text() == "Appliquer à l'étude")

    assert not bouton().isEnabled()  # rien à appliquer avant le calcul
    page._calculer()
    qtbot.wait(50)
    assert bouton().isEnabled()
    avant = [(m["es"], m["ei"]) for m in state.probleme()["maillons"]]
    bouton().click()
    qtbot.wait(50)
    assert [(m["es"], m["ei"]) for m in state.probleme()["maillons"]] != avant
