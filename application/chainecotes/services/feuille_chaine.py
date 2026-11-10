"""Feuille de chaîne de cotes Excel à formules vivantes (jeu au pire des cas, statistique, Cp, Cpk, ppm).

Les cellules de saisie (bleu sur fond jaune) sont modifiables dans Excel ; tout le reste est une formule qui se
recalcule. Une colonne « Valeur de l'application » garde le résultat du site pour contrôler la feuille. Ce module
n'importe ni streamlit ni plotly.
"""

import io
import math

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from chainecotes.core.chaine import solveurChaine
from chainecotes.services.cartouche import lignesCartouche
from chainecotes.services.projet_io import _neutre

TITRES = (
    "N°",
    "Maillon",
    "Sens",
    "Cote nominale (mm)",
    "ES (mm)",
    "EI (mm)",
    "Loi",
    "Facteur",
    "Angle (°)",
    "α (1e-6/K)",
    "T service (°C)",
    "Cote moyenne (mm)",
    "IT (mm)",
    "Coefficient a",
    "a en service",
    "Jeu nominal : a·cote (mm)",
    "Jeu moyen : a·cote moy. (mm)",
    "Pire des cas : |a|·IT/2 (mm)",
    "σ du maillon (mm)",
    "σ² (mm²)",
    "ISO 286",
    "σ mesuré (mm)",
    "Moyenne mesurée (mm)",
    "Écart mesuré : a·(moy. mesurée − cote moy.) (mm)",
)
LARGEURS = (5, 22, 6, 12, 10, 10, 13, 9, 9, 10, 10, 13, 10, 11, 11, 15, 15, 15, 12, 12, 10, 12, 14, 18)
BLEU = Font(color="0000FF")
SAISIE = PatternFill("solid", fgColor="FFF8DC")
ENTETE = PatternFill("solid", fgColor="305496")
FIN = Side(style="thin", color="999999")
BORDURE = Border(top=FIN, bottom=FIN, left=FIN, right=FIN)
FORMAT_MM = "0.0000"
TOLERANCE_RELATIVE = 1e-9
MODE_EMPLOI = (
    "Cellules bleues sur fond jaune : saisies, à modifier librement (cotes, écarts, sens « + » ou « - », loi "
    "« normale », « uniforme » ou « triangulaire », facteur, angle, α, température, Jmin, Jmax, k).",
    "Toutes les autres cellules sont des formules : le jeu au pire des cas, la statistique, Cp, Cpk et les ppm se "
    "recalculent à chaque changement. Pour ajouter un maillon, insérer une ligne dans le tableau et recopier les "
    "formules de la ligne du dessus ; ajuster ensuite les plages des sommes (ligne « Totaux »).",
    "Coefficient a = ± facteur · cos(angle) (le signe vient du sens) ; en service, a est multiplié par (1 + α · "
    "(T service − T référence)).",
    "Loi normale : σ = |a| · IT / (2k) ; uniforme : σ = |a| · IT / √12 ; triangulaire : σ = |a| · IT / (2√6).",
    "Mesures de l'atelier (colonnes « σ mesuré » et « Moyenne mesurée », facultatives) : un σ mesuré remplace le σ de "
    "la loi (σ = |a| · σ mesuré) ; une moyenne mesurée décale la moyenne du procédé de a · (moyenne mesurée − cote "
    "moyenne). Cellules laissées vides : le calcul reste celui de la loi.",
    "La colonne « Valeur de l'application » contient le résultat du site au moment de l'export : « OK » dans la "
    "colonne Contrôle veut dire que cette feuille redonne le même nombre.",
    "Cotation par écarts (ISO 129-1), principe d'indépendance (ISO 8015). Chaîne 1D : aucun symbole géométrique.",
)


def _nombre(v):
    """Nombre fini pour une cellule, None (cellule vide) si la valeur est infinie ou absente."""
    return None if v is None or (isinstance(v, float) and not math.isfinite(v)) else v


def _case(ws, ref: str, valeur, saisie: bool = False, fmt: str | None = None):
    c = ws[ref]
    c.value = valeur
    c.border = BORDURE
    if saisie:
        c.font, c.fill = BLEU, SAISIE
    if fmt:
        c.number_format = fmt
    return c


