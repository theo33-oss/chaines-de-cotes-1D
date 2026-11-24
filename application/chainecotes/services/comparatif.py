"""Comparaison de plusieurs chaînes de cotes 1D côte à côte (une colonne = un problème à une cote condition).

Chaque colonne est calculée par calculerChaine ; une colonne en erreur n'empêche pas les autres. Les tirages
Monte-Carlo sont partagés entre les colonnes comme dans le mécanisme (services/mecanisme.py). Ce module n'importe
ni Qt, ni Plotly, ni pandas : le résultat se sérialise en JSON (sauf la clé « _bundles », voir comparerColonnes).
"""

import copy
import csv
import io
import math

from chainecotes.core.chaine import sansLimite
from chainecotes.core.errors import ErreurChaine
from chainecotes.core.montecarlo import GRAINE_DEFAUT
from chainecotes.core.nombres import fr, ppmLisible, versTableur
from chainecotes.services.calcul import calculerChaine
from chainecotes.services.mecanisme import TIRAGES_PAR_CHAINE_MINI, TIRAGES_TOTAUX_MAX

MAX_COLONNES = 12
_ID = "Chaine:Comparatif:invalide"
_VIDE = "—"

# (groupe, libellé, clé de la case, sens, écart, format)
#   sens : +1 = plus grand est meilleur, -1 = plus petit est meilleur, 0 = pas de meilleur (non comparable)
#   écart : "abs" (différence), "rel" (en % de la référence) ou None (pas d'écart : texte ou oui/non)
_LIGNES = [
    ("Exigence", "Jmin exigé (mm)", "jminExige", 0, "abs", ".4f"),
    ("Exigence", "Jmax exigé (mm)", "jmaxExige", 0, "abs", ".4f"),
    ("Résultat au pire des cas", "Jeu nominal (mm)", "nominal", 0, "abs", ".4f"),
    ("Résultat au pire des cas", "Jeu moyen (mm)", "moyen", 0, "abs", ".4f"),
    ("Résultat au pire des cas", "Pire cas mini (mm)", "pireMini", 0, "abs", ".4f"),
    ("Résultat au pire des cas", "Pire cas maxi (mm)", "pireMaxi", 0, "abs", ".4f"),
    ("Résultat au pire des cas", "Conforme au pire des cas", "conformePireCas", 1, None, ""),
    ("Statistique", "Mini à ±kσ (mm)", "statMini", 0, "abs", ".4f"),
    ("Statistique", "Maxi à ±kσ (mm)", "statMaxi", 0, "abs", ".4f"),
    ("Statistique", "Conforme en statistique", "conformeStat", 1, None, ""),
    ("Statistique", "σ du jeu (mm)", "sigma", -1, "abs", ".4f"),
    ("Capabilité et risque", "Cp", "cp", 1, "abs", ".3g"),
    ("Capabilité et risque", "Cpk", "cpk", 1, "abs", ".3g"),
    ("Capabilité et risque", "Hors tolérance, formule (ppm)", "ppmFormule", -1, "rel", ".4g"),
    ("Capabilité et risque", "Hors tolérance, Monte-Carlo (ppm)", "ppmMonteCarlo", -1, "rel", ".4g"),
    ("Chaîne", "Nombre de maillons", "nMaillons", 0, "abs", ".0f"),
    ("Chaîne", "Maillon dominant", "dominant", 0, None, ""),
    ("Chaîne", "Part de variance du maillon dominant (%)", "partDominant", 0, "abs", ".1f"),
    ("Chaîne", "Nombre de lois non normales", "nNonNormales", 0, "abs", ".0f"),
]
_CONFORMITE = {"conformePireCas", "conformeStat"}


def _erreur(message: str) -> ErreurChaine:
    return ErreurChaine(_ID, message)


def _fini(x) -> float | None:
    """Nombre fini en float, sinon None (nan, infini, absent)."""
    try:
        return float(x) if x is not None and math.isfinite(float(x)) else None
    except (TypeError, ValueError):
        return None


