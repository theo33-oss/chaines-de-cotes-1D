"""Briques d'interface : page, section reconstruite à la demande, zone d'affichage et champs liés à state.v.

Une Section redessine son contenu avec une fonction `rendu(zone)`. Les champs gardent leur valeur dans state.v sous
leur clé : une section reconstruite les retrouve, comme une page rouverte.
"""

import atexit
import math
import shutil
import tempfile
import uuid
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pandas as pd
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QColor
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSplitter,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from chainecotes.bureau import state
from chainecotes.core.donnees import ecrireSansPerte
from chainecotes.core.errors import ErreurChaine
from chainecotes.core.formules import texVersHtml
from chainecotes.plots._common import FOND_FIGURE, TEXTE

_DOSSIER_FIGURES = Path(tempfile.mkdtemp(prefix="chaines_cotes_"))
atexit.register(shutil.rmtree, _DOSSIER_FIGURES, ignore_errors=True)  # sinon ~5 Mo restent dans %TEMP% à chaque lancement
HAUTEUR_TABLEAU_MAX = 420
COULEURS_MESSAGE = {
    "info": ("#E4E0F3", "#3D246C"),
    "succes": ("#C8F0D2", "#0B3D1A"),
    "avertissement": ("#FFE2A8", "#5A3A00"),
    "erreur": ("#FFC2C2", "#6B0A12"),
}
MODES_ETUDE = (("calcul", "Analyser"), ("inverse", "Répartir les tolérances"), ("optimisation", "Comparer"))
_NEUTRE = ("#DDDDDD", "#222222")
# vert, orange, rouge : réservés au statut ; le verdict reste écrit en toutes lettres (jamais la couleur seule)
COULEURS_VERDICT = {
    "Conforme": COULEURS_MESSAGE["succes"],
    "conforme au pire des cas": COULEURS_MESSAGE["succes"],
    "conforme en statistique seulement": COULEURS_MESSAGE["avertissement"],
    "Non conforme": COULEURS_MESSAGE["erreur"],
    "non conforme": COULEURS_MESSAGE["erreur"],
    "Sans limite": _NEUTRE,
    "erreur de calcul": _NEUTRE,
}


def differer(fonction: Callable[[], None]) -> None:
    """Exécute fonction après le signal en cours : elle peut alors détruire le champ qui l'a appelée."""
    QTimer.singleShot(0, fonction)


def vider(disposition: Any) -> None:
    """Retire et détruit tout le contenu d'une disposition."""
    while disposition.count():
        element = disposition.takeAt(0)
        if (w := element.widget()) is not None:
            w.hide()
            w.setParent(None)
            w.deleteLater()
        elif element.layout() is not None:
            vider(element.layout())


def contrasteEleve() -> bool:
    """Vrai si « Contraste élevé » est choisi pour les graphiques."""
    return bool(state.v.get("contraste"))


def _renforce(fig: Any) -> None:
    """Contraste élevé : traits épaissis, aires colorées plus opaques, quadrillage et textes plus marqués."""
    for t in fig.data:
        ligne = getattr(t, "line", None)
        if ligne is not None and getattr(ligne, "width", None):  # largeur 0 (bord d'une aire) : inchangée
            ligne.width = max(2.5, ligne.width * 1.8)
        fond = getattr(t, "fillcolor", None)
        if isinstance(fond, str) and fond.startswith("rgba("):
            *rvb, alpha = fond[5:-1].split(",")
            t.fillcolor = f"rgba({','.join(rvb)},{min(1.0, 2 * float(alpha)):g})"
    fig.update_layout(font_size=15)
    for a in fig.layout.annotations:
        if a.font.size is not None and a.font.size < 12:
            a.font.size = 12
    fig.update_xaxes(gridcolor="#8E86AA", linecolor=TEXTE, zerolinecolor=TEXTE, tickfont_size=14)
    fig.update_yaxes(gridcolor="#8E86AA", linecolor=TEXTE, zerolinecolor=TEXTE, tickfont_size=14)


class VueFigure(QWebEngineView):
    """Figure Plotly interactive, sans Internet : plotly.min.js est écrit une fois dans le dossier temporaire."""

    def __init__(self, fig: Any) -> None:
        super().__init__()
        fig.update_layout(paper_bgcolor=FOND_FIGURE, plot_bgcolor=FOND_FIGURE)
        if contrasteEleve():
            _renforce(fig)
        hauteur = int(fig.layout.height or 450)
        chemin = _DOSSIER_FIGURES / f"{uuid.uuid4().hex}.html"
        fig.write_html(
            chemin,
            include_plotlyjs="directory",
            full_html=True,
            default_width="100%",
            default_height=f"{hauteur}px",
            config={"displaylogo": False, "scrollZoom": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]},
        )
        html = chemin.read_text(encoding="utf-8").replace("<body>", '<body style="margin:0;overflow:hidden">', 1)
        chemin.write_text(html, encoding="utf-8")
        self.setFixedHeight(hauteur + 2)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.load(QUrl.fromLocalFile(str(chemin)))


