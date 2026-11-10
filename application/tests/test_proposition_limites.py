"""La page Répartir propose un jeu de 0,05 à 0,1 mm quand Jmin ou Jmax manque."""

from PySide6.QtWidgets import QPushButton

import main as application
from chainecotes.bureau import state


def test_proposition_remplit_les_limites(qtbot):
    state.v.clear()
    state.init()
    f = application.Fenetre()
    qtbot.addWidget(f)
    f.show()
    state.probleme()["condition"]["jmax"] = None
    f.aller("inverse")
    page = f.pages["inverse"][1]
    bouton = next(b for b in page.findChildren(QPushButton) if b.text() == "Proposer un jeu de 0,05 à 0,1 mm")
    bouton.click()
    qtbot.wait(30)
    c = state.probleme()["condition"]
    assert (c["jmin"], c["jmax"]) == (0.05, 0.1)
    page._calculer()
    qtbot.wait(20)
    assert state.v["inv.resultat"]["sortie"]["tenue"]
