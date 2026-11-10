"""Écarts normalisés ISO 286 (tables de data/iso286.json, reprises de MecaStruct RdM Pro).

Port de mecastruct/core/fits.py (shaftDeviations, holeDeviations : mêmes règles, même table), complété par la
lecture d'une désignation comme « 40 h7 », « H7 » ou « 40JS6 » et par la tolérance IT seule (problème inverse).
"""

import re

from chainecotes.core.donnees import chargerJson
from chainecotes.core.errors import ErreurChaine
from chainecotes.core.nombres import fr

LETTRES_ARBRE = ("a", "b", "c", "cd", "d", "e", "ef", "f", "fg", "g", "h", "js", "j", "k", "m", "n", "p", "r", "s",
                 "t", "u", "v", "x", "y", "z", "za", "zb", "zc")  # fmt: skip
LETTRES_ALESAGE = tuple(x.upper() for x in LETTRES_ARBRE)
QUALITES = tuple(range(1, 19))
_ID = "Chaine:Iso286:saisie"
_DESIGNATION = re.compile(r"^\s*(?:(\d+(?:[.,]\d+)?)\s*)?([A-Za-z]{1,2})\s*(\d{1,2})\s*$")


def _table() -> dict:
    return chargerJson("iso286.json")


def _ligne(t: dict, d: float) -> int:
    """Indice de la plage de diamètre contenant d (mm) : première borne supérieure ≥ d."""
    if not 0 < d <= t["bornes"][-1]:
        limite = fr(t["bornes"][-1], "g")
        raise ErreurChaine(_ID, f"Cote nominale hors des tables ISO 286 : {fr(d, 'g')} mm (0 < d ≤ {limite} mm).")
    return next(i for i, b in enumerate(t["bornes"]) if d <= b)


def _it(t: dict, i: int, q: int) -> float:
    if q not in QUALITES:
        raise ErreurChaine(_ID, f"Qualité IT{q} hors des tables (1 à 18).")
    return t["it"][str(q)][i]


def _val(v, quoi: str) -> float:
    if v is None:
        raise ErreurChaine(_ID, f"{quoi} n'existe pas dans l'ISO 286 pour cette cote.")
    return v


def _js(it: float, q: int) -> float:
    """Demi-intervalle de js/JS : IT/2, IT ramené au pair inférieur s'il est impair pour les qualités 7 à 11."""
    if 7 <= q <= 11 and it % 2 == 1:
        it -= 1
    return it / 2


def _plage(t: dict, i: int) -> str:
    bas = 0 if i == 0 else t["bornes"][i - 1]
    return f"au-delà de {fr(bas, 'g')} jusqu'à {fr(t['bornes'][i], 'g')} mm"


def toleranceIT(d: float, q: int) -> float:
    """Tolérance normalisée IT d'une qualité pour une cote nominale.

    Entrées : d (mm), q (qualité 1 à 18).
    Sortie : IT (µm). Erreur ErreurChaine si la cote ou la qualité sort des tables.
    """
    t = _table()
    return _it(t, _ligne(t, d), q)


def shaftDeviations(d: float, lettre: str, q: int) -> dict:
    """Écarts d'un arbre ISO 286 (ex. « r », 6) pour la cote nominale d.

    Entrées : d (mm), lettre (a à zc, js), q (qualité 1 à 18).
    Sortie : dict es, ei, IT (µm), plage (texte), fondamental (« es » ou « ei »).
    Erreur : ErreurChaine (cote, lettre ou qualité hors table, écart inexistant).
    """
    t = _table()
    if lettre not in LETTRES_ARBRE:
        raise ErreurChaine(_ID, f"Position d'arbre inconnue : {lettre!r}.")
    i = _ligne(t, d)
    it = _it(t, i, q)
    nom = f"{lettre}{q}"
    if lettre == "js":
        es, ei, fond = _js(it, q), -_js(it, q), "es"
    elif LETTRES_ARBRE.index(lettre) <= LETTRES_ARBRE.index("h"):
        es = _val(t["arbre"][lettre][i], nom)
        ei, fond = es - it, "es"
    else:
        if lettre == "j":
            col = {5: "j5-6", 6: "j5-6", 7: "j7", 8: "j8"}.get(q)
            if col is None:
                raise ErreurChaine(_ID, f"{nom} n'existe pas : j est défini pour les qualités 5 à 8.")
        elif lettre == "k":
            col = "k4-7" if 4 <= q <= 7 else "k"
        else:
            col = lettre
        ei = _val(t["arbre"][col][i], nom)
        es, fond = ei + it, "ei"
    return {"es": es, "ei": ei, "IT": it, "plage": _plage(t, i), "fondamental": fond}


