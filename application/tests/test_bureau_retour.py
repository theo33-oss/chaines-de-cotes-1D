"""Retour visible des actions du bureau : bouton vert avec coche, message flottant (comme sur le site)."""

from PySide6.QtWidgets import QMainWindow, QPushButton

from chainecotes.bureau import widgets


def _fenetre(qtbot):
    f = QMainWindow()
    f.resize(800, 600)
    qtbot.addWidget(f)
    f.show()
    return f


def test_toast_s_affiche_puis_disparait(qtbot):
    f = _fenetre(qtbot)
    widgets.toast(f, "Tableau copié.")
    assert f._toast.isVisible() and f._toast.text() == "Tableau copié." and f._toast.property("niveau") == "succes"
    widgets.toast(f, "Échec", "erreur")  # un seul message, réutilisé
    assert f._toast.property("niveau") == "erreur" and len(f.findChildren(type(f._toast))) == 1
    qtbot.waitUntil(lambda: not f._toast.isVisible(), timeout=6000)


def test_bouton_vert_puis_texte_d_origine(qtbot, monkeypatch):
    monkeypatch.setattr(widgets, "DUREE_RETOUR_MS", 50)
    b = QPushButton("Enregistrer")
    qtbot.addWidget(b)
    widgets.retour(b, True, "Enregistré")
    assert b.text() == "✓ Enregistré" and b.property("retour") == "ok"
    widgets.retour(b, False, "", "Impossible")  # un second retour garde le texte d'origine
    assert b.text() == "✗ Impossible" and b.property("retour") == "ko"
    qtbot.waitUntil(lambda: b.text() == "Enregistrer", timeout=2000)
    assert b.property("retour") is None


def test_confirmer_bouton_et_message(qtbot):
    f = _fenetre(qtbot)
    b = QPushButton("Copier")
    qtbot.addWidget(b)
    widgets.confirmer(f, b, True, "Copié", message="Copié dans le presse-papiers.")
    assert b.property("retour") == "ok" and f._toast.text() == "Copié dans le presse-papiers."
    widgets.confirmer(f, None, False, "", "Copie impossible")
    assert f._toast.property("niveau") == "erreur" and f._toast.text() == "Copie impossible"


def test_la_feuille_de_style_colore_le_retour(qtbot):
    from PySide6.QtWidgets import QApplication

    widgets.appliquerTheme(QApplication.instance())
    css = QApplication.instance().styleSheet()
    assert '#primaire[retour="ok"]' in css and '#toast[niveau="erreur"]' in css
