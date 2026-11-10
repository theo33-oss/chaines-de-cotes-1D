"""Mode Comparer : par défaut, B est le résultat de la répartition, comparé à l'étude en cours (A)."""

from PySide6.QtWidgets import QLabel

import main as application
from chainecotes.bureau import state, tache


def _fenetre(qtbot):
    state.v.clear()
    state.init()
    f = application.Fenetre()
    qtbot.addWidget(f)
    f.show()
    return f


def _attendre(qtbot):
    qtbot.waitUntil(lambda: not tache.occupe(), timeout=60000)
    qtbot.wait(30)


def test_sans_repartition_un_message_guide_l_utilisateur(qtbot):
    f = _fenetre(qtbot)
    p = f.pages["optimisation"][1]
    f.aller("optimisation")
    p._calculerScenarios()
    affiches = [x.text() for x in p.findChildren(QLabel)]
    assert any("Aucune répartition calculée" in t for t in affiches)  # le message est dessiné puis retiré de l'état
    assert "opt.scen.resultat" not in state.v


def test_compare_l_etude_a_la_repartition(qtbot):
    f = _fenetre(qtbot)
    c = state.probleme()["condition"]
    c["jmin"], c["jmax"] = 0.1, 0.4
    f.aller("inverse")
    f.pages["inverse"][1]._calculer()
    qtbot.wait(20)
    p = f.pages["optimisation"][1]
    f.aller("optimisation")
    p._calculerScenarios()
    _attendre(qtbot)
    cmp = state.v["opt.scen.resultat"]["cmp"]
    assert not cmp["identiques"]  # les IT de la saisie et ceux de la répartition diffèrent
    assert all(m["statut"] == "commun" for m in cmp["maillons"])
