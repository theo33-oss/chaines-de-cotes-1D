"""Dossier de calcul PDF d'une chaîne de cotes (fpdf2, police DejaVu embarquée dans data/polices/).

Contenu : page de garde, saisie, hypothèses, résultats, verdicts, avertissements, bilan du dossier de validation.
Aucune figure. Ce module n'importe ni streamlit ni plotly (le formateur de nombres est donc local).
"""

import io
from datetime import date as _Date
from pathlib import Path

from fpdf import FPDF
from fpdf.fonts import FontFace

from chainecotes.core.chaine import estVide
from chainecotes.core.nombres import fr
from chainecotes.services.cartouche import REVISIONS, lignesCartouche, revisions
from chainecotes.services.graphiques_dossier import LARGEUR_PX
from chainecotes.services.validation import dossierValidation
from chainecotes.services.validation_html import HYPOTHESES

VERSION = "0.1.0"  # version de l'application, identique à pyproject.toml
_POLICES = Path(__file__).resolve().parents[2] / "data" / "polices"
_VIOLET = (61, 36, 108)
_GRIS = (226, 221, 241)


def _ok(b) -> str:
    return "Conforme" if b else "Non conforme"


class _Pdf(FPDF):
    """Document avec police Unicode, pied de page numéroté et tableaux à saut de page automatique."""

    def __init__(self, titre: str):
        super().__init__(format="A4")
        self.titre = titre
        self.substitues = False
        self.add_font("DejaVu", "", str(_POLICES / "DejaVuSans.ttf"))
        self.add_font("DejaVu", "B", str(_POLICES / "DejaVuSans-Bold.ttf"))
        self.set_auto_page_break(True, margin=15)
        self.set_margins(15, 15, 15)
        self.set_title(titre)
        self.set_creator("Chaînes de cotes 1D")

    def normalize_text(self, text: str) -> str:
        """Remplace par « ? » les caractères que la police ne contient pas (et les tabulations par un espace).

        Sans cela fpdf2 les supprime sans prévenir ; `substitues` mémorise qu'il y en a eu pour le signaler
        dans le dossier.
        """
        text = super().normalize_text(text).replace(chr(9), " ")
        cmap = getattr(self.current_font, "cmap", None)
        if not cmap:
            return text
        sortie = "".join(c if ord(c) in cmap or c in "\n\r" else "?" for c in text)
        self.substitues = self.substitues or sortie != text
        return sortie

    def footer(self):
        self.set_y(-12)
        self.set_font("DejaVu", "", 8)
        self.cell(0, 6, f"{self.titre} — page {self.page_no()}/{{nb}}", align="C")

    def titreSection(self, texte: str) -> None:
        self.ln(3)
        self.set_font("DejaVu", "B", 13)
        self.set_text_color(*_VIOLET)
        self.cell(0, 8, texte, new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0)

    def paragraphe(self, texte: str, gras: bool = False) -> None:
        self.set_font("DejaVu", "B" if gras else "", 10)
        self.multi_cell(0, 5.5, texte, new_x="LMARGIN", new_y="NEXT")

    def tableau(self, entetes, lignes, largeurs) -> None:
        """Tableau dont l'en-tête est répété à chaque page ; largeurs en mm (somme ≤ 180)."""
        self.set_font("DejaVu", "", 8)
        with self.table(
            col_widths=largeurs,
            text_align="LEFT",
            headings_style=FontFace(emphasis="BOLD", fill_color=_GRIS),
            line_height=5,
        ) as t:
            t.row(entetes)
            for lig in lignes:
                t.row([str(x) for x in lig])
        self.ln(2)