def _nombre(x, fmt: str) -> tuple[str, float | None]:
    """Case numérique : (texte à la française, nombre fini ou None) ; « — » si le nombre n'existe pas."""
    f = _fini(x)
    if f is not None:
        return fr(f, fmt), f
    if isinstance(x, float) and math.isinf(x):  # limite absente : « −∞ » / « +∞ », pas de nombre
        return fr(x, fmt), None
    return _VIDE, None


def _ouiNon(ok: bool, condition: dict) -> tuple[str, float | None]:
    if sansLimite(condition):
        return "sans limite", None
    return ("oui", 1.0) if ok else ("non", 0.0)


def _noms(colonnes: list[dict]) -> list[str]:
    """Noms uniques : vide → « Chaîne i », doublon → « Nom (2) », « Nom (3) »…"""
    vus: set[str] = set()
    sortie = []
    for i, c in enumerate(colonnes, start=1):
        nom = c.get("nom") if isinstance(c, dict) else None
        base = nom.strip() if isinstance(nom, str) and nom.strip() else f"Chaîne {i}"
        candidat, k = base, 1
        while candidat in vus:
            k += 1
            candidat = f"{base} ({k})"
        vus.add(candidat)
        sortie.append(candidat)
    return sortie


def _verdict(bundle: dict) -> tuple[str, str, str]:
    """(verdict, niveau, détail) d'une colonne calculée."""
    v, c = bundle["verdicts"], bundle["res"]["condition"]
    if sansLimite(c):
        return "indicatif", "info", "sans limite sur la cote condition"
    if v["pireCas"]["ok"]:
        return "conforme", "succes", "conforme au pire des cas"
    if v["rssK"]["ok"] and v["rssProc"]["ok"]:
        return "conforme", "avertissement", "conforme en statistique seulement"
    return "non conforme", "erreur", "non conforme"


def _cases(bundle: dict) -> dict[str, tuple[str, float | None]]:
    """Toutes les cases d'une colonne calculée : clé → (texte, nombre ou None)."""
    res, v, mc = bundle["res"], bundle["verdicts"], bundle["mc"]
    c = res["condition"]
    sigma = float(res["CF_sigma"])
    contribs = bundle["contributions"]
    dominant, part = None, None
    if contribs:
        cle = "partVariance" if sigma > 0 else "partPireCas"
        d = max(contribs, key=lambda x: x[cle])
        dominant = d["nom"]
        part = d["partVariance"] if sigma > 0 else None
    if mc is None:
        ppmMc = (_VIDE, None)
    elif mc["nHors"] == 0:
        ppmMc = (f"< {ppmLisible(mc['resolutionPpm'], False)}", 0.0)
    else:
        ppmMc = (ppmLisible(mc["ppm"], False), _fini(mc["ppm"]))
    ppm = _fini(v["ppm"])
    return {
        "jminExige": _nombre(c["jmin"], ".4f"),
        "jmaxExige": _nombre(c["jmax"], ".4f"),
        "nominal": _nombre(res["CF_nom"], ".4f"),
        "moyen": _nombre(res["CF_moy"], ".4f"),
        "pireMini": _nombre(v["pireCas"]["min"], ".4f"),
        "pireMaxi": _nombre(v["pireCas"]["max"], ".4f"),
        "conformePireCas": _ouiNon(v["pireCas"]["ok"], c),
        "statMini": _nombre(v["rssProc"]["min"], ".4f"),
        "statMaxi": _nombre(v["rssProc"]["max"], ".4f"),
        "conformeStat": _ouiNon(v["rssK"]["ok"] and v["rssProc"]["ok"], c),
        "sigma": _nombre(sigma, ".4f"),
        "cp": _nombre(v["cp"], ".3g"),
        "cpk": _nombre(v["cpk"], ".3g"),
        "ppmFormule": (ppmLisible(ppm, False), ppm),
        "ppmMonteCarlo": ppmMc,
        "nMaillons": (str(len(res["Nom"])), float(len(res["Nom"]))),
        "dominant": (dominant if dominant else _VIDE, None),
        "partDominant": _nombre(part, ".1f"),
        "nNonNormales": (
            str(sum(1 for x in res["loi"] if x != "normale")),
            float(sum(1 for x in res["loi"] if x != "normale")),
        ),
    }


