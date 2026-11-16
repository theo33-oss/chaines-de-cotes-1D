"""Application de bureau « Chaînes de cotes 1D » : menu à gauche, une page par outil.

Lancement : python main.py (ou 1_Ouvrir_application.bat sous Windows).
"""

import copy
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import QSettings, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication, QKeySequence
from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: F401 : à importer avant QApplication
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from chainecotes import __version__
from chainecotes.bureau import icones, state, tache, widgets
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
    ("calcul", "Étude", calcul.PageCalcul),
    ("inverse", None, inverse.PageInverse),
    ("optimisation", None, optimisation.PageOptimisation),
    ("mecanisme", "Mécanisme", mecanisme.PageMecanisme),
    ("Outils", None, None),
    ("exemples", "Exemples", exemples.PageExemples),
    ("ajustement", "Ajustements", ajustement.PageAjustement),
    ("iso286", "Tables ISO 286", iso286.PageIso286),
    ("materiaux", "Matériaux", materiaux.PageMateriaux),
    ("Informations", None, None),
    ("apropos", "À propos", apropos.PageAPropos),
)

URL_EN_LIGNE = "https://theo33-oss.github.io/chaines-de-cotes-1D/"  # la version en ligne, toujours à jour
# barre du haut, comme le site (docs/app.js) : Accueil, puis ces familles ; (page, libellé du bouton)
FAMILLES = (
    ("Étude", (("calcul", "Étude"), ("inverse", "Optimiser"), ("optimisation", "Comparer"), ("parcours", "Nouvelle étude (guidé)"))),
    ("Mécanisme", (("mecanisme", "Mécanisme"),)),
    ("Aides", (("assistant", "Assistant de chaîne"), ("exemples", "Exemples"), ("ajustement", "Ajustements"),
               ("iso286", "Tables ISO 286"), ("materiaux", "Matériaux"), ("apropos", "À propos"))),
)  # fmt: skip
PAGE_DE_FAMILLE = {"Étude": "analyser", "Mécanisme": "mecanisme", "Aides": "exemples"}  # tracé de l'icône de chaque famille
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
        self.fichierReprise: Path | None = None  # idem : copie de secours de l'étude modifiée (reprise après un plantage)
        centre = QWidget()
        colonne = QVBoxLayout(centre)
        colonne.setContentsMargins(0, 0, 0, 0)
        colonne.setSpacing(0)
        self.menu = QListWidget()  # modèle des pages, non affiché : l'ordre et la page ouverte (les boutons du haut le pilotent)
        self.menu.setObjectName("menu")
        self.menu.setIconSize(QSize(18, 18))
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
            self.menu.addItem(QListWidgetItem(icones.iconeMenu(ident), libelle))
        colonne.addWidget(self._bandeau())
        colonne.addWidget(self._barre())
        colonne.addWidget(self.pile, 1)
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

    # ---------------------------------------------------------------------------------------------- bandeau et menu

    def _bandeau(self) -> QWidget:
        """Marque, phrase de confiance, thème et bouton vers la version en ligne (comme le haut du site)."""
        bandeau = QWidget()
        bandeau.setObjectName("bandeau")
        h = QHBoxLayout(bandeau)
        h.setContentsMargins(18, 10, 18, 8)
        h.setSpacing(16)
        icone = QLabel()
        icone.setPixmap(icones.iconeApplication(72).pixmap(36, 36))
        marque = QLabel(TITRE)
        marque.setObjectName("marque")
        confiance = QLabel("Calcul de tolérances d'un assemblage. Tout est calculé sur votre ordinateur : "
                           "aucune cote n'est envoyée sur Internet.")  # fmt: skip
        confiance.setObjectName("confiance")
        confiance.setWordWrap(True)
        confiance.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
        self.bouton_theme = QPushButton()
        self.bouton_theme.setObjectName("bouton")
        self.bouton_theme.clicked.connect(self.basculerTheme)
        en_ligne = QPushButton("Version en ligne")
        en_ligne.setObjectName("primaire")
        en_ligne.setToolTip("Ouvre la version dans le navigateur : sans installation, toujours à jour.")
        en_ligne.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(URL_EN_LIGNE)))
        for w in (icone, marque):
            h.addWidget(w)
        h.addWidget(confiance, 1)
        h.addWidget(self.bouton_theme)
        h.addWidget(en_ligne)
        self._texte_theme()
        return bandeau

    def _barre(self) -> QWidget:
        """Barre du haut : Accueil et les familles, puis les pages de la famille choisie."""
        barre = QFrame()
        barre.setObjectName("barreMenu")
        v = QVBoxLayout(barre)
        v.setContentsMargins(18, 4, 18, 6)
        v.setSpacing(2)
        haut = QHBoxLayout()
        haut.setSpacing(6)
        self.famille_de: dict[str, str] = {}
        self.boutons_familles: dict[str | None, QPushButton] = {}
        self.boutons_pages: dict[str, QPushButton] = {}
        self.rang_famille: dict[str, int] = {}
        self.derniere_page: dict[str, str] = {}  # famille → dernière page ouverte (le bouton de la famille y revient)
        accueil = self._bouton_menu("Accueil", "famille", icones.iconeMenu("accueil", self._couleur_icone(), 36),
                                    lambda: self.aller("accueil"))
        self.boutons_familles[None] = accueil
        haut.addWidget(accueil)
        self.sous = QStackedWidget()
        for nom, pages in FAMILLES:
            self.derniere_page[nom] = pages[0][0]
            b = self._bouton_menu(nom, "famille", icones.iconeMenu(PAGE_DE_FAMILLE[nom], self._couleur_icone(), 36),
                                  lambda _=False, n=nom: self.aller(self.derniere_page[n]))
            self.boutons_familles[nom] = b
            haut.addWidget(b)
            rangee = QWidget()
            r = QHBoxLayout(rangee)
            r.setContentsMargins(0, 0, 0, 0)
            r.setSpacing(6)
            for ident, libelle in pages:
                self.famille_de[ident] = nom
                p = self._bouton_menu(libelle, "sousmenu", None, lambda _=False, i=ident: self.aller(i))
                self.boutons_pages[ident] = p
                r.addWidget(p)
            r.addStretch(1)
            self.rang_famille[nom] = self.sous.addWidget(rangee)
        haut.addStretch(1)
        v.addLayout(haut)
        v.addWidget(self.sous)
        return barre

    @staticmethod
    def _couleur_icone() -> str:
        return "#EDE6F7" if state.v.get("sombre") else "#2A1B4A"

    @staticmethod
    def _bouton_menu(texte: str, nom: str, icone, action) -> QPushButton:
        b = QPushButton(texte)
        b.setObjectName(nom)
        b.setCheckable(True)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        if icone is not None:
            b.setIcon(icone)
            b.setIconSize(QSize(18, 18))
        b.clicked.connect(action)
        return b

    def _maj_barre(self, ident: str) -> None:
        """Marque la famille et la page ouvertes ; la rangée des pages n'existe que pour une famille à plusieurs pages."""
        famille = self.famille_de.get(ident)
        if famille is not None:
            self.derniere_page[famille] = ident
        for nom, b in self.boutons_familles.items():
            b.setChecked(nom == famille)
        for i, b in self.boutons_pages.items():
            b.setChecked(i == ident)
        plusieurs = famille is not None and len(dict(FAMILLES)[famille]) > 1
        self.sous.setVisible(plusieurs)
        if plusieurs:
            self.sous.setCurrentIndex(self.rang_famille[famille])

    def _texte_theme(self) -> None:
        self.bouton_theme.setText("Thème clair" if state.v.get("sombre") else "Thème sombre")

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
        affichage = self.menuBar().addMenu("&Affichage")
        self.actionSombre = action(affichage, "Thème &sombre", "Ctrl+T", self.basculerTheme)
        self.actionSombre.setCheckable(True)
        self.actionSombre.setChecked(bool(state.v.get("sombre")))

    def basculerTheme(self, *_: object) -> None:
        """Thème clair ↔ sombre (Ctrl+T) : même choix que la case de l'accueil et que le bouton du site."""
        state.v["sombre"] = not state.v.get("sombre")
        self.actionSombre.setChecked(bool(state.v["sombre"]))
        widgets.appliquerTheme(QApplication.instance())
        self._texte_theme()
        for nom, b in self.boutons_familles.items():
            b.setIcon(icones.iconeMenu(PAGE_DE_FAMILLE.get(nom, "accueil"), self._couleur_icone(), 36))
        self.pile.currentWidget().afficher()

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
            self._garderReprise()
        self.actionAnnuler.setEnabled(bool(self._annulables))
        self.actionRetablir.setEnabled(bool(self._retablissables))
        nom = Path(state.chemin()).name if state.chemin() else "Étude non enregistrée"
        validee = " [validée]" if etatValidation(p) == "valide" else ""
        self.setWindowTitle(f"{nom}[*]{validee} — {TITRE} {__version__}")
        self.setWindowModified(state.modifiee())

    def _garderReprise(self) -> None:
        """Copie de secours de l'étude modifiée : si l'application s'arrête brutalement, elle est reprise au lancement."""
        if self.fichierReprise is None or not state.modifiee():
            return
        try:
            self.fichierReprise.parent.mkdir(parents=True, exist_ok=True)
            ecrireSansPerte(self.fichierReprise, projet_io.exporterProjet(state.probleme(), state.revisions()))
        except (OSError, ErreurChaine):
            pass  # simple confort : sans copie de secours, l'enregistrement normal reste possible

    def _effacerReprise(self) -> None:
        if self.fichierReprise is not None:
            self.fichierReprise.unlink(missing_ok=True)

    def reprendre(self) -> None:
        """Au lancement : reprend l'étude laissée par un arrêt imprévu (elle reste « à enregistrer »)."""
        try:
            ouvert = projet_io.importerProjet(self.fichierReprise.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError, ErreurChaine):
            self._effacerReprise()  # copie illisible : inutile de la proposer à chaque lancement
            return
        state.definirProbleme(ouvert["probleme"])
        state.definirRevisions(ouvert["revisions"])
        state.nouvelleEtude(None, propre=False)
        state.effacerResultat()
        calcul.oublierDossiers()
        self._surveiller()
        self.aller("calcul")
        self.statusBar().showMessage("Étude reprise après une fermeture imprévue : pensez à l'enregistrer.", 15000)

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
        self._effacerReprise()
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
        self._effacerReprise()  # fermeture voulue (enregistrée ou abandonnée) : rien à reprendre
        evenement.accept()

    def _ouvrir(self, ligne: int) -> None:
        """Ligne du menu choisie : sa page, ou le dernier mode ouvert pour la ligne « Étude en cours »."""
        if ligne == self.pages[self._mode][0]:
            page = self.pages[self._mode][1]
        else:
            page = next((p for rang, p in self.pages.values() if rang == ligne), None)
        if page is not None:
            self.pile.setCurrentWidget(page)
            ident = next((i for i, (_, p) in self.pages.items() if p is page), None)
            if ident:
                self._maj_barre(ident)
            page.afficher()

    def aller(self, ident: str) -> None:
        """Ouvre une page par son identifiant ; la rouvre si elle est déjà affichée (son état a pu changer)."""
        rang, page = self.pages[ident]
        if rang == self.pages["calcul"][0]:
            self._mode = ident
        if self.menu.currentRow() == rang:
            self.pile.setCurrentWidget(page)  # même ligne du menu, autre mode de l'étude
            self._maj_barre(ident)
            page.afficher()
        else:
            self.menu.setCurrentRow(rang)


