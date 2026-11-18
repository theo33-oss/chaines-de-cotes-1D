"""« Demander à une IA » : copie la consigne et l'étude complète, puis propose d'ouvrir Claude ou ChatGPT.

Rien n'est envoyé : c'est l'utilisateur qui colle le texte. L'IA présente d'abord le problème (consigne), puis il lui pose
ses questions. Le texte vient de chainecotes.services.export_texte, le même que sur le site.
"""

from PySide6.QtCore import QPoint, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QMenu, QPushButton, QWidget

from chainecotes.bureau.widgets import messageFlottant
from chainecotes.services.export_texte import texteIA

IA = {"Ouvrir Claude": "https://claude.ai/new", "Ouvrir ChatGPT": "https://chatgpt.com/"}


def _montrerMenu(menu: QMenu, position: QPoint) -> None:
    """Affiche le menu (à part pour que les tests ne bloquent pas sur menu.exec)."""
    menu.exec(position)


def demanderAUneIA(fenetre: QWidget, bouton: QPushButton, bundle: dict | None) -> bool:
    """Copie la consigne et l'étude dans le presse-papiers, puis ouvre le menu Claude / ChatGPT sous le bouton.

    Entrées : fenetre (message flottant), bouton (le menu s'ouvre dessous), bundle (dernier calcul ; None si l'étude
    n'est pas calculée : un message l'explique). Sortie : True si le texte est copié.
    """
    if bundle is None:
        messageFlottant(fenetre, "Calculez d'abord l'étude (F5) : l'IA a besoin des résultats.", "erreur")
        return False
    QApplication.clipboard().setText(texteIA(bundle))
    messageFlottant(fenetre, "Étude copiée : collez-la dans l'IA (Ctrl+V).")
    menu = QMenu(bouton)
    info = menu.addAction("Étude copiée : collez-la (Ctrl+V) dans l'IA")
    info.setEnabled(False)
    menu.addSeparator()
    for libelle, adresse in IA.items():
        menu.addAction(libelle, lambda a=adresse: QDesktopServices.openUrl(QUrl(a)))
    _montrerMenu(menu, bouton.mapToGlobal(QPoint(0, bouton.height())))
    return True
