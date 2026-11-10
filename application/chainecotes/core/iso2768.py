"""Tolérances générales ISO 2768-1 : écart ± d'une cote linéaire sans indication de tolérance (data/iso2768.json)."""

from chainecotes.core.donnees import chargerJson
from chainecotes.core.errors import ErreurChaine
from chainecotes.core.nombres import fr

CLASSES = ("f", "m", "c", "v")
_ID = "Chaine:Iso2768:saisie"


def tolGenerale(cote: float, classe: str) -> float:
    """Écart ± (mm) de la tolérance générale ISO 2768-1 d'une classe pour une cote nominale.

    Entrées : cote (mm, de 0,5 à 1000), classe (« f », « m », « c » ou « v »).
    Sortie : écart ± en mm (la zone de tolérance vaut le double).
    Erreur : ErreurChaine si la classe est inconnue, si la cote est hors de la table (au-delà de 1000 mm, ou sous
    0,5 mm) ou si la classe n'a pas de valeur pour cette plage (la classe « v » ne s'applique pas jusqu'à 3 mm).
    """
    t = chargerJson("iso2768.json")
    if classe not in CLASSES:
        raise ErreurChaine(_ID, f"Classe ISO 2768 inconnue : {classe!r} (f, m, c ou v attendue).")
    if not t["inferieure"] <= cote <= t["bornes"][-1]:
        raise ErreurChaine(
            _ID,
            f"Cote {fr(cote, 'g')} mm hors de la table ISO 2768-1 ({fr(t['inferieure'], 'g')} à "
            f"{fr(t['bornes'][-1], 'g')} mm) : saisissez ses écarts.",
        )
    i = next(k for k, b in enumerate(t["bornes"]) if cote <= b)
    e = t["ecarts"][classe][i]
    if e is None:
        raise ErreurChaine(_ID, f"La classe {classe} n'a pas de valeur ISO 2768-1 pour la cote {fr(cote, 'g')} mm.")
    return float(e)
