"""État de la fenêtre : problème courant (partagé par les pages) et dernier résultat.

`v` garde aussi les valeurs des champs de saisie, par clé : elles survivent au changement de page.
"""

import copy
from datetime import datetime
from typing import Any

from chainecotes.core.chaine import libelleVerdict
from chainecotes.services.exemples import chargerExemple

EXEMPLE_DEPART = "tableau_depart"
PREFIXE_EDITEUR = "editeur."  # clés des champs des éditeurs, oubliées quand le problème est remplacé
HISTORIQUE_MAX = 20
v: dict[str, Any] = {}


def init() -> None:
    """Initialise une seule fois le problème courant (exemple « tableau_depart ») et le résultat (aucun)."""
    v.setdefault("probleme", None)
    if v["probleme"] is None:
        v["probleme"] = chargerExemple(EXEMPLE_DEPART)
    v.setdefault("resultat", None)
    v.setdefault("historique", [])
    v.setdefault("revisions", [])
    v.setdefault("chemin", None)
    v.setdefault("etude", 0)
    if "reference" not in v:
        v["reference"] = _instantane()


def _instantane() -> tuple:
    return copy.deepcopy((v["probleme"], v["revisions"]))


def chemin() -> str | None:
    """Fichier .json de l'étude en cours, ou None si elle n'a jamais été enregistrée."""
    init()
    return v["chemin"]


def modifiee() -> bool:
    """Vrai si l'étude (problème, révisions) a changé depuis son ouverture ou son dernier enregistrement."""
    init()
    return v["reference"] != (v["probleme"], v["revisions"])


def etudeEnregistree(fichier: str) -> None:
    """L'étude vient d'être écrite dans fichier : elle n'est plus « modifiée »."""
    init()
    v["chemin"], v["reference"] = fichier, _instantane()


def nouvelleEtude(fichier: str | None = None, propre: bool = True) -> None:
    """Une autre étude remplace la précédente (fichier ouvert, exemple chargé) : l'annulation repart de zéro.

    Entrées : fichier (chemin du .json ouvert, None pour une étude sans fichier), propre (False : travail à
    enregistrer, par exemple une chaîne bâtie par l'assistant).
    """
    init()
    v["etude"] += 1
    v["chemin"], v["reference"] = fichier, _instantane() if propre else None


def probleme() -> dict:
    """Problème courant, modifiable sur place par les éditeurs.

    Sortie : dict condition, reglages, maillons (longueurs en mm).
    """
    init()
    return v["probleme"]


def definirProbleme(p: dict) -> None:
    """Remplace le problème courant et oublie l'état des éditeurs (ils repartent du nouveau problème).

    Entrée : p (dict condition, reglages, maillons). Sortie : aucune.
    """
    v["probleme"] = p
    for cle in [k for k in v if str(k).startswith(PREFIXE_EDITEUR)]:
        del v[cle]


def resultat() -> dict | None:
    """Dernier résultat calculé : bundle de chainecotes.services.calcul.calculerChaine, ou None."""
    init()
    return v["resultat"]


def definirResultat(bundle: dict) -> None:
    """Enregistre le dernier résultat calculé. Entrée : bundle (sortie de calculerChaine)."""
    v["resultat"] = bundle


def sansCartouche(p: dict) -> dict:
    """Problème sans son cartouche : le cartouche décrit le dossier, il ne change pas le calcul.

    Entrée : p (dict condition, reglages, maillons et, facultatif, cartouche). Sortie : copie superficielle de p.
    """
    return {k: x for k, x in p.items() if k != "cartouche"}


def effacerResultat() -> None:
    """Oublie le dernier résultat calculé (par exemple après le chargement d'un autre problème)."""
    v["resultat"] = None


def ajouterHistorique(bundle: dict, n: int, graine: int) -> None:
    """Ajoute un calcul réalisé à l'historique (les HISTORIQUE_MAX plus récents sont gardés).

    Entrées : bundle (sortie de calculerChaine), n (tirages Monte-Carlo), graine (entier). Sortie : aucune.
    Chaque entrée garde la saisie du problème, pour pouvoir le recharger, et les grandeurs clés du résultat.
    """
    init()
    verdicts, c = bundle["verdicts"], bundle["res"]["condition"]
    entree = {
        "heure": datetime.now().strftime("%H:%M:%S"),
        "nom": bundle["probleme"]["condition"].get("nom") or "Jeu J",
        "nMaillons": len(bundle["probleme"]["maillons"]),
        "jeuMin": verdicts["pireCas"]["min"],
        "jeuMax": verdicts["pireCas"]["max"],
        "verdict": libelleVerdict(verdicts["pireCas"]["ok"], c),
        "ppm": verdicts["ppm"],
        "cpk": verdicts["cpk"],
        "tirages": n,
        "graine": graine,
        "probleme": copy.deepcopy(bundle["probleme"]),
    }
    v["historique"] = (v["historique"] + [entree])[-HISTORIQUE_MAX:]


def revisions() -> list[dict]:
    """Révisions enregistrées pour l'étude en cours (liste de dict indice, date, auteur, objet, probleme)."""
    init()
    return v["revisions"]


def definirRevisions(liste: list[dict]) -> None:
    """Remplace les révisions de l'étude (par exemple à l'ouverture d'un fichier). Entrée : liste de dict."""
    init()
    v["revisions"] = liste


def historique() -> list[dict]:
    """Calculs réalisés depuis l'ouverture, du plus ancien au plus récent (voir ajouterHistorique)."""
    init()
    return v["historique"]
