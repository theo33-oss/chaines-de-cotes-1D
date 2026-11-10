"""Dossier de validation Word (.docx) d'une chaîne de cotes, avec python-docx.

Même contenu que le dossier HTML (services/validation.dossierValidation) : saisie, hypothèses, contrôles refaits à la
main, bilan et avertissements. Ce module n'importe ni streamlit ni plotly.
"""

import io
from datetime import date as _Date

from docx import Document
from docx.shared import Cm, Pt, RGBColor

from chainecotes.services.cartouche import REVISIONS, lignesCartouche, revisions
from chainecotes.services.validation import dossierValidation
from chainecotes.services.validation_html import HYPOTHESES

VIOLET = RGBColor(0x3D, 0x24, 0x6C)


def _nombre(v) -> str:
    """Nombre écrit avec une virgule décimale, « — » si la valeur est absente."""
    if v is None:
        return "—"
    return f"{v:.6g}".replace(".", ",")


def _tableau(document, entetes: list[str], lignes: list[list[str]]) -> None:
    """Tableau Word à en-tête gras, une ligne par liste de textes."""
    table = document.add_table(rows=1, cols=len(entetes))
    table.style = "Light Grid Accent 1"
    for cellule, texte in zip(table.rows[0].cells, entetes, strict=True):
        cellule.text = texte
        cellule.paragraphs[0].runs[0].bold = True
    for ligne in lignes:
        cellules = table.add_row().cells
        for cellule, texte in zip(cellules, ligne, strict=True):
            cellule.text = texte


def dossierWord(probleme: dict, bundle: dict, date: _Date | str, graphiques: list[dict] | None = None) -> bytes:
    """Dossier de validation Word : saisie, hypothèses, contrôles, bilan et avertissements.

    Entrées : probleme (dict condition, reglages, maillons), bundle (sortie de calculerChaine), date (date ou texte
    imprimé en tête ; passée en paramètre pour un fichier reproductible), graphiques (sortie de graphiquesDossier :
    ajoute l'annexe « graphiques du calcul » ; None : sans).
    Sortie : contenu du fichier .docx (bytes, commence par « PK »).
    Erreurs : KeyError si bundle n'est pas une sortie de calculerChaine.
    """
    dossier = dossierValidation(probleme, bundle)
    nom = (probleme.get("condition") or {}).get("nom") or "Jeu J"
    document = Document()
    style = document.styles["Normal"]
    style.font.name = "Arial"
    style.font.size = Pt(10)

    titre = document.add_heading(f"Dossier de validation — {nom}", level=0)
    titre.runs[0].font.color.rgb = VIOLET
    document.add_paragraph(f"Date : {date}")
    cartouche = lignesCartouche(probleme)
    if cartouche:
        _tableau(document, ["Cartouche", ""], [[a, b] for a, b in cartouche])
    historique = revisions(probleme)
    if historique:
        document.add_paragraph()
        _tableau(
            document,
            [t for _, t in REVISIONS],
            [[r[c] for c, _ in REVISIONS] for r in historique],
        )

    document.add_heading("Bilan", level=1)
    document.add_paragraph(dossier["bilan"], style="Intense Quote")
    for c in dossier["controles"]:
        if c["statut"] != "OK":
            document.add_paragraph(
                f"{c['nom']} : attendu {_nombre(c['attendu'])}, obtenu {_nombre(c['obtenu'])} ({c['methode']})",
                style="List Bullet",
            )

    document.add_heading("1. Saisie du problème", level=1)
    _tableau(
        document,
        ["Maillon", "Sens", "Cote (mm)", "ISO 286", "ES (mm)", "EI (mm)", "Loi"],
        [
            [
                m.get("nom", ""),
                m.get("sens", "+"),
                _nombre(m.get("cote")),
                m.get("iso") or "—",
                _nombre(m.get("es")),
                _nombre(m.get("ei")),
                m.get("loi") or "normale",
            ]
            for m in probleme["maillons"]
        ],
    )

    document.add_heading("2. Hypothèses et domaine d'application", level=1)
    for texte in HYPOTHESES:
        document.add_paragraph(texte, style="List Bullet")

    document.add_heading("3. Contrôles refaits à la main", level=1)
    _tableau(
        document,
        ["Contrôle", "Méthode", "Attendu", "Obtenu", "Statut"],
        [
            [c["nom"], c["methode"], _nombre(c["attendu"]), _nombre(c["obtenu"]), c["statut"]]
            for c in dossier["controles"]
        ],
    )

    avertissements = bundle.get("avertissements") or []
    document.add_heading("4. Avertissements du calcul", level=1)
    if avertissements:
        for a in avertissements:
            document.add_paragraph(a, style="List Bullet")
    else:
        document.add_paragraph("Aucun avertissement.")

    if graphiques is not None:
        document.add_heading("5. Annexe : graphiques du calcul", level=1)
        if not any(g.get("png") for g in graphiques):
            document.add_paragraph(
                "Les images des graphiques n'ont pas pu être produites sur ce poste (navigateur absent). Elles "
                "sont disponibles dans le dossier au format HTML et dans l'application."
            )
        for g in graphiques:
            document.add_heading(g["titre"], level=2)
            if g.get("png"):
                document.add_picture(io.BytesIO(g["png"]), width=Cm(16))
            document.add_paragraph(g["legende"])

    tampon = io.BytesIO()
    document.save(tampon)
    return tampon.getvalue()
