"""Comparaison de deux scénarios de chaîne de cotes (deux calculs) : écarts sur le jeu, la capabilité et les tolérances.

Ce module n'importe ni Qt ni pandas : la page web l'utilise sans charger les calculs de mécanisme.
"""

import math

from chainecotes.core.nombres import fr

_EPS = 1e-12


def _delta(a, b):
    """b − a, ou None si l'une des valeurs manque."""
    return None if a is None or b is None else b - a


def _fini(x):
    return float(x) if math.isfinite(x) else None


def _maillonsParNom(res: dict) -> dict:
    """Tolérance IT (mm) par nom de maillon ; un nom répété reçoit un suffixe « (2) », « (3) »…"""
    sortie = {}
    for nom, it in zip(res["Nom"], res["IT"], strict=True):
        cle, k = str(nom), 2
        while cle in sortie:
            cle, k = f"{nom} ({k})", k + 1
        sortie[cle] = float(it)
    return sortie


def comparerScenarios(bundleA: dict, bundleB: dict) -> dict:
    """Compare deux calculs (A = référence, B = variante) : tous les deltas sont B − A.

    Entrées : bundleA, bundleB (sorties de calculerChaine).
    Sortie : dict jeuMini, jeuMaxi (pire des cas, mm), cpk, ppm (formule), chacun {a, b, delta} (delta None si
    une valeur n'existe pas, par exemple Cpk non défini) ; maillons = liste de {nom, statut « commun » | « ajouté »
    | « supprimé », itA, itB, delta (mm)} ; phrases = liste de phrases de synthèse en français ; identiques
    (bool, aucun écart sur les grandeurs ni les tolérances).
    Les maillons sont appariés par nom ; « ajouté » = présent en B seulement, « supprimé » = présent en A seulement.
    """
    vA, vB = bundleA["verdicts"], bundleB["verdicts"]
    grandeurs = {
        "jeuMini": (vA["pireCas"]["min"], vB["pireCas"]["min"]),
        "jeuMaxi": (vA["pireCas"]["max"], vB["pireCas"]["max"]),
        "cpk": (_fini(vA["cpk"]), _fini(vB["cpk"])),
        "ppm": (_fini(vA["ppm"]), _fini(vB["ppm"])),
    }
    sortie = {k: {"a": a, "b": b, "delta": _delta(a, b)} for k, (a, b) in grandeurs.items()}

    mA, mB = _maillonsParNom(bundleA["res"]), _maillonsParNom(bundleB["res"])
    maillons = []
    for nom in list(mA) + [x for x in mB if x not in mA]:
        a, b = mA.get(nom), mB.get(nom)
        statut = "commun" if a is not None and b is not None else ("supprimé" if b is None else "ajouté")
        maillons.append({"nom": nom, "statut": statut, "itA": a, "itB": b, "delta": _delta(a, b)})

    phrases = []
    for cle, libelle, unite in (("jeuMini", "Le jeu mini", "mm"), ("jeuMaxi", "Le jeu maxi", "mm")):
        d = sortie[cle]["delta"]
        if abs(d) > _EPS:
            a, b = fr(sortie[cle]["a"]), fr(sortie[cle]["b"])
            phrases.append(f"{libelle} passe de {a} à {b} {unite} ({fr(d, '+.4f')}).")
    d = sortie["cpk"]["delta"]
    if d is not None and abs(d) > _EPS:
        sens = "s'améliore" if d > 0 else "se dégrade"
        phrases.append(f"Le Cpk {sens} : {fr(sortie['cpk']['a'], '.2f')} → {fr(sortie['cpk']['b'], '.2f')}.")
    d = sortie["ppm"]["delta"]
    if d is not None and abs(d) > _EPS:
        a, b = fr(sortie["ppm"]["a"], ".1f"), fr(sortie["ppm"]["b"], ".1f")
        phrases.append(f"Le taux hors tolérance passe de {a} à {b} ppm.")
    for m in maillons:
        if m["statut"] == "ajouté":
            phrases.append(f"Maillon ajouté : {m['nom']} (IT = {fr(m['itB'])} mm).")
        elif m["statut"] == "supprimé":
            phrases.append(f"Maillon supprimé : {m['nom']} (IT = {fr(m['itA'])} mm).")
        elif abs(m["delta"]) > _EPS:
            verbe = "élargie" if m["delta"] > 0 else "resserrée"
            phrases.append(f"Tolérance de {m['nom']} {verbe} : {fr(m['itA'])} → {fr(m['itB'])} mm.")
    identiques = not phrases
    if identiques:
        phrases.append("Les deux scénarios sont identiques : aucun écart.")
    return {**sortie, "maillons": maillons, "phrases": phrases, "identiques": identiques}