def _ecrit(v: Any, fmt: str | None) -> str:
    """Case de tableau en texte : nombres à la française, vide pour une valeur absente."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return ""
    if isinstance(v, bool):
        return "oui" if v else "non"
    if fmt and isinstance(v, int | float):
        return (fmt % v).replace(".", ",")
    if isinstance(v, float):
        return f"{v:g}".replace(".", ",")
    return str(v)


def ajusterHauteur(table: QTableWidget) -> None:
    """Hauteur du tableau selon ses lignes (bornée : un long tableau défile sur place)."""
    h = table.horizontalHeader().height() + 2 * table.frameWidth() + 18
    h += sum(table.rowHeight(i) for i in range(table.rowCount()))
    table.setFixedHeight(min(h, HAUTEUR_TABLEAU_MAX))
    # le tableau défile sur place : sa largeur ne doit pas élargir le panneau
    table.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
    table.setMinimumWidth(120)


class TableauDonnees(QTableWidget):
    """DataFrame en lecture seule. formats : {colonne: « %.4f »} ; couleurs : {colonne: valeur → (fond, texte)}."""

    def __init__(self, df: pd.DataFrame, formats: dict | None = None, couleurs: dict | None = None,
                 index: bool = False) -> None:  # fmt: skip
        super().__init__(len(df), len(df.columns))
        formats, couleurs = formats or {}, couleurs or {}
        self.setHorizontalHeaderLabels([str(c) for c in df.columns])
        if index:
            self.setVerticalHeaderLabels([str(i) for i in df.index])
        else:
            self.verticalHeader().hide()
        for j, col in enumerate(df.columns):
            for i, v in enumerate(df[col].tolist()):
                item = QTableWidgetItem(_ecrit(v, formats.get(col)))
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                if isinstance(v, int | float) and not isinstance(v, bool):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if col in couleurs and (c := couleurs[col](v)):
                    item.setBackground(QColor(c[0]))
                    item.setForeground(QColor(c[1]))
                self.setItem(i, j, item)
        self.setWordWrap(False)
        self.resizeColumnsToContents()
        for j in range(self.columnCount()):
            self.setColumnWidth(j, min(self.columnWidth(j), 340))
        self.horizontalHeader().setStretchLastSection(True)
        ajusterHauteur(self)


class Colonne:
    """Colonne d'un TableauEditable : cle, titre, genre (« texte », « nombre », « liste »), options, fmt, aide."""

    def __init__(self, cle: str, titre: str, genre: str = "texte", options: Sequence[str] = (), fmt: str = "%g",
                 aide: str = "", libre: bool = False, mini: float | None = None) -> None:  # fmt: skip
        self.cle, self.titre, self.genre, self.options = cle, titre, genre, list(options)
        self.fmt, self.aide, self.libre, self.mini = fmt, aide, libre, mini


class _DelegueListe(QStyledItemDelegate):
    """Éditeur des colonnes à liste : QComboBox ; `libre` laisse taper une autre valeur (désignation ISO)."""

    def __init__(self, table: "TableauEditable") -> None:
        super().__init__(table)
        self.table = table

    def createEditor(self, parent: QWidget, option: Any, index: Any) -> QWidget:  # noqa: N802 : nom imposé par Qt
        col = self.table.colonnes[index.column()]
        if col.genre != "liste":
            return super().createEditor(parent, option, index)
        boite = QComboBox(parent)
        boite.setEditable(col.libre)
        boite.addItems(["", *col.options])
        boite.activated.connect(lambda: self.commitData.emit(boite))
        return boite

    def setEditorData(self, editeur: QWidget, index: Any) -> None:  # noqa: N802 : nom imposé par Qt
        if isinstance(editeur, QComboBox):
            editeur.setCurrentText(index.data() or "")
        else:
            super().setEditorData(editeur, index)

    def setModelData(self, editeur: QWidget, modele: Any, index: Any) -> None:  # noqa: N802 : nom imposé par Qt
        if isinstance(editeur, QComboBox):
            modele.setData(index, editeur.currentText())
        else:
            super().setModelData(editeur, modele, index)


def lireNombre(texte: str) -> float | None:
    """Nombre tapé avec un point ou une virgule ; None si le texte est vide ; ValueError s'il est illisible."""
    t = texte.strip().replace(",", ".").replace(" ", "").replace("−", "-")
    return None if not t else float(t)


