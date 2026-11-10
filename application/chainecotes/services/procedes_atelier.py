"""Procédés de l'atelier : valeurs de coût (c, n, qualités IT) de l'utilisateur, enregistrées dans un fichier.

Le fichier garde seulement les valeurs qui diffèrent de data/procedes.json, pour que les valeurs indicatives
mises à jour avec l'application ne soient pas figées par un ancien enregistrement :

    {"format": "procedes-atelier", "version": 1, "procedes": {"tournage": {"c": 1.4, "n": 1.1, "itmin": 6, "itmax": 12}}}

Ce module n'importe ni Qt ni plotly.
"""

import json
import os
from pathlib import Path

from chainecotes.core import cout as cout_mod
from chainecotes.core.donnees import ecrireSansPerte
from chainecotes.core.errors import ErreurChaine

FORMAT = "procedes-atelier"
VERSION = 1
CHAMPS = ("c", "n", "itmin", "itmax")
_ID = "Chaine:ProcedesAtelier:invalide"


def cheminParDefaut() -> Path:
    """Fichier de l'utilisateur : %APPDATA%\\ChainesDeCotes1D\\procedes_atelier.json (dossier personnel à défaut)."""
    base = os.environ.get("APPDATA")
    return (Path(base) if base else Path.home() / ".config") / "ChainesDeCotes1D" / "procedes_atelier.json"


def _erreur(message: str) -> ErreurChaine:
    return ErreurChaine(_ID, f"Procédés de l'atelier non reconnus : {message}")


def _valider(procedes) -> dict[str, dict]:
    """Valeurs de l'atelier contrôlées : procédé connu, nombres c > 0 et n > 0, qualités 1 à 18 avec itmin ≤ itmax."""
    if not isinstance(procedes, dict):
        raise _erreur("le bloc « procedes » doit être un dictionnaire.")
    base = {p["id"]: p for p in cout_mod.listeProcedes()}
    sortie = {}
    for pid, valeurs in procedes.items():
        if pid not in base:
            raise _erreur(f"procédé inconnu : {pid!r}.")
        if not isinstance(valeurs, dict) or not set(valeurs) <= set(CHAMPS):
            raise _erreur(f"les valeurs de {pid!r} doivent être parmi {', '.join(CHAMPS)}.")
        for champ, v in valeurs.items():
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise _erreur(f"{pid} : {champ} doit être un nombre.")
            if champ.startswith("it") and not (isinstance(v, int) or float(v).is_integer()) or v != v:
                raise _erreur(f"{pid} : {champ} doit être une qualité entière de 1 à 18.")
        complet = {c: valeurs.get(c, base[pid][c]) for c in CHAMPS}
        if not (1 <= complet["itmin"] <= complet["itmax"] <= 18):
            raise _erreur(f"{pid} : qualités IT de 1 à 18 avec ITmin ≤ ITmax.")
        cout_mod.modeleMaillon({"procede": pid, **{k: complet[k] for k in CHAMPS}})  # c > 0 et n > 0
        diff = {c: (int(complet[c]) if c.startswith("it") else float(complet[c])) for c in CHAMPS if complet[c] != base[pid][c]}
        if diff:
            sortie[pid] = diff
    return sortie


def exporterProcedes(procedes: dict) -> str:
    """Texte JSON des valeurs d'atelier (seules celles qui diffèrent des valeurs indicatives sont gardées).

    Entrée : procedes ({id: {c, n, itmin, itmax}}, valeurs partielles permises). Erreur : ErreurChaine si invalide.
    """
    return json.dumps(
        {"format": FORMAT, "version": VERSION, "procedes": _valider(procedes)}, ensure_ascii=False, indent=2
    )


def importerProcedes(texte: str) -> dict[str, dict]:
    """Valeurs d'atelier relues d'un texte JSON ; ErreurChaine avec un message clair si le fichier n'est pas valide."""
    try:
        d = json.loads(texte)
    except (TypeError, ValueError) as err:
        raise _erreur(f"ce n'est pas un fichier JSON lisible ({err}).") from err
    if not isinstance(d, dict) or d.get("format") != FORMAT:
        raise _erreur("ce fichier n'a pas été enregistré par la page Répartir les tolérances.")
    version = d.get("version")
    if isinstance(version, bool) or not isinstance(version, int) or not 1 <= version <= VERSION:
        raise _erreur("numéro de version absent, invalide ou trop récent.")
    return _valider(d.get("procedes"))


def lireFichier(chemin: Path | None = None) -> tuple[dict[str, dict], str | None]:
    """Valeurs d'atelier du fichier de l'utilisateur. Sortie : (valeurs, message d'erreur ou None).

    Un fichier absent donne ({}, None) ; un fichier illisible ou invalide donne ({}, message) : l'application reste
    sur les valeurs indicatives, sans jamais planter au lancement.
    """
    chemin = chemin or cheminParDefaut()
    if not chemin.exists():
        return {}, None
    try:
        return importerProcedes(chemin.read_text(encoding="utf-8-sig")), None
    except ErreurChaine as e:
        return {}, e.message
    except (OSError, UnicodeDecodeError) as e:
        return {}, f"Procédés de l'atelier illisibles ({e})."


def ecrireFichier(procedes: dict, chemin: Path | None = None) -> Path:
    """Enregistre les valeurs d'atelier ; crée le dossier. Erreur : ErreurChaine (valeurs) ou OSError (écriture)."""
    chemin = chemin or cheminParDefaut()
    texte = exporterProcedes(procedes)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    ecrireSansPerte(chemin, texte)
    return chemin