def _ecart(v: float | None, ref: float | None, mode: str | None, fmt: str) -> str | None:
    """Écart d'une case à la référence : « +0,12 » (absolu) ou « +12 % » (relatif) ; « 0 » si rien ne change."""
    if mode is None or v is None or ref is None:
        return None
    d = v - ref
    if mode == "rel" and ref != 0:
        if abs(v / ref) >= 100 or abs(v / ref) <= 0.01:  # un pourcentage de plusieurs millions ne se lit pas : facteur
            return f"× {fr(v / ref, '.2g')}" if v != 0 else "× 0"
        pct = 100 * d / abs(ref)
        f = ".0f" if abs(pct) >= 10 else ".1f"
        if float(format(pct, f)) == 0:
            return "0 %"
        return ("+" if pct > 0 else "") + fr(pct, f) + " %"
    if float(format(d, fmt)) == 0:
        return "0"
    return ("+" if d > 0 else "") + fr(d, fmt)


def _meilleurs(nombres: list[float | None], sens: int) -> list[int]:
    """Indices des colonnes à la meilleure valeur (vide si non comparable ou si toutes les valeurs sont égales)."""
    avec = [(j, x) for j, x in enumerate(nombres) if x is not None]
    if sens == 0 or len(avec) < 2:
        return []
    cible = max(x for _, x in avec) if sens > 0 else min(x for _, x in avec)
    if all(math.isclose(x, cible, rel_tol=1e-12, abs_tol=1e-12) for _, x in avec):
        return []
    return [j for j, x in avec if math.isclose(x, cible, rel_tol=1e-12, abs_tol=1e-12)]


def _garde(texte: str) -> str:
    """Neutralise un texte saisi qui serait lu comme une formule par le tableur (« =… », « +… », « @… »)."""
    return "'" + texte if texte[:1] in ("=", "+", "-", "@") else texte


def _tableau(colonnes: list[dict], lignes: list[dict]) -> list[list[str]]:
    """Lignes de texte du tableau exporté : en-tête, verdicts, erreurs éventuelles, puis les grandeurs."""
    t = [["Grandeur"] + [_garde(c["nom"]) for c in colonnes], ["Verdict"] + [c["verdict"] for c in colonnes]]
    if any(c["erreur"] for c in colonnes):
        t.append(["Erreur"] + [_garde(c["erreur"] or "") for c in colonnes])
    for ligne in lignes:
        garde = _garde if ligne["libelle"] == "Maillon dominant" else str
        t.append([ligne["libelle"]] + ["" if x is None else garde(x) for x in ligne["valeurs"]])
    return [[versTableur(case.replace("\t", " ").replace("\n", " ")) for case in rang] for rang in t]


def _csv(tableau: list[list[str]]) -> str:
    sortie = io.StringIO()
    csv.writer(sortie, delimiter=";", lineterminator="\r\n").writerows(tableau)
    return "﻿" + sortie.getvalue()