class TableauEditable(QTableWidget):
    """Tableau de saisie. surChange(ligne, clé, valeur) reçoit chaque case validée (nombre, texte ou None)."""

    def __init__(self, colonnes: list[Colonne], surChange: Callable[[int, str, Any], None],
                 surSelection: Callable[[int], None] | None = None) -> None:  # fmt: skip
        super().__init__(0, len(colonnes))
        self.colonnes, self.surChange, self.surSelection = colonnes, surChange, surSelection
        self.lignes: list[dict] = []
        self.setHorizontalHeaderLabels([c.titre for c in colonnes])
        for j, c in enumerate(colonnes):
            self.horizontalHeaderItem(j).setToolTip(c.aide)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.setItemDelegate(_DelegueListe(self))
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed
            | QAbstractItemView.EditTrigger.SelectedClicked
        )
        self.itemChanged.connect(self._change)
        self.currentCellChanged.connect(self._selection)

    def _texte(self, c: Colonne, v: Any) -> str:
        if v is None or v == "" or (isinstance(v, float) and math.isnan(v)):
            return ""
        return _ecrit(float(v), c.fmt) if c.genre == "nombre" else str(v)

    def charger(self, lignes: list[dict]) -> None:
        """Affiche des lignes (dict par colonne) sans déclencher surChange ; la cellule courante reste en place."""
        self.blockSignals(True)
        self.lignes = lignes
        self.setRowCount(len(lignes))
        for i, ligne in enumerate(lignes):
            for j, c in enumerate(self.colonnes):
                item = self.item(i, j) or QTableWidgetItem()
                item.setText(self._texte(c, ligne.get(c.cle)))
                if c.genre == "nombre":
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.setItem(i, j, item)
        self.blockSignals(False)
        self.resizeColumnsToContents()
        ajusterHauteur(self)

    def _change(self, item: QTableWidgetItem) -> None:
        i, c = item.row(), self.colonnes[item.column()]
        texte = item.text().strip()
        if c.genre == "nombre":
            try:
                valeur = lireNombre(texte)
                if valeur is not None and (not math.isfinite(valeur) or (c.mini is not None and valeur < c.mini)):
                    raise ValueError
            except ValueError:  # saisie illisible : la case reprend sa valeur
                self.blockSignals(True)
                item.setText(self._texte(c, self.lignes[i].get(c.cle)))
                self.blockSignals(False)
                return
        else:
            valeur = texte or None
        differer(lambda: self.surChange(i, c.cle, valeur))

    def _selection(self, ligne: int, _colonne: int, avant: int, _colonneAvant: int) -> None:
        if self.surSelection and ligne >= 0 and ligne != avant:
            differer(lambda: self.surSelection(ligne))


class ChampNombre(QLineEdit):
    """Nombre tapé au clavier (point ou virgule) ; peut rester vide si `vide` ; borné par mini et maxi."""

    def __init__(self, valeur: float | None, decimales: int, mini: float | None, maxi: float | None, vide: bool,
                 surValide: Callable[[float | None], None]) -> None:  # fmt: skip
        super().__init__()
        self.decimales, self.mini, self.maxi, self.vide, self.surValide = decimales, mini, maxi, vide, surValide
        self.valeur = valeur
        self._ecrire()
        self.editingFinished.connect(self._valider)

    def _ecrire(self) -> None:
        if self.valeur is None:
            self.setText("")
        elif self.decimales == 0:
            self.setText(f"{self.valeur:.0f}")
        else:
            self.setText(f"{self.valeur:.{self.decimales}f}".replace(".", ","))

    def _valider(self) -> None:
        try:
            v = lireNombre(self.text())
            if v is None and not self.vide:
                raise ValueError
            if v is not None and not math.isfinite(v):
                raise ValueError
        except ValueError:
            self._ecrire()
            return
        if v is not None:
            v = v if self.mini is None else max(v, self.mini)
            v = v if self.maxi is None else min(v, self.maxi)
            v = int(round(v)) if self.decimales == 0 else v
        change = v != self.valeur
        self.valeur = v
        self._ecrire()
        if change:
            self.surValide(v)


