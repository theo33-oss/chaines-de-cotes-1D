"""Tableau de cotation d'une chaîne de cotes, exporté en xlsx et en csv.

La cotation est une cotation par écarts (ISO 129-1) interprétée selon le principe d'indépendance (ISO 8015) :
chaque cote tient seule, sans lien implicite entre taille et forme. La chaîne étant linéaire, aucun symbole de
tolérancement géométrique (ISO 1101) n'est produit : ils ne s'appliquent pas à une cote linéaire de chaîne.
"""

import csv
import io
import math

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from chainecotes.core.chaine import solveurChaine
from chainecotes.core.errors import ErreurChaine
from chainecotes.core.geometrie import libelle
from chainecotes.core.nombres import fr
from chainecotes.services.projet_io import _celluleCsv, _neutre

NOTE_NORMES = (
    "Cotation par écarts selon l'ISO 129-1, lue selon le principe d'indépendance (ISO 8015) : chaque cote et sa "
    "tolérance sont exigées indépendamment des autres. Chaîne de cotes linéaire : aucun symbole de tolérancement "
    "géométrique (ISO 1101) n'est associé."
)
COLONNES = [
    ("repere", "Repère", None, 8),
    ("nom", "Maillon", None, 20),
    ("designation", "Désignation ISO 286", None, 12),
    ("cote", "Cote nominale (mm)", "0.000", 12),
    ("es", "ES (mm)", "+0.0000;-0.0000;0.0000", 11),
    ("ei", "EI (mm)", "+0.0000;-0.0000;0.0000", 11),
    ("cmax", "Cote maxi (mm)", "0.0000", 12),
    ("cmin", "Cote mini (mm)", "0.0000", 12),
    ("it", "IT (mm)", "0.0000", 10),
    ("tolSym", "Tolérance équivalente ± (mm)", "0.0000", 14),
    ("procede", "Procédé garanti", None, 24),
    ("remarque", "Remarque", None, 50),
]


def _procede(m: dict, k: float) -> str:
    if m["loi"] == "normale":
        return f"loi normale, ±{fr(k, 'g')} σ"
    return "loi uniforme (bornes ES / EI)"


def tableauCotation(probleme: dict, bundle: dict | None = None) -> list[dict]:
    """Lignes du tableau de cotation, une par maillon, dans l'ordre de la chaîne.

    Entrées : probleme (dict condition, reglages, maillons), bundle (sortie de calculerChaine ; sinon le problème
    est résolu ici). Cotes, écarts et tolérances en mm.
    Sortie : liste de dict repere (« M1 »…), nom, sens, designation (texte ISO 286 ou « » si les écarts sont
    saisis), cote (nominale), es, ei, cmax, cmin, it, tolSym (it / 2 si ES = −EI, sinon None), procede (loi et
    k), remarque (texte : origine des écarts, écart connu ISO, hors domaine matériau).
    Erreur : ErreurChaine si le problème est invalide.
    """
    res = bundle["res"] if bundle else solveurChaine(probleme)
    k = res["reglages"]["kSigma"]
    lignes = []
    for i, m in enumerate(res["maillons"], start=1):
        remarques = [m["avertissement"]] if m["avertissement"] else []
        if m["geometrie"]:
            remarques.append(
                f"tolérance géométrique ISO 1101 ({libelle(m['geometrie'])}), zone de {fr(m['es'] - m['ei'], 'g')} mm : "
                "à porter dans un cadre de tolérance sur le plan"
            )
        elif m["origine"]:
            remarques.append(f"tolérance générale ISO {m['origine']} (± {fr(m['es'], 'g')} mm), non portée sur la cote")
        else:
            remarques.append("écarts de la désignation ISO 286" if m["iso"] else "écarts saisis")
        if m["horsDomaine"]:
            remarques.append(f"hors domaine du matériau ({m['motif']})")
        it = m["es"] - m["ei"]
        lignes.append(
            {
                "repere": f"M{i}",
                "nom": m["nom"],
                "sens": m["sens"],
                "designation": m["iso"],
                "cote": m["cote"],
                "es": m["es"],
                "ei": m["ei"],
                "cmax": m["cote"] + m["es"],
                "cmin": m["cote"] + m["ei"],
                "it": it,
                "tolSym": it / 2 if math.isclose(m["es"], -m["ei"], abs_tol=1e-12) else None,
                "procede": _procede(m, k),
                "remarque": " ; ".join(remarques),
            }
        )
    return lignes


