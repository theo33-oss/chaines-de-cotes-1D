"""Calculs longs hors du fil de l'interface : la fenêtre reste réactive pendant Monte-Carlo ou un dossier."""

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtGui import QGuiApplication

_enCours: list["_Tache"] = []


class _Signaux(QObject):
    fini = Signal(object)
    echec = Signal(object)


class _Tache(QRunnable):
    def __init__(self, fonction: Callable[[], Any]) -> None:
        super().__init__()
        self.setAutoDelete(False)
        self.fonction = fonction
        self.signaux = _Signaux()

    def run(self) -> None:
        try:
            r = self.fonction()
        except Exception as e:  # noqa: BLE001 : toute erreur est rendue au fil de l'interface
            self.signaux.echec.emit(e)
        else:
            self.signaux.fini.emit(r)


def occupe() -> bool:
    """Vrai si un calcul long tourne déjà."""
    return bool(_enCours)


def lancer(fonction: Callable[[], Any], surFin: Callable[[Any], None], surErreur: Callable[[Exception], None]) -> bool:
    """Exécute fonction() en arrière-plan puis appelle surFin(résultat) ou surErreur(exception) dans l'interface.

    Un seul calcul à la fois : renvoie False sans rien lancer si un autre tourne.
    """
    if _enCours:
        return False
    tache = _Tache(fonction)

    def terminer(rappel: Callable[[Any], None], valeur: Any) -> None:
        _enCours.remove(tache)
        QGuiApplication.restoreOverrideCursor()
        rappel(valeur)

    # l'objet signaux vit dans le fil de l'interface : les rappels y sont exécutés
    tache.signaux.fini.connect(lambda r: terminer(surFin, r), Qt.ConnectionType.QueuedConnection)
    tache.signaux.echec.connect(lambda e: terminer(surErreur, e), Qt.ConnectionType.QueuedConnection)
    _enCours.append(tache)
    QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    QThreadPool.globalInstance().start(tache)
    return True