class Zone:
    """Emplacement où écrire : mêmes gestes partout (titre, texte, tableau, figure, champs, boutons)."""

    def __init__(self, page: "Page", disposition: Any, section: "Section | None" = None) -> None:
        self.page, self.d, self.section_ = page, disposition, section

    def _ajouter(self, w: QWidget) -> QWidget:
        self.d.addWidget(w)
        return w

    def _libelle(self, texte: str, nom: str, md: bool = False) -> QLabel:
        lab = QLabel(texte)
        lab.setObjectName(nom)
        lab.setWordWrap(True)
        lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lab.setTextFormat(Qt.TextFormat.MarkdownText if md else Qt.TextFormat.PlainText)
        return self._ajouter(lab)

    def titre(self, texte: str) -> None:
        self._libelle(texte, "titre")

    def sousTitre(self, texte: str) -> None:
        self._libelle(texte, "sousTitre")

    def texte(self, md: str) -> None:
        """Texte en Markdown (gras, listes)."""
        self._libelle(md, "texte", md=True)

    def legende(self, texte: str) -> None:
        self._libelle(texte, "legende")

    def message(self, niveau: str, texte: str) -> None:
        """Bandeau coloré : niveau « info », « succes », « avertissement » ou « erreur »."""
        lab = self._libelle(texte, "message", md=True)
        fond, encre = COULEURS_MESSAGE[niveau]
        lab.setStyleSheet(f"background:{fond};color:{encre};padding:8px;border-radius:5px;")

    def info(self, texte: str) -> None:
        self.message("info", texte)

    def succes(self, texte: str) -> None:
        self.message("succes", texte)

    def avertissement(self, texte: str) -> None:
        self.message("avertissement", texte)

    def erreur(self, texte: str) -> None:
        self.message("erreur", texte)

    def messageGarde(self, cle: str) -> None:
        """Affiche puis oublie le message (niveau, texte) gardé sous cle."""
        m = state.v.pop(cle, None)
        if m:
            self.message(m[0], m[1])

    def metrique(self, libelle: str, valeur: str, aide: str | None = None) -> None:
        cadre = QFrame()
        cadre.setObjectName("metrique")
        cadre.setToolTip(aide or "")
        col = QVBoxLayout(cadre)
        col.setContentsMargins(8, 4, 8, 4)
        col.setSpacing(0)
        haut, bas = QLabel(libelle), QLabel(valeur)
        haut.setObjectName("metriqueLibelle")
        haut.setWordWrap(True)
        bas.setObjectName("metriqueValeur")
        bas.setWordWrap(True)
        bas.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        col.addWidget(haut)
        col.addWidget(bas)
        if valeur in COULEURS_VERDICT:  # une valeur qui est un verdict porte sa couleur de statut
            fond, encre = COULEURS_VERDICT[valeur]
            cadre.setStyleSheet(f"#metrique {{ background:{fond}; }} #metrique QLabel {{ color:{encre}; }}")
        self._ajouter(cadre)

    def metriques(self, valeurs: Sequence[tuple], parLigne: int = 4) -> None:
        """Ligne(s) de valeurs clés : tuples (libellé, valeur) ou (libellé, valeur, aide)."""
        for debut in range(0, len(valeurs), parLigne):
            cols = self.colonnes(parLigne)
            for col, v in zip(cols, valeurs[debut : debut + parLigne], strict=False):
                col.metrique(*v)

    def tableau(self, df: pd.DataFrame, formats: dict | None = None, couleurs: dict | None = None,
                index: bool = False) -> None:  # fmt: skip
        self._ajouter(TableauDonnees(df, formats, couleurs, index))

    def figure(self, fig: Any, legende: str | None = None) -> None:
        self._ajouter(VueFigure(fig))
        if legende:
            self.legende(legende)

    def formule(self, tex: str) -> None:
        """Formule en vrais caractères (indices, exposants, fractions en petit tableau) : texte, sans image."""
        lab = QLabel(texVersHtml(tex))
        lab.setTextFormat(Qt.TextFormat.RichText)
        lab.setWordWrap(True)
        lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lab.setStyleSheet(f"background:{FOND_FIGURE};padding:6px;")
        self._ajouter(lab)

    def colonnes(self, poids: int | Sequence[int]) -> list["Zone"]:
        """Colonnes côte à côte (nombre, ou poids relatifs)."""
        poids = [1] * poids if isinstance(poids, int) else list(poids)
        ligne = QWidget()
        h = QHBoxLayout(ligne)
        h.setContentsMargins(0, 0, 0, 0)
        zones = []
        for p in poids:
            w = QWidget()
            v = QVBoxLayout(w)
            v.setContentsMargins(0, 0, 0, 0)
            v.setAlignment(Qt.AlignmentFlag.AlignTop)
            h.addWidget(w, p)
            zones.append(Zone(self.page, v, self.section_))
        self._ajouter(ligne)
        return zones

    def cadre(self) -> "Zone":
        """Encadré : contenu groupé d'une carte."""
        w = QFrame()
        w.setObjectName("cadre")
        v = QVBoxLayout(w)
        self._ajouter(w)
        return Zone(self.page, v, self.section_)

    def repliable(self, titre: str, ouvert: bool = False, rendu: Callable[["Zone"], None] | None = None) -> "Zone":
        """Bloc repliable ; son état survit aux reconstructions. Avec `rendu`, le contenu n'est bâti qu'à l'ouverture."""
        cle = f"repli.{titre}"
        ouvert = bool(state.v.get(cle, ouvert))
        tete = QToolButton()
        tete.setObjectName("repli")
        tete.setText(titre)
        tete.setCheckable(True)
        tete.setChecked(ouvert)
        tete.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        tete.setArrowType(Qt.ArrowType.DownArrow if ouvert else Qt.ArrowType.RightArrow)
        tete.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        corps = QWidget()
        v = QVBoxLayout(corps)
        v.setContentsMargins(12, 2, 0, 6)
        zone = Zone(self.page, v, self.section_)
        corps.setVisible(ouvert)
        bati = {"fait": rendu is None}

        def basculer(actif: bool) -> None:
            state.v[cle] = actif
            tete.setArrowType(Qt.ArrowType.DownArrow if actif else Qt.ArrowType.RightArrow)
            if actif and not bati["fait"]:
                bati["fait"] = True
                rendu(zone)
            corps.setVisible(actif)

        tete.toggled.connect(basculer)
        self._ajouter(tete)
        self._ajouter(corps)
        if ouvert and not bati["fait"]:
            bati["fait"] = True
            rendu(zone)
        return zone

    def onglets(self, rendus: dict[str, Callable[["Zone"], None]], cle: str | None = None) -> None:
        """Onglets : le contenu d'un onglet n'est bâti qu'à sa première ouverture (figures coûteuses)."""
        tabs = QTabWidget()
        zones: list[Zone] = []
        for nom in rendus:
            w = QWidget()
            v = QVBoxLayout(w)
            v.setAlignment(Qt.AlignmentFlag.AlignTop)
            tabs.addTab(_defilable(w), nom)
            zones.append(Zone(self.page, v, self.section_))
        noms, faits = list(rendus), set()

        def ouvrir(i: int) -> None:
            if cle:
                state.v[cle] = noms[i]
            if i not in faits:
                faits.add(i)
                rendus[noms[i]](zones[i])

        tabs.setMinimumHeight(620)
        depart = noms.index(state.v[cle]) if cle and state.v.get(cle) in noms else 0
        tabs.setCurrentIndex(depart)
        ouvrir(depart)
        tabs.currentChanged.connect(ouvrir)
        self._ajouter(tabs)

    def section(self, rendu: Callable[["Zone"], None]) -> "Section":
        s = Section(self.page, rendu)
        self._ajouter(s)
        s.rafraichir()
        return s

    def bouton(self, texte: str, action: Callable[[], None], primaire: bool = False, actif: bool = True,
               aide: str | None = None) -> QPushButton:  # fmt: skip
        b = QPushButton(texte)
        b.setObjectName("primaire" if primaire else "bouton")
        b.setEnabled(actif)
        b.setToolTip(aide or "")
        b.clicked.connect(lambda: differer(action))
        self._ajouter(b)
        return b

    def modes(self, actuel: str) -> None:
        """Barre des trois modes de l'étude en cours ; le mode affiché est mis en avant."""
        for col, (ident, libelle) in zip(self.colonnes(len(MODES_ETUDE)), MODES_ETUDE, strict=True):
            col.bouton(libelle, lambda i=ident: self.page.aller(i), primaire=ident == actuel)

    def lien(self, page: str, texte: str) -> None:
        """Lien vers une autre page de l'application."""
        b = QPushButton(texte)
        b.setObjectName("lien")
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(lambda: differer(lambda: self.page.aller(page)))
        self._ajouter(b)

    def telecharger(self, libelle: str, donnees: bytes | str | Callable[[], bytes | str], nomFichier: str) -> None:
        """Bouton d'enregistrement : demande où écrire le fichier ; donnees peut être une fonction (bâti au clic)."""

        def ecrire() -> None:
            chemin, _ = QFileDialog.getSaveFileName(self.page, "Enregistrer", nomFichier)
            if not chemin:
                return
            try:
                contenu = donnees() if callable(donnees) else donnees
            except ErreurChaine as e:  # saisie invalide : message à l'écran plutôt qu'une erreur de l'application
                QMessageBox.warning(self.page, "Enregistrement impossible", e.message)
                return
            try:
                ecrireSansPerte(chemin, contenu)
            except OSError as e:
                QMessageBox.warning(self.page, "Enregistrement impossible", str(e))
            else:
                self.page.fenetre.statusBar().showMessage(f"Fichier enregistré : {Path(chemin).name}", 6000)

        self.bouton(libelle, ecrire)

    def ouvrirFichier(self, libelle: str, filtre: str, action: Callable[[list[tuple[str, bytes]]], None],
                      multiple: bool = False, aide: str | None = None) -> None:  # fmt: skip
        """Bouton d'ouverture : action reçoit la liste des (nom, octets) des fichiers choisis."""

        def ouvrir() -> None:
            if multiple:
                chemins, _ = QFileDialog.getOpenFileNames(self.page, libelle, "", filtre)
            else:
                chemin, _ = QFileDialog.getOpenFileName(self.page, libelle, "", filtre)
                chemins = [chemin] if chemin else []
            if chemins:
                state.v["fichier.chemin"] = chemins[0]  # lu par les pages qui ouvrent une étude (Ctrl+S y réécrit)
                action([(Path(c).name, Path(c).read_bytes()) for c in chemins])

        self.bouton(libelle, ouvrir, aide=aide)

    def _etiquette(self, libelle: str, w: QWidget, aide: str | None) -> QWidget:
        w.setToolTip(aide or "")
        if libelle:
            lab = QLabel(libelle)
            lab.setObjectName("etiquette")
            lab.setWordWrap(True)
            lab.setToolTip(aide or "")
            self._ajouter(lab)
        return self._ajouter(w)

    def _rappel(self, cle: str, valeur: Any, apres: Callable[[], None] | None) -> None:
        state.v[cle] = valeur
        if apres:
            differer(apres)

    def liste(self, libelle: str, options: Sequence, cle: str, format: Callable[[Any], str] = str, defaut: Any = None,
              apres: Callable[[], None] | None = None, aide: str | None = None, actif: bool = True) -> Any:  # fmt: skip
        """Liste déroulante ; renvoie la valeur choisie (celle gardée, sinon `defaut`, sinon la première)."""
        options = list(options)
        v = state.v.get(cle, defaut)
        v = v if v in options else (defaut if defaut in options else options[0] if options else None)
        state.v[cle] = v
        boite = QComboBox()
        # un libellé long ne doit pas élargir le panneau : la liste se replie, le menu déroulant garde le texte entier
        boite.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        boite.setMinimumContentsLength(8)
        boite.addItems([format(o) for o in options])
        boite.setEnabled(actif)
        if v in options:
            boite.setCurrentIndex(options.index(v))
        boite.activated.connect(lambda i: self._rappel(cle, options[i], apres))
        boite.wheelEvent = lambda e: e.ignore()  # la molette fait défiler la page, pas la liste
        self._etiquette(libelle, boite, aide)
        return v

    def radio(self, libelle: str, options: Sequence, cle: str, format: Callable[[Any], str] = str, defaut: Any = None,
              apres: Callable[[], None] | None = None, aide: str | None = None, vertical: bool = False) -> Any:  # fmt: skip
        """Boutons radio ; renvoie la valeur choisie."""
        options = list(options)
        v = state.v.get(cle, defaut)
        v = v if v in options else options[0]
        state.v[cle] = v
        groupe = QWidget()
        d = QVBoxLayout(groupe) if vertical else QHBoxLayout(groupe)
        d.setContentsMargins(0, 0, 0, 0)
        boutons = QButtonGroup(groupe)
        for i, o in enumerate(options):
            b = QRadioButton(format(o))
            b.setChecked(o == v)
            boutons.addButton(b, i)
            d.addWidget(b)
        if not vertical:
            d.addStretch(1)
        boutons.idClicked.connect(lambda i: self._rappel(cle, options[i], apres))
        self._etiquette(libelle, groupe, aide)
        return v

    def multi(self, libelle: str, options: Sequence, cle: str, format: Callable[[Any], str] = str,
              apres: Callable[[], None] | None = None, aide: str | None = None) -> list:  # fmt: skip
        """Choix multiple par cases à cocher ; renvoie la liste choisie, dans l'ordre des options."""
        options = list(options)
        choisis = [o for o in options if o in state.v.get(cle, [])]
        state.v[cle] = choisis
        boite = QListWidget()
        for o in options:
            it = QListWidgetItem(format(o))
            it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if o in choisis else Qt.CheckState.Unchecked)
            boite.addItem(it)
        boite.setFixedHeight(min(150, 8 + 22 * len(options)))

        def change() -> None:
            coches = [o for i, o in enumerate(options) if boite.item(i).checkState() == Qt.CheckState.Checked]
            if coches != state.v.get(cle):
                self._rappel(cle, coches, apres)

        boite.itemChanged.connect(lambda _it: change())
        self._etiquette(libelle, boite, aide)
        return choisis

    def nombre(self, libelle: str, cle: str, defaut: float | None = 0.0, mini: float | None = None,
               maxi: float | None = None, decimales: int = 3, vide: bool = False,
               apres: Callable[[], None] | None = None, aide: str | None = None, actif: bool = True) -> Any:  # fmt: skip
        """Champ numérique ; decimales = 0 : entier ; vide = True : peut rester sans valeur (None)."""
        v = state.v.get(cle, defaut)
        state.v[cle] = v
        champ = ChampNombre(v, decimales, mini, maxi, vide, lambda x: self._rappel(cle, x, apres))
        champ.setEnabled(actif)
        self._etiquette(libelle, champ, aide)
        return v

    def saisie(self, libelle: str, cle: str, defaut: str = "", apres: Callable[[], None] | None = None,
               aide: str | None = None, indice: str = "", longueur: int | None = None) -> str:  # fmt: skip
        """Champ de texte ; le texte est pris en compte à la sortie du champ (ou Entrée)."""
        v = state.v.get(cle, defaut)
        state.v[cle] = v
        champ = QLineEdit(v)
        champ.setPlaceholderText(indice)
        if longueur:
            champ.setMaxLength(longueur)

        def valider() -> None:
            if champ.text() != state.v.get(cle):
                self._rappel(cle, champ.text(), apres)

        champ.editingFinished.connect(valider)
        self._etiquette(libelle, champ, aide)
        return v

    def zoneTexte(self, libelle: str, cle: str) -> None:
        """Texte sur plusieurs lignes, lu dans state.v[cle] à chaque frappe."""
        champ = QPlainTextEdit(state.v.get(cle, ""))
        champ.setFixedHeight(110)
        champ.textChanged.connect(lambda: state.v.__setitem__(cle, champ.toPlainText()))
        self._etiquette(libelle, champ, None)

    def case(self, libelle: str, cle: str, defaut: bool = False, apres: Callable[[], None] | None = None,
             aide: str | None = None) -> bool:  # fmt: skip
        v = bool(state.v.get(cle, defaut))
        state.v[cle] = v
        c = QCheckBox(libelle)
        c.setChecked(v)
        c.setToolTip(aide or "")
        c.toggled.connect(lambda x: self._rappel(cle, x, apres))
        self._ajouter(c)
        return v

    def curseur(self, libelle: str, cle: str, defaut: float, mini: float, maxi: float, pas: float, fmt: str = "%g",
                continu: Callable[[], None] | None = None, apres: Callable[[], None] | None = None,
                aide: str | None = None) -> float:  # fmt: skip
        """Curseur ; `continu` est appelé pendant le glissement, `apres` au relâchement."""
        v = float(state.v.get(cle, defaut))
        state.v[cle] = v
        c = QSlider(Qt.Orientation.Horizontal)
        c.setRange(0, round((maxi - mini) / pas))
        c.setValue(round((v - mini) / pas))
        tete = QLabel(f"{libelle} : {(fmt % v).replace('.', ',')}")
        tete.setObjectName("etiquette")
        tete.setToolTip(aide or "")
        c.setToolTip(aide or "")
        c.wheelEvent = lambda e: e.ignore()

        def bouge(i: int) -> None:
            x = mini + i * pas
            state.v[cle] = x
            tete.setText(f"{libelle} : {(fmt % x).replace('.', ',')}")
            if continu:
                differer(continu)

        c.valueChanged.connect(bouge)
        if apres:
            c.sliderReleased.connect(lambda: differer(apres))
        self._ajouter(tete)
        self._ajouter(c)
        return v