def _annexeGraphiques(pdf: _Pdf, graphiques: list[dict]) -> None:
    """Annexe : une image par graphique avec sa légende ; sans image (export impossible), le titre et la légende."""
    pdf.add_page()
    pdf.titreSection("7. Annexe : graphiques du calcul")
    if not any(g.get("png") for g in graphiques):
        pdf.paragraphe(
            "Les images des graphiques n'ont pas pu être produites sur ce poste (navigateur absent). Ils sont "
            "disponibles dans le dossier au format HTML et dans l'application."
        )
    largeur = 180  # mm
    for g in graphiques:
        hauteur = largeur * (g["fig"].layout.height or 420) / LARGEUR_PX
        if pdf.get_y() + hauteur + 20 > pdf.h - 15:  # le titre, l'image et la légende restent ensemble
            pdf.add_page()
        pdf.set_font("DejaVu", "B", 11)
        pdf.cell(0, 7, g["titre"], new_x="LMARGIN", new_y="NEXT")
        if g.get("png"):
            pdf.image(io.BytesIO(g["png"]), w=largeur)
        pdf.set_font("DejaVu", "", 9)
        pdf.multi_cell(0, 5, g["legende"], new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)


def _saisie(pdf: _Pdf, probleme: dict) -> None:
    c, r = probleme.get("condition") or {}, probleme.get("reglages") or {}

    def lim(v):
        return "pas de limite" if estVide(v) else f"{fr(v, 'g')} mm"

    pdf.titreSection("1. Saisie")
    pdf.paragraphe(
        f"Cote condition : {c.get('nom', 'Jeu J')} — J min = {lim(c.get('jmin'))}, J max = {lim(c.get('jmax'))}\n"
        f"Procédé garanti à ± k σ avec k = {fr(r.get('kSigma', 3), 'g')} ; température de référence "
        f"{fr(r.get('tref', 20), 'g')} °C ; mode de température : {r.get('modeT', 'uniforme')}."
    )
    cols = ("nom", "sens", "cote", "iso", "es", "ei", "loi", "materiau")
    lignes = [["" if estVide(m.get(k)) else m.get(k) for k in cols] for m in probleme.get("maillons") or []]
    pdf.tableau(
        ("Nom", "Sens", "Cote (mm)", "ISO", "es (mm)", "ei (mm)", "Loi", "Matériau"),
        lignes,
        (36, 12, 22, 16, 22, 22, 22, 28),
    )


def _resultats(pdf: _Pdf, bundle: dict) -> None:
    res, v, mc = bundle["res"], bundle["verdicts"], bundle.get("mc")
    pdf.titreSection("3. Résultats")
    pdf.paragraphe("Cote condition (jeu), en mm", gras=True)
    pdf.tableau(
        ("Grandeur", "Valeur"),
        [
            ("Nominal", fr(res["CF_nom"])),
            ("Moyenne", fr(res["CF_moy"])),
            ("Pire cas [min ; max]", f"[{fr(res['CF_min'])} ; {fr(res['CF_max'])}]"),
            ("Écart type σ", fr(res["CF_sigma"], ".5f")),
            ("Statistique ± k σ", f"[{fr(v['rssK']['min'])} ; {fr(v['rssK']['max'])}]"),
            ("Statistique ± 6 σ", f"[{fr(v['rss6']['min'])} ; {fr(v['rss6']['max'])}]"),
        ],
        (80, 100),
    )
    pdf.paragraphe("Aptitude du procédé", gras=True)
    pdf.tableau(
        ("Indicateur", "Formule", "Monte-Carlo"),
        [
            ("Cp", fr(v["cp"], ".3f"), fr(mc["cp"], ".3f") if mc else "—"),
            ("Cpk", fr(v["cpk"], ".3f"), fr(mc["cpk"], ".3f") if mc else "—"),
            ("ppm hors tolérance", fr(v["ppm"], ".0f"), fr(mc["ppm"], ".0f") if mc else "—"),
        ],
        (60, 60, 60),
    )
    if mc:
        pdf.paragraphe(
            f"Monte-Carlo : {mc['n']} tirages, graine {mc['graine']}, moyenne {fr(mc['moyenne'])} mm, "
            f"écart type {fr(mc['ecartType'], '.5f')} mm, {mc['nHors']} tirages hors limites."
        )
    else:
        pdf.paragraphe("Monte-Carlo : non réalisé (dispersion nulle ou simulation désactivée).")
    pdf.titreSection("4. Verdicts")
    pdf.tableau(
        ("Méthode", "Intervalle du jeu (mm)", "Verdict"),
        [
            ("Pire des cas", f"[{fr(v['pireCas']['min'])} ; {fr(v['pireCas']['max'])}]", _ok(v["pireCas"]["ok"])),
            ("Statistique ± k σ", f"[{fr(v['rssK']['min'])} ; {fr(v['rssK']['max'])}]", _ok(v["rssK"]["ok"])),
            ("Statistique ± 6 σ", f"[{fr(v['rss6']['min'])} ; {fr(v['rss6']['max'])}]", _ok(v["rss6"]["ok"])),
        ],
        (50, 80, 50),
    )


