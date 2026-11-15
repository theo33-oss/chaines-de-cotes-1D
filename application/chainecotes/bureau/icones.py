"""Icônes SVG du menu et de la fenêtre : de simples traits, dessinés ici, à la couleur du texte du menu (ni image ni emoji).

Les tracés d'accueil, d'étude, de mécanisme et d'aides sont ceux du site (ICONES de docs/app.js).
"""

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from chainecotes.core.donnees import DOSSIER_DONNEES

TRACES = {
    "accueil": '<path d="M3 11l9-8 9 8M5 10v10h5v-6h4v6h5V10"/>',
    "analyser": '<path d="M3 7v10M21 7v10M3 12h18M7 9l-4 3 4 3M17 9l4 3-4 3"/>',
    "mecanisme": '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2"/>',
    "parcours": '<path d="M9 6h11M9 12h11M9 18h11M4 6h.01M4 12h.01M4 18h.01"/>',
    "assistant": '<circle cx="6" cy="12" r="2"/><circle cx="18" cy="6" r="2"/><circle cx="18" cy="18" r="2"/><path d="M8 11l8-4M8 13l8 4"/>',
    "exemples": '<path d="M4 4h13a3 3 0 0 1 3 3v13H7a3 3 0 0 1-3-3zM4 17a3 3 0 0 1 3-3h13"/>',
    "ajustement": '<path d="M3 8h6v8H3M21 8h-6v8h6M9 12h6"/>',
    "iso286": '<rect x="3" y="4" width="18" height="16" rx="1"/><path d="M3 10h18M9 4v16"/>',
    "materiaux": '<path d="M10 14V5a2 2 0 0 1 4 0v9a4 4 0 1 1-4 0z"/>',
    "apropos": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5h.01"/>',
}
# ligne du menu → tracé (le menu et le site n'ont pas tout à fait les mêmes noms)
PAGE_VERS_TRACE = {"calcul": "analyser"}


def _icone(svg: str, taille: int) -> QIcon:
    rendu = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    image = QImage(taille, taille, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    peintre = QPainter(image)
    rendu.render(peintre)
    peintre.end()
    return QIcon(QPixmap.fromImage(image))


def iconeMenu(page: str, couleur: str = "#FFDBC3", taille: int = 36) -> QIcon:
    """Icône d'une ligne du menu (identifiant de page), tracée à la couleur du texte du menu."""
    trace = TRACES[PAGE_VERS_TRACE.get(page, page)]
    return _icone(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{couleur}" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round">{trace}</svg>',
        taille,
    )


def iconeApplication(taille: int = 128) -> QIcon:
    """Icône de la fenêtre : celle du site (data/icone.svg)."""
    return _icone((DOSSIER_DONNEES / "icone.svg").read_text(encoding="utf-8"), taille)
