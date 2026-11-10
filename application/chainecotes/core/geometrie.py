"""Tolérances géométriques (ISO 1101) prises en compte dans une chaîne de cotes 1D.

Une zone de tolérance de largeur t (deux plans parallèles, ou cylindre de diamètre t pour une position) laisse la
surface ou l'axe se déplacer de ± t/2 au plus dans le sens de la chaîne. Elle devient donc un maillon de cote nulle,
de sens « + » ou « − », d'intervalle de tolérance IT = t (écarts ± t/2). Au maximum de matière (Ⓜ), la tolérance
géométrique peut être augmentée du « bonus » (écart entre la taille réelle et la taille au maximum de matière) : au pire
des cas, on ajoute au plus l'IT de l'élément. Ce modèle 1D ne remplace pas une analyse 2D ou 3D (zones inclinées,
bascule, effet de levier) : un angle de la zone avec l'axe de la chaîne se règle avec les champs facteur et angle.
Ce module n'importe ni streamlit ni plotly.
"""

import math

from chainecotes.core.errors import ErreurChaine

# identifiant → (nom, symbole ISO 1101, famille)
TYPES = {
    "rectitude": ("Rectitude", "⏤", "forme"),
    "planeite": ("Planéité", "⏥", "forme"),
    "parallelisme": ("Parallélisme", "∥", "orientation"),
    "perpendicularite": ("Perpendicularité", "⟂", "orientation"),
    "inclinaison": ("Inclinaison", "∠", "orientation"),
    "localisation": ("Localisation", "⌖", "position"),
    "coaxialite": ("Coaxialité", "◎", "position"),
    "symetrie": ("Symétrie", "⌯", "position"),
    "battement": ("Battement circulaire", "↗", "battement"),
}
MAXIMUM_MATIERE = "Ⓜ"
_ID = "Chaine:Geometrie:"


def libelle(identifiant: str) -> str:
    """Nom suivi du symbole ISO 1101 d'un type de tolérance (« Planéité ⏥ »).

    Entrée : identifiant (clé de TYPES). Sortie : texte. Erreur : ErreurChaine si le type est inconnu.
    """
    if identifiant not in TYPES:
        raise ErreurChaine(_ID + "type", f"Tolérance géométrique inconnue : {identifiant!r}.")
    nom, symbole, _ = TYPES[identifiant]
    return f"{nom} {symbole}"


def maillonGeometrique(
    identifiant: str,
    tolerance: float,
    sens: str = "+",
    nom: str | None = None,
    bonus: float = 0.0,
    loi: str = "uniforme",
) -> dict:
    """Maillon de chaîne représentant une tolérance géométrique.

    Entrées : identifiant (clé de TYPES), tolerance (largeur de zone t en mm, > 0), sens (« + » ou « - »), nom (texte ;
    par défaut le type et la zone), bonus (mm ≥ 0 : bonus maximal au maximum de matière Ⓜ, ajouté à t),
    loi (« uniforme »
    par défaut : la zone est remplie à peu près également ; « normale » ou « triangulaire » possibles).
    Sortie : dict maillon (cote 0, es = +IT/2, ei = −IT/2, IT = t + bonus, clé geometrie = identifiant du type).
    Erreur : ErreurChaine si le type est inconnu, t ≤ 0, bonus < 0 ou non fini.
    """
    etiquette = libelle(identifiant)
    if not (math.isfinite(tolerance) and tolerance > 0):
        raise ErreurChaine(_ID + "valeur", "La zone de tolérance géométrique doit être un nombre strictement positif.")
    if not (math.isfinite(bonus) and bonus >= 0):
        raise ErreurChaine(_ID + "bonus", "Le bonus au maximum de matière doit être un nombre positif ou nul.")
    it = tolerance + bonus
    suffixe = f" {MAXIMUM_MATIERE}" if bonus > 0 else ""
    return {
        "nom": nom or f"{etiquette} {tolerance:g}{suffixe}",
        "sens": sens,
        "cote": 0.0,
        "iso": None,
        "es": it / 2,
        "ei": -it / 2,
        "loi": loi,
        "materiau": None,
        "alpha": None,
        "tservice": None,
        "geometrie": identifiant,
    }
