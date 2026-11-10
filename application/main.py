"""Application de bureau « Chaînes de cotes 1D » : menu à gauche, une page par outil.

Lancement : python main.py (ou 1_Ouvrir_application.bat sous Windows).
"""

import copy
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QKeySequence
from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: F401 : à importer avant QApplication
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QWidget,
)

from chainecotes.bureau import state, widgets
from chainecotes.core.donnees import ecrireSansPerte
from chainecotes.core.errors import ErreurChaine
from chainecotes.services import procedes_atelier, projet_io
from chainecotes.services.cartouche import etatValidation
from chainecotes.bureau.pages import (
    accueil,
    ajustement,
    apropos,
    assistant,
    calcul,
    exemples,
    inverse,
    iso286,
    materiaux,
    mecanisme,
    optimisation,
    parcours,
)

MENU = (
    ("accueil", "Accueil", accueil.PageAccueil),
    ("Étude", None, None),
    ("parcours", "Nouvelle étude (guidé)", parcours.PageParcours),
    ("assistant", "Assistant de chaîne", assistant.PageAssistant),
    # une seule entrée pour l'étude : ses trois modes (barre en haut de page) partagent la ligne de « calcul »
    ("calcul", "Étude en cours", calcul.PageCalcul),
    ("inverse", None, inverse.PageInverse),
    ("optimisation", None, optimisation.PageOptimisation),
    ("mecanisme", "Mécanisme (plusieurs chaînes)", mecanisme.PageMecanisme),
    ("Outils", None, None),
    ("exemples", "Bibliothèque d'exemples", exemples.PageExemples),
    ("ajustement", "Assistant d'ajustement", ajustement.PageAjustement),
    ("iso286", "Tables ISO 286", iso286.PageIso286),
    ("materiaux", "Matériaux et dilatation", materiaux.PageMateriaux),
    ("Informations", None, None),
    ("apropos", "À propos", apropos.PageAPropos),
)

TITRE = "Chaînes de cotes 1D"
FILTRE = "Étude (*.json)"
ANNULATIONS_MAX = 50
PREFERENCES = ("sombre", "contraste")  # cases de l'accueil, gardées d'une session à l'autre


def _demander(parent: QWidget) -> str:
    """Étude modifiée sur le point d'être perdue. Sortie : « enregistrer », « abandonner » ou « annuler »."""
    b = QMessageBox(QMessageBox.Icon.Question, TITRE, "L'étude en cours a des modifications non enregistrées.",
                    parent=parent)  # fmt: skip
    b.setInformativeText("Voulez-vous les enregistrer ?")
    oui = b.addButton("Enregistrer", QMessageBox.ButtonRole.AcceptRole)
    non = b.addButton("Ne pas enregistrer", QMessageBox.ButtonRole.DestructiveRole)
    b.setEscapeButton(b.addButton("Annuler", QMessageBox.ButtonRole.RejectRole))
    b.setDefaultButton(oui)
    b.exec()
    return "enregistrer" if b.clickedButton() is oui else "abandonner" if b.clickedButton() is non else "annuler"


def _demanderDeverrouiller(parent: QWidget) -> bool:
    """Étude validée sur le point d'être modifiée. Sortie : True si l'utilisateur repasse l'étude en brouillon."""
    b = QMessageBox(QMessageBox.Icon.Warning, TITRE, "Cette étude est validée : elle ne doit plus être modifiée.",
                    parent=parent)  # fmt: skip
    b.setInformativeText("Repasser son statut en « Brouillon » pour la modifier ? Sinon la modification est annulée.")
    oui = b.addButton("Repasser en brouillon", QMessageBox.ButtonRole.AcceptRole)
    b.setEscapeButton(b.addButton("Garder l'étude validée", QMessageBox.ButtonRole.RejectRole))
    b.setDefaultButton(b.escapeButton())
    b.exec()
    return b.clickedButton() is oui