def _signalerErreur(genre: type, erreur: BaseException, trace: object) -> None:
    """Sans console (pythonw), une erreur inattendue serait muette : elle s'affiche à l'écran."""
    detail = "".join(traceback.format_exception(genre, erreur, trace))
    QMessageBox.critical(None, "Erreur de l'application", f"{erreur}\n\n{detail[-1500:]}")


def verifier(app: QApplication, fenetre: "Fenetre", sortie: str) -> int:
    """Auto-vérification (main.py --verifier fichier.txt) : ouvre chaque page, calcule l'étude, fabrique les dossiers.

    Sert à contrôler l'application empaquetée (modules ou données oubliés), en local et sur GitHub. Écrit un rapport
    et rend 0 si tout va bien, 1 sinon.
    """
    from chainecotes.services.dossier_fichier import fichierDossier

    erreurs: list[str] = []
    sys.excepthook = lambda g, e, t: erreurs.append("".join(traceback.format_exception(g, e, t))[-1500:])

    def pause(ms: int) -> None:
        fin: list[int] = []
        QTimer.singleShot(ms, lambda: fin.append(1))
        while not fin:
            app.processEvents()

    lignes = []
    for ident, libelle, _ in MENU:
        if libelle is None and ident not in ("inverse", "optimisation"):
            continue
        avant = len(erreurs)
        try:
            fenetre.aller(ident)
            pause(300)
        except Exception:  # noqa: BLE001 : toute erreur est notée, la vérification continue
            erreurs.append(traceback.format_exc()[-1500:])
        lignes.append(f"page {ident} : {'OK' if len(erreurs) == avant else 'ERREUR'}")
    avant = len(erreurs)
    try:  # le calcul de l'étude ouverte : Monte-Carlo, graphiques, explications
        fenetre.aller("calcul")
        fenetre.calculer()
        while tache.occupe():
            app.processEvents()
        pause(600)
        bundle = state.resultat()
        assert bundle is not None, "aucun résultat après le calcul"
    except Exception:  # noqa: BLE001
        erreurs.append(traceback.format_exc()[-1500:])
        bundle = None
    lignes.append(f"calcul de l'étude : {'OK' if len(erreurs) == avant and bundle else 'ERREUR'}")
    for format_, debut in (("HTML", b"<"), ("PDF", b"%PDF"), ("Word", b"PK")):  # polices, gabarit, reportlab-free fpdf2, docx
        avant = len(erreurs)
        try:
            contenu = fichierDossier(state.probleme(), bundle, format_)["contenu"]
            contenu = contenu.encode("utf-8") if isinstance(contenu, str) else contenu
            assert contenu.lstrip()[: len(debut)] == debut, f"début inattendu : {contenu[:12]!r}"
        except Exception:  # noqa: BLE001
            erreurs.append(traceback.format_exc()[-1500:])
        lignes.append(f"dossier {format_} : {'OK' if len(erreurs) == avant else 'ERREUR'}")
    with open(sortie, "w", encoding="utf-8") as f:
        f.write("\n".join(lignes) + "\n\n" + "\n\n".join(erreurs))
    return 1 if erreurs else 0


