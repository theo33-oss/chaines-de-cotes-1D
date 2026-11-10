"""Assistant de choix d'ajustement ISO 286 : classe les ajustements recommandés selon la fonction souhaitée.

Les ajustements et leurs usages viennent de data/ajustements.json ; les jeux sont toujours calculés par
chainecotes.core.iso286 (jamais recopiés).
"""

from chainecotes.core.donnees import chargerJson
from chainecotes.core.errors import ErreurChaine
from chainecotes.core.iso286 import lireDesignation, toleranceIT

SYSTEMES = ("alesage", "arbre")
_ID = "Chaine:Ajustement:saisie"
_CLE = {"alesage": "alesageNormal", "arbre": "arbreNormal"}


def fonctionsDisponibles() -> dict:
    """Fonctions d'ajustement proposées. Sortie : dict {code: libellé}."""
    return dict(chargerJson("ajustements.json")["fonctions"])


def _nature(jeuMini: float, jeuMaxi: float) -> str:
    """« avec jeu » si jeu mini ≥ 0, « serré » si jeu maxi ≤ 0 (serrage garanti), sinon « incertain »."""
    if jeuMini >= 0:
        return "avec jeu"
    return "serré" if jeuMaxi <= 0 else "incertain"


def choisirAjustement(cote: float, fonction: str, systeme: str = "alesage", arrondiJs: bool = False) -> list[dict]:
    """Classe les ajustements candidats pour une fonction, une cote nominale et un système.

    Entrées : cote (mm) ; fonction (code de fonctionsDisponibles()) ; systeme « alesage » (alésage normal H) ou
    « arbre » (arbre normal h) ; arrondiJs : arrondi ISO des js/JS impairs (False = comportement MATLAB, voir
    iso286.lireDesignation).
    Sortie : liste triée par adéquation décroissante (à égalité, ordre du fichier de données) de dicts :
    rang (1 = meilleur), designation (ex. « H7/g6 »), famille, jeuMini, jeuMaxi (mm, jeu = alésage - arbre ;
    négatif = serrage), nature (« avec jeu », « incertain », « serré »), ITAlesage, ITArbre (µm), risque, usage,
    description, avertissement (vide sauf js/JS impair ou nature différente de l'usage courant de la table).
    Les ajustements dont une pièce n'existe pas pour cette cote (hors table, qualité non définie) sont écartés.
    Erreur : ErreurChaine si fonction ou système inconnu, ou cote hors des tables ISO 286.
    """
    d = chargerJson("ajustements.json")
    if fonction not in d["fonctions"]:
        raise ErreurChaine(_ID, f"Fonction d'ajustement inconnue : {fonction!r} ({', '.join(d['fonctions'])}).")
    if systeme not in SYSTEMES:
        raise ErreurChaine(_ID, f"Système inconnu : {systeme!r} (« alesage » ou « arbre »).")
    toleranceIT(cote, 7)  # lève ErreurChaine si la cote est hors des tables
    candidats = []
    for a in d["ajustements"]:
        score = a["adequation"].get(fonction, 0)
        if score <= 0:
            continue
        desig = a[_CLE[systeme]]
        try:
            trou, arbre = (lireDesignation(p, cote, arrondiJs) for p in desig.split("/"))
        except ErreurChaine:
            continue
        jeuMini, jeuMaxi = round(trou["ei"] - arbre["es"], 9), round(trou["es"] - arbre["ei"], 9)
        nature = _nature(jeuMini, jeuMaxi)
        avert = " ".join(x for x in (trou["avertissement"], arbre["avertissement"]) if x)
        if nature != a["natureAttendue"]:
            attendu = a["natureAttendue"]
            avert = f"{avert} À cette cote l'ajustement est « {nature} » (usage courant : « {attendu} »).".strip()
        candidats.append((-score, len(candidats), {
            "designation": desig, "famille": a["famille"], "jeuMini": jeuMini, "jeuMaxi": jeuMaxi,
            "nature": nature, "ITAlesage": trou["IT"], "ITArbre": arbre["IT"], "risque": a["risque"],
            "usage": a["usage"], "description": a["description"], "avertissement": avert,
        }))  # fmt: skip
    return [{"rang": i, **c[2]} for i, c in enumerate(sorted(candidats, key=lambda c: c[:2]), 1)]
