"""Cartouche d'un dossier de calcul : projet, repère, indice de révision, auteur, vérificateur, statut, historique.

Le cartouche est un bloc optionnel `cartouche` du problème (enregistré dans le fichier .json, repris par les dossiers
HTML, PDF et Word). Ce module n'importe ni streamlit ni plotly.
"""

import hashlib
import json

from chainecotes.core.chaine import estVide

CHAMPS = (
    ("projet", "Projet"),
    ("ensemble", "Ensemble ou pièce"),
    ("reference", "Référence du plan"),
    ("indice", "Indice de révision"),
    ("statut", "Statut"),
    ("auteur", "Auteur"),
    ("verificateur", "Vérificateur"),
    ("commentaire", "Remarque"),
)
STATUTS = ("Brouillon", "En revue", "Validé", "Obsolète")
REVISIONS = (("indice", "Indice"), ("date", "Date"), ("auteur", "Auteur"), ("objet", "Modification"))
MAX_REVISIONS = 50


def empreinte(probleme: dict) -> str:
    """Empreinte (SHA-256, 16 premiers caractères) de ce qui décide du calcul : condition, réglages et maillons.

    Le cartouche n'y est pas : on peut compléter l'auteur ou la remarque d'une étude validée sans changer son empreinte.
    """
    base = {k: probleme.get(k) for k in ("condition", "reglages", "maillons")}
    if isinstance(base["maillons"], list):  # l'image d'un maillon ne décide pas du calcul
        base["maillons"] = [
            {k: v for k, v in m.items() if k != "image"} if isinstance(m, dict) else m for m in base["maillons"]
        ]
    texte = json.dumps(base, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()[:16]


def etatValidation(probleme: dict) -> str:
    """État de validation d'une étude : « aucune », « valide » (empreinte enregistrée et identique) ou « modifie ».

    « modifie » : le statut est « Validé » mais le problème n'a plus l'empreinte enregistrée à la validation
    (fichier retouché à la main, ou modifié depuis).
    """
    c = probleme.get("cartouche")
    c = c if isinstance(c, dict) else {}
    if c.get("statut") != "Validé" or estVide(c.get("empreinte")):
        return "aucune"
    return "valide" if c["empreinte"] == empreinte(probleme) else "modifie"


def _texte(v) -> str:
    return "" if estVide(v) else str(v).strip()


def lignesCartouche(probleme: dict) -> list[tuple[str, str]]:
    """Lignes (libellé, texte) du cartouche qui sont remplies, dans l'ordre de CHAMPS.

    Entrée : probleme (dict ; le bloc « cartouche » est facultatif, tout autre type est ignoré).
    Sortie : liste vide si le cartouche est absent ou vide.
    """
    c = probleme.get("cartouche")
    c = c if isinstance(c, dict) else {}
    lignes = [(libelle, _texte(c.get(cle))) for cle, libelle in CHAMPS if _texte(c.get(cle))]
    if _texte(c.get("empreinte")):
        lignes.append(("Empreinte du problème", _texte(c["empreinte"])))
        if etatValidation(probleme) == "modifie":
            lignes.append(("Contrôle d'intégrité", "ATTENTION : le problème a changé depuis la validation"))
    return lignes


def revisions(probleme: dict) -> list[dict]:
    """Historique des révisions du cartouche : liste de dict indice, date, auteur, objet (textes).

    Les lignes vides sont écartées.

    Entrée : probleme (dict ; « cartouche » → « revisions » est facultatif). Sortie : au plus MAX_REVISIONS lignes.
    """
    c = probleme.get("cartouche")
    brut = c.get("revisions") if isinstance(c, dict) else None
    lignes = [{cle: _texte(r.get(cle)) for cle, _ in REVISIONS} for r in brut if isinstance(r, dict)] if brut else []
    return [r for r in lignes if any(r.values())][:MAX_REVISIONS]