class Section(QWidget):
    """Partie de page redessinée d'un bloc par sa fonction de rendu."""

    def __init__(self, page: "Page", rendu: Callable[[Zone], None]) -> None:
        super().__init__()
        self.page, self.rendu = page, rendu
        self.disposition = QVBoxLayout(self)
        self.disposition.setContentsMargins(0, 0, 0, 0)
        self.disposition.setAlignment(Qt.AlignmentFlag.AlignTop)

    def rafraichir(self) -> None:
        self.setUpdatesEnabled(False)
        vider(self.disposition)
        self.rendu(Zone(self.page, self.disposition, self))
        self.setUpdatesEnabled(True)


def _defilable(contenu: QWidget) -> QScrollArea:
    a = QScrollArea()
    a.setWidgetResizable(True)
    a.setFrameShape(QFrame.Shape.NoFrame)
    a.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)  # jamais de contenu coupé
    a.setWidget(contenu)
    return a


class Page(QWidget):
    """Page de la fenêtre. Une page simple redéfinit rendre(zone) ; une page à deux panneaux, construire()."""

    def __init__(self, fenetre: Any) -> None:
        super().__init__()
        self.fenetre = fenetre
        self.d = QVBoxLayout(self)
        self.d.setContentsMargins(16, 10, 8, 8)
        self.sections: list[Section] = []
        self.bati = False

    def aller(self, page: str) -> None:
        self.fenetre.aller(page)

    def afficher(self) -> None:
        """Appelée à chaque ouverture de la page : tout repart de l'état courant."""
        if not self.bati:
            self.bati = True
            self.construire()
        for s in self.sections:
            s.rafraichir()

    def construire(self) -> None:
        s = Section(self, self.rendre)
        self.sections.append(s)
        self.d.addWidget(_defilable(s))

    def rendre(self, z: Zone) -> None:
        raise NotImplementedError

    def deuxPanneaux(self, tete: Callable[[Zone], None], gauche: Callable[[Zone], None],
                     droite: Callable[[Zone], None]) -> tuple[Section, Section]:  # fmt: skip
        """En-tête puis saisie à gauche et visualisation à droite, chacune défilant seule."""
        haut = Section(self, tete)
        sg, sd = Section(self, gauche), Section(self, droite)
        self.sections += [haut, sg, sd]
        self.d.addWidget(haut)
        self.d.addWidget(partage(sg, sd), 1)
        return sg, sd