class Fenetre(QMainWindow):
    """Fenêtre principale : menu et pages empilées, chaque page étant bâtie à sa première ouverture."""

    def __init__(self) -> None:
        super().__init__()
        ecran = QGuiApplication.primaryScreen().availableGeometry()
        self.resize(min(1400, ecran.width() - 40), min(860, ecran.height() - 60))  # au-dessus de la barre des tâches
        self.reglages: QSettings | None = None  # posé par main() : les tests ne touchent pas aux préférences du poste
        centre = QWidget()
        h = QHBoxLayout(centre)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        self.menu = QListWidget()
        self.menu.setObjectName("menu")
        self.menu.setFixedWidth(235)
        self.pile = QStackedWidget()
        self.pages: dict[str, tuple[int, widgets.Page]] = {}
        self._mode = "calcul"  # dernier mode ouvert de l'étude en cours
        for ident, libelle, classe in MENU:
            if classe is None:  # titre de groupe
                it = QListWidgetItem(ident.upper())
                it.setFlags(Qt.ItemFlag.NoItemFlags)
                self.menu.addItem(it)
                continue
            page = classe(self)
            self.pile.addWidget(page)
            if libelle is None:  # mode de l'étude : pas de ligne à lui, celle de « Étude en cours »
                self.pages[ident] = (self.pages["calcul"][0], page)
                continue
            self.pages[ident] = (self.menu.count(), page)
            self.menu.addItem(QListWidgetItem("   " + libelle))
        h.addWidget(self.menu)
        h.addWidget(self.pile, 1)
        self.setCentralWidget(centre)
        self.menu.currentRowChanged.connect(self._ouvrir)
        self._menus()
        self._annulables: list[dict] = []
        self._retablissables: list[dict] = []
        self._etude, self._vu = state.v["etude"], copy.deepcopy(state.probleme())
        # les éditeurs modifient le problème sur place : une veille périodique suit le titre et l'annulation
        self._veille = QTimer(self, interval=400, timeout=self._surveiller)
        self._veille.start()
        self._surveiller()
        self.aller("accueil")

    def _menus(self) -> None:
        def action(menu, texte: str, raccourci: str, fonction):
            a = menu.addAction(texte, fonction)
            a.setShortcut(QKeySequence(raccourci))
            return a

        fichier = self.menuBar().addMenu("&Fichier")
        action(fichier, "&Ouvrir…", "Ctrl+O", self.ouvrir)
        action(fichier, "&Enregistrer", "Ctrl+S", self.enregistrer)
        action(fichier, "Enregistrer &sous…", "Ctrl+Shift+S", self.enregistrerSous)
        fichier.addSeparator()
        action(fichier, "&Quitter", "Ctrl+Q", self.close)
        edition = self.menuBar().addMenu("&Édition")
        self.actionAnnuler = action(edition, "&Annuler", "Ctrl+Z", self.annuler)
        self.actionRetablir = action(edition, "&Rétablir", "Ctrl+Y", self.retablir)
        action(self.menuBar().addMenu("&Calcul"), "&Calculer", "F5", self.calculer)

    def _surveiller(self) -> None:
        """Suit le problème courant : pile d'annulation, titre (fichier, astérisque « modifié »)."""
        p = state.probleme()
        if state.v["etude"] != self._etude:  # autre étude : son historique ne doit pas ramener la précédente
            self._etude, self._vu = state.v["etude"], copy.deepcopy(p)
            self._annulables.clear()
            self._retablissables.clear()
        elif p != self._vu:
            if etatValidation(p) == "modifie" and etatValidation(self._vu) == "valide":
                if _demanderDeverrouiller(self):  # modification acceptée : l'étude n'est plus validée
                    p["cartouche"] = {k: x for k, x in p["cartouche"].items() if k != "empreinte"} | {"statut": "Brouillon"}
                else:  # modification refusée : retour au problème validé
                    state.definirProbleme(copy.deepcopy(self._vu))
                    self.pile.currentWidget().afficher()
                    return
                self.pile.currentWidget().afficher()
            self._annulables.append(self._vu)
            del self._annulables[:-ANNULATIONS_MAX]
            self._retablissables.clear()
            self._vu = copy.deepcopy(p)
        self.actionAnnuler.setEnabled(bool(self._annulables))
        self.actionRetablir.setEnabled(bool(self._retablissables))
        nom = Path(state.chemin()).name if state.chemin() else "Étude non enregistrée"
        validee = " [validée]" if etatValidation(p) == "valide" else ""
        self.setWindowTitle(f"{nom}[*]{validee} — {TITRE}")
        self.setWindowModified(state.modifiee())

    def _revenir(self, source: list[dict], destination: list[dict]) -> None:
        self._surveiller()  # prend en compte une modification toute récente
        if not source:
            return
        destination.append(self._vu)
        self._vu = source.pop()
        state.definirProbleme(copy.deepcopy(self._vu))
        self.pile.currentWidget().afficher()
        self._surveiller()

    def annuler(self) -> None:
        """Revient au problème d'avant la dernière modification (saisie, import, « Appliquer »…)."""
        self._revenir(self._annulables, self._retablissables)

    def retablir(self) -> None:
        self._revenir(self._retablissables, self._annulables)

    def calculer(self) -> None:
        """F5 : lance le calcul de la page affichée si elle en a un, sinon celui de la page Calcul."""
        page = self.pile.currentWidget()
        if not hasattr(page, "_calculer"):
            self.aller("calcul")
            page = self.pages["calcul"][1]
        page._calculer()

    def confirmerAbandon(self) -> bool:
        """Avant de remplacer ou de fermer une étude modifiée. Sortie : True si l'on peut continuer."""
        if not state.modifiee():
            return True
        reponse = _demander(self)
        return self.enregistrer() if reponse == "enregistrer" else reponse == "abandonner"

    def ouvrir(self) -> None:
        chemin, _ = QFileDialog.getOpenFileName(self, "Ouvrir une étude", "", FILTRE)
        if not chemin:
            return
        try:
            ouvert = projet_io.importerProjet(Path(chemin).read_bytes().decode("utf-8-sig"))
        except UnicodeDecodeError:
            QMessageBox.warning(self, "Ouverture impossible", "Fichier non reconnu : ce n'est pas un texte UTF-8.")
            return
        except (OSError, ErreurChaine) as e:
            QMessageBox.warning(self, "Ouverture impossible", str(e))
            return
        if not self.confirmerAbandon():
            return
        state.definirProbleme(ouvert["probleme"])
        state.definirRevisions(ouvert["revisions"])
        state.nouvelleEtude(chemin)
        state.effacerResultat()
        calcul.oublierDossiers()
        self._surveiller()
        self.aller("calcul")

    def enregistrer(self) -> bool:
        """Réécrit le fichier de l'étude, ou demande où l'écrire la première fois. Sortie : True si écrit."""
        return self._ecrire(state.chemin()) if state.chemin() else self.enregistrerSous()

    def enregistrerSous(self) -> bool:
        chemin, _ = QFileDialog.getSaveFileName(
            self, "Enregistrer l'étude", state.chemin() or "chaine_de_cotes.json", FILTRE
        )
        return bool(chemin) and self._ecrire(chemin)

    def _ecrire(self, chemin: str) -> bool:
        try:
            texte = projet_io.exporterProjet(state.probleme(), state.revisions())
            ecrireSansPerte(chemin, texte)
        except (OSError, ErreurChaine) as e:
            QMessageBox.warning(self, "Enregistrement impossible", str(e))
            return False
        state.etudeEnregistree(chemin)
        self.statusBar().showMessage(f"Étude enregistrée : {Path(chemin).name}", 6000)
        self._surveiller()
        return True

    def closeEvent(self, evenement) -> None:
        if not self.confirmerAbandon():
            evenement.ignore()
            return
        if self.reglages is not None:
            self.reglages.setValue("geometrie", self.saveGeometry())
            for cle in PREFERENCES:
                self.reglages.setValue(cle, bool(state.v.get(cle)))
        evenement.accept()

    def _ouvrir(self, ligne: int) -> None:
        """Ligne du menu choisie : sa page, ou le dernier mode ouvert pour la ligne « Étude en cours »."""
        if ligne == self.pages[self._mode][0]:
            page = self.pages[self._mode][1]
        else:
            page = next((p for rang, p in self.pages.values() if rang == ligne), None)
        if page is not None:
            self.pile.setCurrentWidget(page)
            page.afficher()

    def aller(self, ident: str) -> None:
        """Ouvre une page par son identifiant ; la rouvre si elle est déjà affichée (son état a pu changer)."""
        rang, page = self.pages[ident]
        if rang == self.pages["calcul"][0]:
            self._mode = ident
        if self.menu.currentRow() == rang:
            self.pile.setCurrentWidget(page)  # même ligne du menu, autre mode de l'étude
            page.afficher()
        else:
            self.menu.setCurrentRow(rang)


def _signalerErreur(genre: type, erreur: BaseException, trace: object) -> None:
    """Sans console (pythonw), une erreur inattendue serait muette : elle s'affiche à l'écran."""
    detail = "".join(traceback.format_exception(genre, erreur, trace))
    QMessageBox.critical(None, "Erreur de l'application", f"{erreur}\n\n{detail[-1500:]}")


def main() -> int:
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    sys.excepthook = _signalerErreur
    state.init()
    reglages = QSettings("ChainesDeCotes1D", "bureau")
    for cle in PREFERENCES:
        state.v[cle] = reglages.value(cle, False, type=bool)
    valeurs, erreur = procedes_atelier.lireFichier()  # procédés de l'atelier : ceux du dernier enregistrement
    inverse.poserValeursAtelier(valeurs)
    if erreur:
        state.v[inverse.CLE_MESSAGE_ATELIER] = ("avertissement", erreur)
    widgets.appliquerTheme(app)
    fenetre = Fenetre()
    fenetre.reglages = reglages
    if reglages.value("geometrie") is not None:
        fenetre.restoreGeometry(reglages.value("geometrie"))
    fenetre.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
