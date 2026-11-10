"""Import des maillons d'une chaîne depuis un tableau : fichier csv ou xlsx, ou texte copié depuis Excel.

Les titres de colonnes sont reconnus sans tenir compte des accents, des majuscules ni des unités entre parenthèses
(« Cote nominale (mm) », « ES », « Écart supérieur »…). Une feuille exportée par services/feuille_chaine se relit
telle quelle. Ce module n'importe ni streamlit ni plotly.
"""

import csv
import io
import re
import unicodedata

from openpyxl import load_workbook

from chainecotes.core.chaine import LOIS, estVide
from chainecotes.core.errors import ErreurChaine
from chainecotes.core.iso286 import lireDesignation
from chainecotes.core.materiaux import nomsMateriaux
from chainecotes.services.projet_io import MAX_MAILLONS, MAX_TEXTE

TAILLE_MAX = 2_000_000  # octets : un fichier de maillons est minuscule, au-delà c'est autre chose
LIGNES_MAX = 2000  # lignes lues au plus dans un classeur
LIGNES_ENTETE = 30  # l'en-tête est cherché dans les premières lignes (une feuille a souvent un titre au-dessus)

# titre de colonne normalisé → champ du maillon
SYNONYMES = {
    "nom": ("nom", "maillon", "designation", "repere", "piece", "description", "libelle"),
    "sens": ("sens", "signe", "direction"),
    "cote": ("cote", "cote nominale", "cote nom", "nominal", "dimension", "valeur"),
    "iso": ("iso", "iso 286", "ajustement", "classe", "designation iso", "tolerance iso"),
    "es": ("es", "ecart superieur", "ecart sup", "tol+", "tol +", "+tol", "+ tol", "tolerance sup", "tolerance +"),
    "ei": ("ei", "ecart inferieur", "ecart inf", "tol-", "tol -", "-tol", "- tol", "tolerance inf", "tolerance -"),
    "tolerance": ("pm tol", "pm tolerance", "pm", "tolerance symetrique", "tolerance +/-", "tol sym"),
    "it": ("it", "intervalle de tolerance"),
    "loi": ("loi", "distribution"),
    "materiau": ("materiau", "matiere"),
    "alpha": ("alpha", "α", "dilatation", "coefficient de dilatation"),
    "tservice": ("t service", "tservice", "temperature", "temperature de service", "t"),
    "derive": ("derive",),
    "facteur": ("facteur", "levier"),
    "angle": ("angle",),
    "sigma_reel": ("sigma reel", "sigma mesure", "σ mesure", "ecart type mesure", "ecart type reel", "sigma atelier"),
    "moyenne_reelle": ("moyenne reelle", "moyenne mesuree", "moyenne atelier"),
}
_CHAMP = {titre: champ for champ, titres in SYNONYMES.items() for titre in titres}
_SENS = {"+": "+", "plus": "+", "positif": "+", "1": "+", "-": "-", "moins": "-", "negatif": "-", "-1": "-"}
_LOIS = {
    "normale": "normale",
    "normal": "normale",
    "gauss": "normale",
    "gaussienne": "normale",
    "uniforme": "uniforme",
    "uniform": "uniforme",
    "triangulaire": "triangulaire",
    "triangle": "triangulaire",
}
MODELE_CSV = (
    "Maillon;Sens;Cote nominale (mm);ISO 286;ES (mm);EI (mm);Loi;Matériau;T service (°C)\r\n"
    "Alésage du carter;+;40;H7;;;normale;;\r\n"
    "Épaisseur de la cale;-;1,5;;0,02;-0,02;uniforme;;\r\n"
    "Longueur de l'arbre;-;38,5;;0;-0,1;normale;Acier C45;\r\n"
).encode("utf-8-sig")


def _sans_accent(texte) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(texte)) if unicodedata.category(c) != "Mn")


def _titre(cellule) -> str:
    """Titre de colonne normalisé : minuscules, sans accent, sans unité entre parenthèses, espaces réduits."""
    t = _sans_accent(cellule).lower().replace("±", "pm ").replace("_", " ").replace("°", "")
    return re.sub(r"\s+", " ", re.sub(r"\([^)]*\)", "", t)).strip()


def _nombre(valeur) -> float:
    """Nombre d'une cellule : virgule ou point décimal, espaces et signe moins typographique tolérés (ValueError)."""
    if isinstance(valeur, (int, float)) and not isinstance(valeur, bool):
        return float(valeur)
    t = re.sub(r"[\s  ]", "", str(valeur)).replace("−", "-").replace("–", "-")
    if "," in t and "." in t:  # le dernier séparateur est le décimal : 1.234,5 ou 1,234.5
        t = t.replace(".", "").replace(",", ".") if t.rfind(",") > t.rfind(".") else t.replace(",", "")
    return float(t.replace(",", "."))