def partage(gauche: QWidget, droite: QWidget) -> QSplitter:
    """Deux panneaux défilants côte à côte, séparés par une barre déplaçable."""
    s = QSplitter(Qt.Orientation.Horizontal)
    s.addWidget(_defilable(gauche))
    s.addWidget(_defilable(droite))
    s.setStretchFactor(0, 2)
    s.setStretchFactor(1, 3)
    s.setSizes([560, 840])
    return s


def appliquerTheme(app: QApplication) -> None:
    """Palette Vanilla Peach, Lilac Stone, Twilight Purple, Midnight Violet ; thème clair ou sombre."""
    if state.v.get("sombre"):
        fond, carte, encre, bord, accent, menu = "#0E0B16", "#1A1626", "#FFDBC3", "#9F91CC", "#7A68C0", "#1A1626"
    else:
        # cartes et champs en blanc chaud (celui des figures) : ils se détachent du fond pêche
        fond, carte, encre, bord, accent, menu = "#FFDBC3", FOND_FIGURE, "#3D246C", "#5C4B99", "#5C4B99", "#3D246C"
    app.setStyleSheet(f"""
    QWidget {{ background:{fond}; color:{encre}; font-size:10pt; }}
    QLabel {{ background:transparent; }}
    QToolTip {{ background:{carte}; color:{encre}; border:1px solid {bord}; }}
    #titre {{ font-size:19pt; font-weight:bold; }}
    #sousTitre {{ font-size:13pt; font-weight:bold; margin-top:8px; }}
    #legende {{ font-size:9pt; }}
    #etiquette {{ font-size:9pt; margin-top:3px; }}
    #metrique, #cadre {{ background:{carte}; border:1px solid {bord}; border-radius:5px; }}
    #metrique QLabel, #cadre QLabel, #cadre QWidget {{ background:transparent; }}
    #metriqueLibelle {{ font-size:8pt; }}
    #metriqueValeur {{ font-size:13pt; font-weight:bold; }}
    QRadioButton::indicator, QCheckBox::indicator, QListWidget::indicator {{ width:13px; height:13px; background:{carte};
        border:1px solid {bord}; }}
    QRadioButton::indicator {{ border-radius:7px; }}
    QRadioButton::indicator:checked, QCheckBox::indicator:checked, QListWidget::indicator:checked {{ background:{accent}; }}
    QLineEdit, QPlainTextEdit, QComboBox, QListWidget, QTableWidget {{
        background:{carte}; border:1px solid {bord}; border-radius:3px; padding:2px; }}
    QTableWidget {{ gridline-color:{bord}; }}
    QLineEdit:disabled, QComboBox:disabled {{ color:#8E86AA; }}
    QHeaderView::section {{ background:{bord}; color:#FFFFFF; padding:3px; border:none; }}
    #bouton {{ background:{carte}; border:1px solid {bord}; border-radius:4px; padding:5px 10px; }}
    #bouton:hover {{ border-color:{encre}; }}
    #bouton:disabled, #primaire:disabled {{ color:#8E86AA; }}
    #primaire {{ background:{accent}; color:#FFFFFF; border:none; border-radius:4px; padding:7px 12px;
                 font-weight:bold; }}
    #lien {{ background:transparent; border:none; color:{encre}; text-decoration:underline; text-align:left;
             padding:2px; }}
    #cadre #primaire {{ background:{accent}; }}
    #cadre #bouton {{ background:{carte}; }}
    #repli {{ background:{carte}; border:1px solid {bord}; border-radius:4px; padding:4px; font-weight:bold; }}
    #menu {{ background:{menu}; color:#FFDBC3; border:none; font-size:10pt; }}
    #menu::item {{ padding:6px 8px; }}
    #menu::item:selected {{ background:#5C4B99; color:#FFFFFF; }}
    QMenuBar::item {{ padding:4px 10px; }}
    QMenu {{ border:1px solid {bord}; }}
    QMenu::item {{ padding:5px 24px; }}
    QMenuBar::item:selected, QMenu::item:selected {{ background:{accent}; color:#FFFFFF; }}
    QMenu::item:disabled {{ color:#8E86AA; }}
    QTabWidget::pane {{ border:1px solid {bord}; }}
    QTabBar::tab {{ background:{carte}; border:1px solid {bord}; padding:5px 9px; }}
    QTabBar::tab:selected {{ background:{accent}; color:#FFFFFF; }}
    """)