def holeDeviations(d: float, lettre: str, q: int) -> dict:
    """Écarts d'un alésage ISO 286 (ex. « H », 7) pour la cote nominale d.

    Entrées : d (mm), lettre (A à ZC, JS), q (qualité 1 à 18).
    Sortie : dict ES, EI, IT, delta (µm, correction Δ ajoutée à ES, 0 sinon), plage, fondamental (« EI » ou « ES »).
    Erreur : ErreurChaine.
    """
    t = _table()
    if lettre not in LETTRES_ALESAGE:
        raise ErreurChaine(_ID, f"Position d'alésage inconnue : {lettre!r}.")
    i = _ligne(t, d)
    it = _it(t, i, q)
    nom = f"{lettre}{q}"
    delta = 0.0
    if lettre == "JS":
        ES, EI, fond = _js(it, q), -_js(it, q), "EI"
    elif LETTRES_ALESAGE.index(lettre) <= LETTRES_ALESAGE.index("H"):
        EI = _val(t["alesage"][lettre][i], nom)
        ES, fond = EI + it, "EI"
    else:
        if lettre == "J":
            if q not in (6, 7, 8):
                raise ErreurChaine(_ID, f"{nom} n'existe pas : J est défini pour les qualités 6 à 8.")
            col = f"J{q}"
        elif lettre in ("K", "M", "N"):
            col = f"{lettre}<=8" if q <= 8 else lettre
        else:
            col = lettre
        ES = _val(t["alesage"][col][i], nom)
        avec_delta = (lettre in ("K", "M", "N") and 3 <= q <= 8) or (
            LETTRES_ALESAGE.index(lettre) >= LETTRES_ALESAGE.index("P") and 3 <= q <= 7
        )
        if avec_delta:
            delta = _val(t["delta"][str(q)][i], f"Δ pour {nom}")
            ES += delta
        EI, fond = ES - it, "ES"
    return {"ES": ES, "EI": EI, "IT": it, "delta": delta, "plage": _plage(t, i), "fondamental": fond}


def lireDesignation(texte: str, cote: float | None = None, arrondiJs: bool = False) -> dict:
    """Lit une désignation ISO 286 (« 40 h7 », « H7 », « 40JS6 ») et calcule ses écarts.

    Entrées : texte de la désignation ; cote (mm) utilisée si le texte ne contient pas de cote ;
    arrondiJs : False (défaut) = js/JS à ± IT/2 exactement, comme ajustementISO.m (référence MATLAB) ;
    True = arrondi ISO 286-1 de MecaStruct (IT impair ramené au pair inférieur pour les qualités 7 à 11).
    Sortie : dict designation (normalisée, ex. « 40 h7 »), cote (mm), lettre, qualite, type (« arbre » ou
    « alésage »), es, ei (mm, écart supérieur et inférieur), IT (µm), plage (texte), avertissement (texte,
    vide sauf écart connu entre MATLAB et la norme).
    Erreur : ErreurChaine si le texte est illisible, sans cote, ou hors des tables.
    """
    m = _DESIGNATION.match(str(texte or ""))
    if not m:
        raise ErreurChaine(
            _ID, f"Désignation ISO 286 illisible : {texte!r} (exemples : « 40 h7 », « H7 », « 25 JS6 »)."
        )
    if m.group(1):
        cote = float(m.group(1).replace(",", "."))
    if cote is None:
        raise ErreurChaine(_ID, f"Cote nominale manquante pour {texte!r}.")
    lettre, q = m.group(2), int(m.group(3))
    if lettre.lower() == "js":
        lettre = "JS" if lettre[0].isupper() else "js"
    if lettre.isupper():
        r = holeDeviations(cote, lettre, q)
        es, ei, typ = r["ES"], r["EI"], "alésage"
    elif lettre.islower():
        r = shaftDeviations(cote, lettre, q)
        es, ei, typ = r["es"], r["ei"], "arbre"
    else:
        raise ErreurChaine(_ID, f"Position {lettre!r} : écrire tout en majuscules (alésage) ou en minuscules (arbre).")
    avertissement = ""
    if lettre in ("js", "JS") and 7 <= q <= 11 and r["IT"] % 2 == 1:
        demi = r["IT"] / 2
        avertissement = (
            f"{lettre}{q} : IT{q} = {fr(r['IT'], 'g')} µm est impair. La norme ISO 286-1 arrondit les écarts à "
            f"± {fr(demi - 0.5, 'g')} µm ; l'application MATLAB de référence, et donc ce calcul, garde "
            f"± {fr(demi, 'g')} µm."
        )
        if not arrondiJs:
            es, ei = demi, -demi
    return {
        "designation": f"{cote:g} {lettre}{q}",
        "cote": cote,
        "lettre": lettre,
        "qualite": q,
        "type": typ,
        "es": es / 1000,
        "ei": ei / 1000,
        "IT": r["IT"],
        "plage": r["plage"],
        "avertissement": avertissement if not arrondiJs else "",
    }
