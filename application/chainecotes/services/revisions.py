"""Révisions d'une étude : états datés du problème, enregistrés dans le fichier projet, et comparaison de deux états.

Une révision est un instantané du problème (dict indice, date, auteur, objet, probleme). La comparaison donne la liste
des changements de saisie (cote condition, réglages, maillons) puis l'effet sur les résultats (comparerScenarios).
Ce module n'importe ni streamlit ni plotly.
"""

import copy
import math
import string

from chainecotes.core.chaine import estVide
from chainecotes.core.errors import ErreurChaine
from chainecotes.services.calcul import calculerChaine
from chainecotes.services.comparaison import comparerScenarios
from chainecotes.services.projet_io import MAX_REVISIONS_ETUDE, MAX_TEXTE

CHAMPS_MAILLON = {
    "sens": "sens",
    "cote": "cote",
    "iso": "désignation ISO",
    "es": "ES",
    "ei": "EI",
    "loi": "loi",
    "materiau": "matériau",
    "alpha": "α",
    "tservice": "T de service",
    "derive": "dérive",
    "facteur": "facteur",
    "angle": "angle",
    "sigma_reel": "σ mesuré",
    "moyenne_reelle": "moyenne mesurée",
}
CHAMPS_CONDITION = {"nom": "nom", "jmin": "Jmin", "jmax": "Jmax"}
CHAMPS_REGLAGES = {"kSigma": "k", "tref": "T de référence", "modeT": "mode de température",
                   "tservice": "T de service", "decentrage": "décentrage"}  # fmt: skip
ETAT_ACTUEL = "État actuel"


def indiceSuivant(revisions: list[dict]) -> str:
    """Indice de révision qui suit le dernier : A, B… Z, puis A2, B2… ; « A » pour la première.

    Entrée : revisions (liste de dict avec la clé indice). Sortie : texte.
    """
    lettres = string.ascii_uppercase
    n = len(revisions)
    return lettres[n % 26] + ("" if n < 26 else str(n // 26 + 1))


def nouvelleRevision(probleme: dict, indice: str, date: str, auteur: str = "", objet: str = "") -> dict:
    """Révision datée d'un problème (copie profonde).

    Entrées : probleme, indice, date (textes, par exemple « 2026-11-03 »), auteur, objet (textes de 200 caractères
    au plus). Sortie : dict indice, date, auteur, objet, probleme.
    Erreur : ErreurChaine si l'indice est vide ou un texte est trop long.
    """
    champs = {"indice": indice, "date": date, "auteur": auteur, "objet": objet}
    champs = {k: "" if estVide(v) else str(v).strip() for k, v in champs.items()}
    if not champs["indice"]:
        raise ErreurChaine("Chaine:Revision:indice", "L'indice de révision ne peut pas être vide.")
    if any(len(v) > MAX_TEXTE for v in champs.values()):
        raise ErreurChaine(
            "Chaine:Revision:texte", f"Chaque texte de révision tient en {MAX_TEXTE} caractères au plus."
        )
    return {**champs, "probleme": copy.deepcopy(probleme)}


def ajouterRevision(revisions: list[dict], revision: dict) -> list[dict]:
    """Liste de révisions complétée (les anciennes sont gardées). Erreur : ErreurChaine au-delà du maximum."""
    if len(revisions) >= MAX_REVISIONS_ETUDE:
        raise ErreurChaine(
            "Chaine:Revision:trop", f"Trop de révisions ({MAX_REVISIONS_ETUDE} au plus) : supprimez-en une."
        )
    return [*revisions, revision]


def libelleRevision(revision: dict) -> str:
    """Texte court d'une révision pour une liste : « B — 2026-11-03 — objet »."""
    morceaux = [revision["indice"], revision["date"], revision["objet"]]
    return " — ".join(m for m in morceaux if m)


def _valeur(v) -> str:
    if estVide(v):
        return "vide"
    if isinstance(v, float) and math.isfinite(v):
        return f"{v:g}"
    return str(v)


def _changements(a: dict, b: dict, champs: dict, etiquette: str) -> list[str]:
    return [
        f"{etiquette} : {libelle} {_valeur(a.get(cle))} → {_valeur(b.get(cle))}."
        for cle, libelle in champs.items()
        if _valeur(a.get(cle)) != _valeur(b.get(cle))
    ]


def _parNom(maillons: list[dict]) -> dict[str, dict]:
    """Maillons indexés par nom ; un nom répété reçoit un suffixe « (2) », « (3) »…"""
    sortie = {}
    for i, m in enumerate(maillons, start=1):
        nom = str(m.get("nom") or f"Maillon {i}")
        cle, k = nom, 2
        while cle in sortie:
            cle, k = f"{nom} ({k})", k + 1
        sortie[cle] = m
    return sortie


def diffProblemes(a: dict, b: dict) -> list[str]:
    """Changements de saisie entre deux problèmes (A = avant, B = après), en phrases françaises.

    Entrées : a, b (dict condition, reglages, maillons). Les maillons sont appariés par nom.
    Sortie : liste de phrases ; vide si la saisie est identique. Le cartouche n'est pas comparé.
    """
    phrases = _changements(a.get("condition") or {}, b.get("condition") or {}, CHAMPS_CONDITION, "Cote condition")
    phrases += _changements(a.get("reglages") or {}, b.get("reglages") or {}, CHAMPS_REGLAGES, "Réglage")
    ma, mb = _parNom(a.get("maillons") or []), _parNom(b.get("maillons") or [])
    for nom, m in mb.items():
        if nom not in ma:
            phrases.append(f"Maillon ajouté : {nom} (cote {_valeur(m.get('cote'))} mm, sens {m.get('sens', '+')}).")
    for nom, m in ma.items():
        if nom not in mb:
            phrases.append(f"Maillon supprimé : {nom} (cote {_valeur(m.get('cote'))} mm).")
        else:
            phrases += _changements(m, mb[nom], CHAMPS_MAILLON, f"Maillon {nom}")
    ordreA = [n for n in ma if n in mb]
    ordreB = [n for n in mb if n in ma]
    if ordreA != ordreB:
        phrases.append("L'ordre des maillons a changé.")
    return phrases


def comparerRevisions(a: dict, b: dict) -> dict:
    """Compare deux problèmes : changements de saisie et effet sur les résultats (A = référence, B = variante).

    Entrées : a, b (dict condition, reglages, maillons). Les calculs se font sans Monte-Carlo.
    Sortie : dict saisie (liste de phrases, voir diffProblemes) et resultats (sortie de comparerScenarios).
    Erreur : ErreurChaine si l'un des deux problèmes ne se calcule pas (le message précise lequel).
    """
    bundles = []
    for nom, p in (("A", a), ("B", b)):
        try:
            bundles.append(calculerChaine(copy.deepcopy(p), monteCarlo=False))
        except ErreurChaine as e:
            raise ErreurChaine(e.identifiant, f"Problème {nom} : {e.message}") from e
    return {"saisie": diffProblemes(a, b), "resultats": comparerScenarios(*bundles)}