def _lignesTexte(texte: str) -> list[list[str]]:
    """Cellules d'un texte csv ou collé : séparateur tabulation, point-virgule ou virgule (le plus fréquent d'abord)."""
    lignes = [ln for ln in texte.replace("\r\n", "\n").replace("\r", "\n").split("\n") if ln.strip()]
    if not lignes:
        return []
    entete = lignes[0]
    separateur = max(("\t", ";", ","), key=entete.count) if any(s in entete for s in "\t;,") else ";"
    return [list(r) for r in csv.reader(lignes, delimiter=separateur)]


def _lignesXlsx(contenu: bytes) -> list[list]:
    try:
        classeur = load_workbook(io.BytesIO(contenu), read_only=True, data_only=True)
    except Exception as e:  # noqa: BLE001 : openpyxl lève des erreurs variées sur un fichier abîmé
        raise ErreurChaine("Chaine:Import:illisible", f"Classeur Excel illisible ({type(e).__name__}).") from e
    feuille = classeur.worksheets[0]
    lignes = []
    for i, ligne in enumerate(feuille.iter_rows(values_only=True)):
        if i >= LIGNES_MAX:
            break
        lignes.append(list(ligne))
    classeur.close()
    return lignes


def _enteteEtColonnes(lignes: list[list]) -> tuple[int, dict[str, int]]:
    """Indice de la ligne d'en-tête et colonne de chaque champ reconnu ; ErreurChaine si aucun en-tête n'est lisible."""
    for i, ligne in enumerate(lignes[:LIGNES_ENTETE]):
        colonnes = {}
        for j, cellule in enumerate(ligne):
            champ = _CHAMP.get(_titre(cellule)) if not estVide(cellule) else None
            if champ and champ not in colonnes:
                colonnes[champ] = j
        if "cote" in colonnes or "iso" in colonnes:
            return i, colonnes
    accepte = ", ".join(
        f"{c} ({' / '.join(t[:2])})" for c, t in SYNONYMES.items() if c in ("nom", "sens", "cote", "es")
    )
    raise ErreurChaine(
        "Chaine:Import:entete",
        "Aucune ligne de titres reconnue : la première ligne doit nommer les colonnes, au moins la cote nominale "
        f"ou la désignation ISO. Titres acceptés, par exemple : {accepte}. Un modèle est téléchargeable.",
    )


def _maillon(ligne: list, colonnes: dict[str, int], numero: int, materiaux: dict[str, str]) -> tuple[dict, list[str]]:
    """Maillon d'une ligne du tableau et ses erreurs (messages avec le numéro de ligne)."""
    erreurs = []

    def cellule(champ):
        j = colonnes.get(champ)
        return ligne[j] if j is not None and j < len(ligne) and not estVide(ligne[j]) else None

    def nombre(champ, quoi):
        v = cellule(champ)
        if v is None:
            return None
        try:
            return _nombre(v)
        except ValueError:
            erreurs.append(f"Ligne {numero} : {quoi} « {v} » n'est pas un nombre.")
            return None

    m = {"nom": str(cellule("nom") or f"Maillon {numero}").strip()[:MAX_TEXTE]}
    cote = nombre("cote", "la cote")
    iso = None if cellule("iso") is None else str(cellule("iso")).strip()
    if cote is None and iso:
        try:
            cote = lireDesignation(iso)["cote"]
        except ErreurChaine:
            cote = None
    sens = cellule("sens")
    if sens is not None:
        sens = _SENS.get(_sans_accent(str(sens)).lower().replace("−", "-").strip())
        if sens is None:
            erreurs.append(f"Ligne {numero} : le sens « {cellule('sens')} » doit être + ou -.")
    if cote is not None and cote < 0:  # cote signée : le signe donne le sens
        cote = -cote
        if cellule("sens") is None:
            sens = "-"
    m["sens"] = sens or "+"
    if cote is None:
        erreurs.append(f"Ligne {numero} : la cote nominale est absente (ni colonne cote, ni cote dans l'ISO).")
    m["cote"] = cote
    es, ei = nombre("es", "l'écart supérieur"), nombre("ei", "l'écart inférieur")
    tol, it = nombre("tolerance", "la tolérance ±"), nombre("it", "l'IT")
    if iso:
        try:
            lireDesignation(iso, cote)
        except ErreurChaine as e:
            erreurs.append(f"Ligne {numero} : {e.message}")
    elif es is None and ei is None and (tol is not None or it is not None):
        demi = abs(tol) if tol is not None else abs(it) / 2  # tolérance symétrique autour de la cote
        es, ei = demi, -demi
    elif es is None or ei is None:
        erreurs.append(
            f"Ligne {numero} : donner la désignation ISO, ou ES et EI, ou une colonne « ± tolérance » ou « IT »."
        )
    m.update(iso=iso or None, es=None if iso else es, ei=None if iso else ei)
    loi = cellule("loi")
    if loi is not None:
        loi = _LOIS.get(_sans_accent(str(loi)).lower().strip())
        if loi not in LOIS:
            erreurs.append(
                f"Ligne {numero} : la loi « {cellule('loi')} » est inconnue (normale, uniforme, triangulaire)."
            )
    m["loi"] = loi or "normale"
    mat = cellule("materiau")
    if mat is not None:
        m["materiau"] = materiaux.get(_sans_accent(str(mat)).lower().strip())
        if m["materiau"] is None:
            erreurs.append(f"Ligne {numero} : le matériau « {mat} » est absent de la bibliothèque (page Matériaux).")
    else:
        m["materiau"] = None
    m["alpha"], m["tservice"] = nombre("alpha", "α"), nombre("tservice", "la température de service")
    for champ, quoi in (
        ("derive", "la dérive"),
        ("facteur", "le facteur"),
        ("angle", "l'angle"),
        ("sigma_reel", "l'écart type mesuré"),
        ("moyenne_reelle", "la moyenne mesurée"),
    ):
        v = nombre(champ, quoi)
        if v is not None:
            m[champ] = v
    if m.get("sigma_reel") is not None and m["sigma_reel"] < 0:
        erreurs.append(f"Ligne {numero} : l'écart type mesuré doit être positif ou nul.")
    if m.get("facteur") is not None and not m["facteur"] > 0:
        erreurs.append(f"Ligne {numero} : le facteur doit être strictement positif.")
    return m, erreurs