def comparerColonnes(
    colonnes: list[dict], reference: int = 0, n: int = 100_000, graine: int = GRAINE_DEFAUT
) -> dict:
    """Calcule N chaînes de cotes et les met en colonnes (une colonne = un problème à une cote condition).

    Entrées : colonnes (liste de dict nom, probleme ; 1 à 12 colonnes), reference (indice de la colonne de
    référence, à partir de 0), n (tirages Monte-Carlo par colonne, réduits si beaucoup de colonnes : 2 000 000
    au total, 20 000 au plus bas), graine (entier).
    Sortie : dict
      colonnes : liste de {nom (unique), erreur (message ou None), verdict « conforme » | « non conforme » |
        « indicatif » (aucune limite) | « erreur », niveau « succes » | « avertissement » | « erreur » | « info »,
        detail (texte)} ;
      reference : indice de la colonne de référence ;
      lignes : liste de {groupe, libelle (unité comprise), valeurs (texte français ou None si colonne en erreur),
        nombres (float ou None), meilleur (indice de la meilleure colonne ou None si non comparable ou égalité),
        ecarts (écart à la référence : « +0,12 », « +12 % » ; None pour la référence, le texte et l'erreur),
        identique (toutes les colonnes calculées ont la même valeur)} ;
      classes : une liste par ligne, une classe par colonne : « erreur » (colonne en erreur), « vide »,
        « succes » / « erreur » (lignes de conformité oui / non), « meilleur » (meilleure valeur), sinon « » ;
      csv : texte « ; » qui commence par la marque UTF-8 (BOM), une colonne par chaîne ;
      texte : même tableau séparé par des tabulations, à coller dans un tableur ;
      nTirages : tirages Monte-Carlo réellement utilisés par chaîne ;
      _bundles : liste (un bundle de calculerChaine ou None par colonne) pour les graphiques. Non sérialisable :
        l'appelant la retire (resultat.pop("_bundles")) après figuresComparatif et avant tout JSON.
    Une colonne en erreur (ErreurChaine, saisie incomplète) garde son rang, avec des cases vides.
    Erreur : ErreurChaine s'il y a moins d'une ou plus de 12 colonnes, ou si la référence est hors liste.
    """
    colonnes = list(colonnes or [])
    if not colonnes:
        raise _erreur("Comparaison impossible : aucune chaîne à comparer.")
    if len(colonnes) > MAX_COLONNES:
        raise _erreur(f"Trop de chaînes à comparer ({len(colonnes)}) : {MAX_COLONNES} au plus.")
    if not isinstance(reference, int) or not 0 <= reference < len(colonnes):
        raise _erreur(f"Chaîne de référence invalide : {reference!r} (0 à {len(colonnes) - 1}).")
    noms = _noms(colonnes)
    nEff = min(n, max(TIRAGES_PAR_CHAINE_MINI, TIRAGES_TOTAUX_MAX // len(colonnes)))
    entetes, bundles, cases = [], [], []
    for nom, col in zip(noms, colonnes, strict=True):
        message, bundle = None, None
        probleme = col.get("probleme") if isinstance(col, dict) else None
        if not isinstance(probleme, dict):
            message = "Saisie incomplète : aucun problème à calculer."
        else:
            try:
                bundle = calculerChaine(copy.deepcopy(probleme), True, nEff, graine)
            except ErreurChaine as e:
                message = e.message
            except (TypeError, ValueError, KeyError, AttributeError) as e:
                message = f"Saisie incomplète : {e}"
        if bundle is None:
            entetes.append(
                {"nom": nom, "erreur": message, "verdict": "erreur", "niveau": "erreur", "detail": "erreur de calcul"}
            )
            cases.append(None)
        else:
            verdict, niveau, detail = _verdict(bundle)
            entetes.append({"nom": nom, "erreur": None, "verdict": verdict, "niveau": niveau, "detail": detail})
            cases.append(_cases(bundle))
        bundles.append(bundle)

    refValide = cases[reference] is not None
    lignes, classes = [], []
    for groupe, libelle, cle, sens, mode, fmt in _LIGNES:
        valeurs = [None if c is None else c[cle][0] for c in cases]
        nombres = [None if c is None else c[cle][1] for c in cases]
        calcules = [x for x in valeurs if x is not None]
        meilleurs = _meilleurs(nombres, sens)
        ecarts = [
            None
            if j == reference or not refValide or nombres[j] is None
            else _ecart(nombres[j], nombres[reference], mode, fmt)
            for j in range(len(cases))
        ]
        lignes.append(
            {
                "groupe": groupe,
                "libelle": libelle,
                "valeurs": valeurs,
                "nombres": nombres,
                "meilleur": meilleurs[0] if meilleurs else None,
                "ecarts": ecarts,
                "identique": len(calcules) >= 2 and len(set(calcules)) == 1,
            }
        )
        classe = []
        for j, c in enumerate(cases):
            if c is None:
                classe.append("erreur")
            elif valeurs[j] == _VIDE:
                classe.append("vide")
            elif cle in _CONFORMITE:
                classe.append({"oui": "succes", "non": "erreur"}.get(valeurs[j], ""))
            else:
                classe.append("meilleur" if j in meilleurs else "")
        classes.append(classe)

    tableau = _tableau(entetes, lignes)
    return {
        "colonnes": entetes,
        "reference": reference,
        "lignes": lignes,
        "classes": classes,
        "csv": _csv(tableau),
        "texte": "\n".join("\t".join(rang) for rang in tableau),
        "nTirages": nEff,
        "_bundles": bundles,
    }