def rapportPdf(probleme: dict, bundle: dict, date: _Date | str, graphiques: list[dict] | None = None) -> bytes:
    """Dossier de calcul PDF (garde, saisie, hypothèses, résultats, verdicts, avertissements, validation).

    Entrées : probleme (dict condition, reglages, maillons), bundle (sortie de calculerChaine), date (date ou
    texte imprimé sur la page de garde ; passée en paramètre pour un PDF reproductible), graphiques (sortie de
    graphiquesDossier : ajoute l'annexe « graphiques du calcul » ; None : sans).
    Sortie : contenu du fichier PDF (bytes, commence par « %PDF »).
    Erreurs : KeyError si bundle n'est pas une sortie de calculerChaine ; FileNotFoundError si la police
    de data/polices/ manque. Le bilan de validation recalcule les contrôles (services/validation).
    """
    nom = (probleme.get("condition") or {}).get("nom") or "Jeu J"
    pdf = _Pdf(f"Dossier de calcul — {nom}")
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.ln(50)
    pdf.set_font("DejaVu", "B", 24)
    pdf.set_text_color(*_VIOLET)
    pdf.multi_cell(0, 12, "Dossier de calcul\nChaîne de cotes 1D", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)
    pdf.set_text_color(0)
    pdf.set_font("DejaVu", "", 16)
    pdf.multi_cell(0, 9, f"Cote condition : {nom}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "", 11)
    pdf.ln(8)
    d = date.strftime("%d/%m/%Y") if hasattr(date, "strftime") else str(date)
    pdf.multi_cell(0, 7, f"Date : {d}\nVersion de l'application : {VERSION}", align="C", new_x="LMARGIN", new_y="NEXT")
    cartouche, historique = lignesCartouche(probleme), revisions(probleme)
    if cartouche:
        pdf.ln(10)
        pdf.tableau(("Cartouche", ""), cartouche, (50, 130))
    if historique:
        pdf.tableau([t for _, t in REVISIONS], [[r[c] for c, _ in REVISIONS] for r in historique], (22, 28, 40, 90))
    pdf.add_page()
    _saisie(pdf, probleme)
    pdf.titreSection("2. Hypothèses et domaine d'application")
    for h in HYPOTHESES:
        pdf.paragraphe("• " + h)
    _resultats(pdf, bundle)
    pdf.titreSection("5. Avertissements")
    av = bundle.get("avertissements") or []
    for a in av or ["Aucun avertissement pour ce calcul."]:
        pdf.paragraphe(("• " if av else "") + a)
    if pdf.substitues:
        pdf.paragraphe(
            "• Certains caractères de la saisie ne sont pas pris en charge par la police du dossier : "
            "ils sont remplacés par « ? »."
        )
    dv = dossierValidation(probleme, bundle)
    pdf.titreSection("6. Dossier de validation")
    pdf.paragraphe(dv["bilan"], gras=True)
    pdf.tableau(
        ("Contrôle", "Attendu", "Solveur", "Statut"),
        [(c["nom"], fr(c["attendu"], ".6g"), fr(c["obtenu"], ".6g"), c["statut"]) for c in dv["controles"]],
        (84, 34, 34, 28),
    )
    if graphiques is not None:
        _annexeGraphiques(pdf, graphiques)
    return bytes(pdf.output())