def lireMaillons(contenu: bytes | str) -> dict:
    """Maillons lus dans un fichier csv ou xlsx, ou dans un texte collé depuis Excel.

    Entrée : contenu (octets d'un fichier .xlsx ou .csv, ou texte). Un classeur est reconnu à son en-tête « PK ».
    Cotes en mm, α en 1e-6/K, températures en °C.
    Sortie : dict maillons (liste de dict du problème : nom, sens, cote, iso, es, ei, loi, materiau, alpha, tservice,
    et derive, facteur, angle s'ils sont donnés), erreurs (liste de messages avec le numéro de ligne ; vide si tout est
    lisible), colonnes (champs reconnus). Une seule erreur de ligne invalide l'import entier : aucune ligne n'est
    prise à moitié.
    Erreur : ErreurChaine si le contenu est trop gros, illisible, sans en-tête reconnu ou sans maillon.
    """
    if isinstance(contenu, bytes):
        if len(contenu) > TAILLE_MAX:
            raise ErreurChaine(
                "Chaine:Import:taille", f"Fichier trop gros ({len(contenu)} octets, {TAILLE_MAX} au plus)."
            )
        if contenu[:2] == b"PK":
            lignes = _lignesXlsx(contenu)
        else:
            try:
                texte = contenu.decode("utf-8-sig")
            except UnicodeDecodeError:
                texte = contenu.decode("cp1252", errors="replace")
            lignes = _lignesTexte(texte)
    else:
        if len(contenu) > TAILLE_MAX:
            raise ErreurChaine("Chaine:Import:taille", "Texte trop long.")
        lignes = _lignesTexte(contenu)
    if not lignes:
        raise ErreurChaine("Chaine:Import:vide", "Rien à importer : le tableau est vide.")
    debut, colonnes = _enteteEtColonnes(lignes)
    materiaux = {_sans_accent(n).lower(): n for n in nomsMateriaux()}
    maillons, erreurs = [], []
    for i, ligne in enumerate(lignes[debut + 1 :], start=debut + 2):
        if all(estVide(c) for c in ligne):
            if maillons:
                break
            continue
        j, k = colonnes.get("cote"), colonnes.get("iso")
        if all(estVide(ligne[x]) for x in (j, k) if x is not None and x < len(ligne)):
            if maillons:  # fin du tableau (ligne de totaux, notes…)
                break
            continue
        m, e = _maillon(ligne, colonnes, i, materiaux)
        maillons.append(m)
        erreurs += e
    if not maillons:
        raise ErreurChaine("Chaine:Import:vide", "Aucun maillon sous la ligne de titres.")
    if len(maillons) > MAX_MAILLONS:
        raise ErreurChaine("Chaine:Import:taille", f"Trop de maillons ({len(maillons)}, {MAX_MAILLONS} au plus).")
    return {"maillons": maillons, "erreurs": erreurs, "colonnes": sorted(colonnes)}