def exporterFeuilleChaine(probleme: dict, bundle: dict | None = None) -> bytes:
    """Classeur Excel de la chaîne, avec des formules vivantes.

    Entrées : probleme (dict condition, reglages, maillons ; un bloc « cartouche » facultatif est repris),
    bundle (sortie de calculerChaine ; sinon le problème est résolu ici). Cotes en mm, α en 1e-6/K, T en °C.
    Sortie : contenu du fichier .xlsx (bytes) : feuille « Chaîne » (paramètres, tableau des maillons, totaux et
    résultats en formules, comparaison au calcul du site) et feuille « Mode d'emploi ».
    Erreur : ErreurChaine si le problème est invalide.
    """
    res = bundle["res"] if bundle else solveurChaine(probleme)
    v = bundle["verdicts"] if bundle else None
    wb = Workbook()
    ws = wb.active
    ws.title = "Chaîne"
    c, r = res["condition"], res["reglages"]
    ws["A1"] = _neutre(f"Chaîne de cotes — {c['nom']}")
    ws["A1"].font = Font(bold=True, size=14)
    ligne = 3
    for libelle, texte in lignesCartouche(probleme):
        ws.cell(ligne, 1, libelle).font = Font(bold=True)
        ws.cell(ligne, 3, _neutre(texte))
        ligne += 1
    ligne += 1

    parametres = {}
    for cle, libelle, valeur, fmt in (
        ("jmin", "Jmin (mm) — vide : pas de limite", _nombre(c["jmin"]), FORMAT_MM),
        ("jmax", "Jmax (mm) — vide : pas de limite", _nombre(c["jmax"]), FORMAT_MM),
        ("k", "k : procédé garanti à ± k σ", r["kSigma"], "0.00"),
        ("tref", "T référence (°C)", r["tref"], "0.0"),
        ("dec", "Décentrage du procédé (en σ du jeu)", r["decentrage"], "0.00"),
    ):
        ws.cell(ligne, 1, libelle).font = Font(bold=True)
        parametres[cle] = f"$D${ligne}"
        _case(ws, f"D{ligne}", valeur, saisie=True, fmt=fmt)
        ligne += 1
    jmin, jmax, k, tref, dec = (parametres[x] for x in ("jmin", "jmax", "k", "tref", "dec"))

    ligne += 1
    entete = ligne
    for j, (titre, largeur) in enumerate(zip(TITRES, LARGEURS, strict=True), start=1):
        cel = ws.cell(entete, j, titre)
        cel.font, cel.fill, cel.border = Font(bold=True, color="FFFFFF"), ENTETE, BORDURE
        cel.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(j)].width = largeur
    ws.row_dimensions[entete].height = 45
    premiere = entete + 1
    n = len(res["Nom"])
    derniere = premiere + n - 1
    for i, m in enumerate(res["maillons"]):
        x = premiere + i
        saisies = {
            "A": i + 1,
            "B": _neutre(m["nom"]),
            "C": m["sens"],
            "D": m["cote"],
            "E": m["es"],
            "F": m["ei"],
            "G": m["loi"],
            "H": m["facteur"],
            "I": m["angle"],
            "J": m["alpha"] * 1e6,
            "K": m["tservice"],
            "V": m["sigma_reel"],
            "W": m["moyenne_reelle"],
        }
        for col, valeur in saisies.items():
            fmt = FORMAT_MM if col in "DEFVW" else None
            _case(ws, f"{col}{x}", valeur, saisie=col != "A", fmt=fmt)
        formules = {
            "L": (f"=D{x}+(E{x}+F{x})/2", FORMAT_MM),
            "M": (f"=E{x}-F{x}", FORMAT_MM),
            "N": (f'=IF(C{x}="+",1,-1)*H{x}*COS(RADIANS(I{x}))', "0.0000"),
            "O": (f"=N{x}*(1+J{x}*0.000001*(K{x}-{tref}))", "0.00000000"),
            "P": (f"=O{x}*D{x}", FORMAT_MM),
            "Q": (f"=O{x}*L{x}", FORMAT_MM),
            "R": (f"=ABS(O{x})*M{x}/2", FORMAT_MM),
            "S": (
                f"=IF(ISNUMBER(V{x}),ABS(O{x})*V{x},"
                f'ABS(O{x})*M{x}*IF(G{x}="normale",1/(2*{k}),IF(G{x}="uniforme",1/SQRT(12),1/(2*SQRT(6)))))',
                "0.000000",
            ),
            "T": (f"=S{x}^2", "0.00000000"),
            "X": (f"=IF(ISNUMBER(W{x}),O{x}*(W{x}-L{x}),0)", FORMAT_MM),
        }
        for col, (formule, fmt) in formules.items():
            _case(ws, f"{col}{x}", formule, fmt=fmt)
        _case(ws, f"U{x}", m["iso"] or "")

    def somme(col):
        return f"=SUM({col}{premiere}:{col}{derniere})"

    tot = derniere + 1
    ws.cell(tot, 2, "Totaux").font = Font(bold=True)
    for col in "PQRTX":
        _case(ws, f"{col}{tot}", somme(col), fmt=FORMAT_MM if col != "T" else "0.00000000")
    nom, moy, demi, var, ecartMesure = f"P{tot}", f"Q{tot}", f"R{tot}", f"T{tot}", f"X{tot}"

    ligne = tot + 2
    cap = ligne
    for j, titre in enumerate(("Résultat", "", "", "Feuille", "Valeur de l'application", "Écart", "Contrôle"), start=1):
        if titre:
            cel = ws.cell(cap, j, titre)
            cel.font, cel.fill = Font(bold=True, color="FFFFFF"), ENTETE
    ligne += 1
    cases = {}

    def resultat(cle, libelle, formule, valeurApp, fmt=FORMAT_MM):
        nonlocal ligne
        ws.cell(ligne, 2, libelle)
        _case(ws, f"D{ligne}", formule, fmt=fmt)
        cases[cle] = f"$D${ligne}"
        valeurApp = _nombre(valeurApp)
        if isinstance(valeurApp, (int, float)) and not (isinstance(valeurApp, float) and math.isnan(valeurApp)):
            _case(ws, f"E{ligne}", valeurApp, fmt=fmt)
            _case(ws, f"F{ligne}", f"=D{ligne}-E{ligne}", fmt="0.0E+00")
            _case(
                ws,
                f"G{ligne}",
                f'=IF(ABS(F{ligne})<={TOLERANCE_RELATIVE}*MAX(1,ABS(E{ligne})),"OK","ÉCART")',
            )
        ligne += 1

    resultat("nom", "Jeu nominal", f"={nom}", res["CF_nom"])
    resultat("moy", "Jeu moyen", f"={moy}", res["CF_moy"])
    resultat("demi", "Demi-étendue au pire des cas", f"={demi}", res["CF_max"] - res["CF_moy"])
    resultat("min", "Jeu mini au pire des cas", f"={cases['moy']}-{cases['demi']}", res["CF_min"])
    resultat("max", "Jeu maxi au pire des cas", f"={cases['moy']}+{cases['demi']}", res["CF_max"])

    def verdict(lo, hi):
        """Même test que le verdict du site : une limite absente ne borne pas."""
        return (
            f"=IF(AND(OR(NOT(ISNUMBER({jmin})),{lo}>={jmin}),OR(NOT(ISNUMBER({jmax})),{hi}<={jmax})),"
            '"Conforme","Non conforme")'
        )

    resultat("verdictWc", "Verdict au pire des cas", verdict(cases["min"], cases["max"]), None, fmt="General")
    resultat("sigma", "σ du jeu", f"=SQRT({var})", res["CF_sigma"], "0.000000")
    resultat(
        "rmin", "Jeu mini statistique (moyenne − kσ)", f"={cases['moy']}-{k}*{cases['sigma']}", v and v["rssK"]["min"]
    )
    resultat(
        "rmax", "Jeu maxi statistique (moyenne + kσ)", f"={cases['moy']}+{k}*{cases['sigma']}", v and v["rssK"]["max"]
    )
    resultat("verdictRss", "Verdict statistique ± kσ", verdict(cases["rmin"], cases["rmax"]), None, fmt="General")
    # le décentrage se calcule à partir de la moyenne déjà décalée par les moyennes mesurées (comme solveurChaine)
    resultat("decReel", "Décalage dû aux moyennes mesurées", f"={ecartMesure}", res["decalage_reel"])
    moyMesuree = f"({cases['moy']}+{cases['decReel']})"
    dmin = f"IF(ISNUMBER({jmin}),{moyMesuree}-{jmin},1E+99)"
    dmax = f"IF(ISNUMBER({jmax}),{jmax}-{moyMesuree},1E+99)"
    sans_limite = f"AND(NOT(ISNUMBER({jmin})),NOT(ISNUMBER({jmax})))"
    resultat(
        "decalage",
        "Décalage de la moyenne (mesures et décentrage)",
        f"={cases['decReel']}+IF(OR({dec}<=0,{sans_limite}),0,"
        f"IF({dmin}<={dmax},-{dec}*{cases['sigma']},{dec}*{cases['sigma']}))",
        res["decalage"],
    )
    resultat("mu", "Moyenne du procédé", f"={cases['moy']}+{cases['decalage']}", res["CF_moy_proc"])
    s, mu = cases["sigma"], cases["mu"]
    resultat(
        "cp",
        "Cp",
        f'=IF(AND(ISNUMBER({jmin}),ISNUMBER({jmax}),{s}>0),({jmax}-{jmin})/(6*{s}),"")',
        v and v["cp"],
        "0.000",
    )
    resultat(
        "cpk",
        "Cpk",
        f'=IF(OR({s}<=0,{sans_limite}),"",MIN(IF(ISNUMBER({jmin}),({mu}-{jmin})/(3*{s}),1E+99),'
        f"IF(ISNUMBER({jmax}),({jmax}-{mu})/(3*{s}),1E+99)))",
        v and v["cpk"],
        "0.000",
    )
    resultat(
        "ppm",
        "Hors tolérance (ppm, loi normale)",
        f'=IF({s}<=0,"",1E6*(IF(ISNUMBER({jmin}),NORMSDIST(({jmin}-{mu})/{s}),0)'
        f"+IF(ISNUMBER({jmax}),NORMSDIST(({mu}-{jmax})/{s}),0)))",
        v and v["ppm"],
        "0.00",
    )

    ws.freeze_panes = ws.cell(premiere, 3)
    mode = wb.create_sheet("Mode d'emploi")
    mode.column_dimensions["A"].width = 130
    for i, texte in enumerate(MODE_EMPLOI, start=1):
        mode.cell(i, 1, texte).alignment = Alignment(wrap_text=True, vertical="top")
    tampon = io.BytesIO()
    wb.save(tampon)
    return tampon.getvalue()