def main() -> int:
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    sys.excepthook = _signalerErreur
    state.init()
    reglages = QSettings("ChainesDeCotes1D", "bureau")
    for cle in PREFERENCES:
        state.v[cle] = reglages.value(cle, False, type=bool)
    if not reglages.contains("sombre"):  # première ouverture : le thème de Windows
        state.v["sombre"] = widgets.systemeSombre()
    app.setWindowIcon(icones.iconeApplication())
    valeurs, erreur = procedes_atelier.lireFichier()  # procédés de l'atelier : ceux du dernier enregistrement
    inverse.poserValeursAtelier(valeurs)
    if erreur:
        state.v[inverse.CLE_MESSAGE_ATELIER] = ("avertissement", erreur)
    widgets.appliquerTheme(app)
    fenetre = Fenetre()
    fenetre.reglages = reglages
    fenetre.fichierReprise = procedes_atelier.cheminParDefaut().with_name("derniere_etude.json")
    if reglages.value("geometrie") is not None:
        fenetre.restoreGeometry(reglages.value("geometrie"))
    fenetre.show()
    if "--verifier" in sys.argv:  # auto-vérification de l'exécutable : main.py --verifier rapport.txt
        return verifier(app, fenetre, sys.argv[sys.argv.index("--verifier") + 1])
    if fenetre.fichierReprise.exists():
        fenetre.reprendre()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
