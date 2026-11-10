"""Bibliothèque d'exemples : ceux de l'application MATLAB (data/exemples.json, avec références MATLAB) puis les
exemples pédagogiques du site (data/exemples_atelier.json, sans référence MATLAB)."""

import copy
import math

from chainecotes.core.donnees import chargerJson
from chainecotes.core.errors import ErreurChaine
from chainecotes.plots._common import intervalle

FICHIERS = ("exemples.json", "exemples_atelier.json")
_PRESENTATION = ("id", "titre", "description", "source", "methodologie")


def _tous() -> list[dict]:
    """Tous les exemples des fichiers de FICHIERS, dans l'ordre."""
    return [e for f in FICHIERS for e in chargerJson(f)["exemples"]]


def listeExemples() -> list[dict]:
    """Liste des exemples disponibles.

    Sortie : liste de dict id, titre, description, source (textes), dans l'ordre des fichiers ; la clé
    « methodologie » (liste de textes, étapes à suivre de page en page) n'est présente que pour les exemples qui en ont.
    """
    return [{k: e[k] for k in _PRESENTATION if k in e} for e in _tous()]


def chargerExemple(identifiant: str) -> dict:
    """Problème d'un exemple, prêt à être calculé ou modifié.

    Entrée : identifiant de l'exemple (champ « id » des fichiers d'exemples).
    Sortie : problème (dict condition, reglages, maillons), copie indépendante du fichier.
    Erreur : ErreurChaine si l'identifiant est inconnu.
    """
    for e in _tous():
        if e["id"] == identifiant:
            return copy.deepcopy({k: v for k, v in e.items() if k not in _PRESENTATION})
    raise ErreurChaine("Chaine:Exemples:inconnu", f"Exemple inconnu : {identifiant!r}.")


def texteCondition(condition: dict) -> str:
    """Cote condition écrite en clair : nom et intervalle [Jmin ; Jmax] en mm (côté sans limite ouvert).

    Entrée : condition (dict nom, jmin, jmax en mm ou None). Sortie : texte.
    """
    jmin = -math.inf if condition.get("jmin") is None else condition["jmin"]
    jmax = math.inf if condition.get("jmax") is None else condition["jmax"]
    return f"{condition['nom']} attendu dans {intervalle(jmin, jmax)} mm"


def lignesMaillons(probleme: dict, apercu: dict) -> list[dict]:
    """Lignes de présentation des maillons d'un problème (écarts lus dans l'aperçu calculé s'il existe).

    Entrées : probleme (dict condition, reglages, maillons), apercu (sortie de apercuChaine).
    Sortie : liste de dict Maillon, Sens, Cote (mm), ISO, ES (mm), EI (mm), Loi, Matériau, T service (°C).
    """
    calcules = apercu["res"]["maillons"] if "res" in apercu else probleme["maillons"]
    return [
        {
            "Maillon": m["nom"],
            "Sens": "−" if m["sens"] == "-" else "+",
            "Cote (mm)": m["cote"],
            "ISO": m["iso"] or "",
            "ES (mm)": m["es"],
            "EI (mm)": m["ei"],
            "Loi": m["loi"],
            "Matériau": m["materiau"] or "",
            "T service (°C)": m["tservice"],
        }
        for m in calcules
    ]
