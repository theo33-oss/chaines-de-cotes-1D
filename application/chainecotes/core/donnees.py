"""Lecture des tables de data/*.json (valeurs numériques de base, jamais recopiées dans le code)."""

import functools
import json
import os
from pathlib import Path

DOSSIER_DONNEES = Path(__file__).resolve().parents[2] / "data"


@functools.cache
def chargerJson(nom: str) -> dict:
    """Charge un fichier de data/ (mis en cache : les tables ne changent pas pendant une session).

    Entrée : nom du fichier (ex. « iso286.json »).
    Sortie : contenu JSON (dict). À ne pas modifier : l'objet est partagé.
    """
    return json.loads((DOSSIER_DONNEES / nom).read_text(encoding="utf-8"))


def ecrireSansPerte(chemin: str | Path, contenu: bytes | str) -> None:
    """Écrit un fichier de l'utilisateur sans jamais abîmer l'ancien : fichier voisin, puis remplacement.

    Entrées : chemin, contenu (octets, ou texte écrit en UTF-8). Erreur : OSError ; l'ancien fichier reste alors intact.
    """
    chemin = Path(chemin)
    provisoire = chemin.with_name(chemin.name + ".tmp")
    try:
        provisoire.write_bytes(contenu.encode("utf-8") if isinstance(contenu, str) else contenu)
        os.replace(provisoire, chemin)
    finally:
        provisoire.unlink(missing_ok=True)