def _hypotheses(probleme: dict, bundle: dict | None) -> list[tuple[str, str]]:
    res = bundle["res"] if bundle else solveurChaine(probleme)
    c, r = res["condition"], res["reglages"]

    def limite(x):
        return "aucune" if math.isinf(x) else f"{fr(x, 'g')} mm"

    modeT = "température de service uniforme" if r["modeT"] == "uniforme" else "température de service par cote"
    lignes = [
        ("Normes", NOTE_NORMES),
        ("Cote condition", f"{c['nom']} : Jmin = {limite(c['jmin'])}, Jmax = {limite(c['jmax'])}"),
        ("Jeu nominal Σ aᵢ·cᵢ", f"{fr(res['CF_nom_ref'], 'g')} mm"),
        ("Procédé garanti k", f"{fr(r['kSigma'], 'g')} (loi normale : σ = IT / 2k)"),
        ("Loi uniforme", "σ = IT / √12"),
        ("Tolérance générale", f"ISO 2768-{r['tolGenerale']} pour les cotes sans écarts" if r["tolGenerale"]
         else "aucune : tous les écarts sont saisis"),
        ("Températures", f"référence {fr(r['tref'], 'g')} °C, {modeT}"),
        ("Unités", "cotes et écarts en mm ; IT = ES − EI ; cote maxi = cote + ES ; cote mini = cote + EI"),
        ("Tolérance équivalente ±", "donnée seulement si ES = −EI (tolérance symétrique), valeur IT / 2"),
    ]
    for t in (bundle or {}).get("avertissements", []):
        lignes.append(("Avertissement", t))
    return lignes


def exporterCotation(probleme: dict, bundle: dict | None = None, format: str = "xlsx") -> bytes:
    """Tableau de cotation exporté en fichier.

    Entrées : probleme et bundle (voir tableauCotation), format (« xlsx » ou « csv »).
    Sortie : octets du fichier. xlsx : feuille « Cotation » (en-tête figé, formats de nombres en mm, largeurs de
    colonnes, note de norme sous le tableau) et feuille « Hypothèses ». csv : UTF-8 avec BOM, séparateur « ; »,
    virgule décimale, mêmes colonnes que la feuille Cotation puis la note de norme.
    Erreur : ErreurChaine si le format est inconnu ou le problème invalide.
    """
    if format not in ("xlsx", "csv"):
        raise ErreurChaine("Chaine:Fichier:format", f"Format d'export inconnu : {format!r} (xlsx ou csv).")
    lignes = tableauCotation(probleme, bundle)
    if format == "csv":
        # module csv : une cellule qui contient « ; », un guillemet ou un retour à la ligne est mise entre guillemets,
        # et chaque cellule texte est neutralisée seule (un nom « a;=1+1 » ne crée pas de formule)
        sortie = io.StringIO()
        ecrit = csv.writer(sortie, delimiter=";", lineterminator="\r\n")
        ecrit.writerow(_neutre(titre) for _, titre, _, _ in COLONNES)
        for ln in lignes:
            ecrit.writerow("" if ln[cle] is None else _celluleCsv(ln[cle]) for cle, _, _, _ in COLONNES)
        ecrit.writerow([])
        ecrit.writerow([_neutre(NOTE_NORMES)])
        return sortie.getvalue().removesuffix("\r\n").encode("utf-8-sig")  # pas de ligne vide finale

    wb = Workbook()
    ws = wb.active
    ws.title = "Cotation"
    fin = Side(style="thin", color="999999")
    ws.append([titre for _, titre, _, _ in COLONNES])
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="305496")
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for ln in lignes:
        ws.append([_neutre(ln[cle]) for cle, _, _, _ in COLONNES])
    for j, (_, _, fmt, largeur) in enumerate(COLONNES, start=1):
        ws.column_dimensions[get_column_letter(j)].width = largeur
        for ligne in ws.iter_rows(min_row=2, max_row=len(lignes) + 1, min_col=j, max_col=j):
            for c in ligne:
                c.border = Border(top=fin, bottom=fin, left=fin, right=fin)
                if fmt:
                    c.number_format = fmt
                c.alignment = Alignment(vertical="top", wrap_text=fmt is None)
    ws.row_dimensions[1].height = 32
    ws.freeze_panes = "A2"
    note = len(lignes) + 3
    ws.cell(note, 1, NOTE_NORMES).font = Font(italic=True)
    ws.merge_cells(start_row=note, start_column=1, end_row=note, end_column=len(COLONNES))
    ws.cell(note, 1).alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[note].height = 45
    h = wb.create_sheet("Hypothèses")
    h.append(["Rubrique", "Texte"])
    for c in h[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="305496")
    for rubrique, texte in _hypotheses(probleme, bundle):
        h.append([rubrique, _neutre(texte)])
    h.column_dimensions["A"].width = 26
    h.column_dimensions["B"].width = 110
    for ligne in h.iter_rows(min_row=2):
        for c in ligne:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    tampon = io.BytesIO()
    wb.save(tampon)
    return tampon.getvalue()
