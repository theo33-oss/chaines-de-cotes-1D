"""Bibliothèque d'exemples : ceux de l'application MATLAB (data/exemples.json, avec références MATLAB) puis les
exemples pédagogiques du site (data/exemples_atelier.json, sans référence MATLAB)."""

import copy

from chainecotes.core.donnees import chargerJson
from chainecotes.core.errors import ErreurChaine

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
