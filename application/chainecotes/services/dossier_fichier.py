"""Fichier de dossier de validation prêt à télécharger, en HTML, PDF ou Word (graphiques compris).

Rassemble graphiquesDossier et le générateur du format choisi, pour que les pages n'aient qu'un appel à faire.
Ce module n'importe ni streamlit ni plotly.
"""

from datetime import date as _Date

from chainecotes.core.errors import ErreurChaine
from chainecotes.services.dossier_word import dossierWord
from chainecotes.services.graphiques_dossier import graphiquesDossier
from chainecotes.services.rapport_pdf import rapportPdf
from chainecotes.services.validation import dossierValidation

FORMATS_DOSSIER = {
    "HTML": ("html", "text/html"),
    "PDF": ("pdf", "application/pdf"),
    "Word": ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
}
AVERTISSEMENT_IMAGES = (
    "Les images des graphiques n'ont pas pu être produites sur ce serveur (navigateur absent) : le HTML garde des "
    "graphiques interactifs, le PDF et le Word les signalent seulement."
)


def fichierDossier(probleme: dict, bundle: dict, format: str, date: _Date | str | None = None) -> dict:
    """Construit le dossier de validation d'un calcul dans le format choisi.

    Entrées : probleme (dict condition, reglages, maillons et, facultatif, cartouche), bundle (sortie de
    calculerChaine), format (« HTML », « PDF » ou « Word »), date (date ou texte imprimé ; aujourd'hui par défaut).
    Sortie : dict contenu (str pour le HTML, bytes sinon), extension, mime, imagesManquantes (bool : les PNG des
    graphiques n'ont pas pu être produits).
    Erreur : ErreurChaine si le format est inconnu ou le calcul invalide ; KeyError si bundle n'est pas une sortie de
    calculerChaine ; FileNotFoundError si la police du PDF manque.
    """
    if format not in FORMATS_DOSSIER:
        raise ErreurChaine("Chaine:Fichier:format", f"Format de dossier inconnu : {format!r} (HTML, PDF ou Word).")
    date = date or _Date.today()
    graphiques = graphiquesDossier(bundle)
    if format == "PDF":
        contenu = rapportPdf(probleme, bundle, date, graphiques)
    elif format == "Word":
        contenu = dossierWord(probleme, bundle, date, graphiques)
    else:
        contenu = dossierValidation(probleme, bundle, graphiques)["html"]
    extension, mime = FORMATS_DOSSIER[format]
    return {
        "contenu": contenu,
        "extension": extension,
        "mime": mime,
        "imagesManquantes": not all(g["png"] for g in graphiques),
    }
