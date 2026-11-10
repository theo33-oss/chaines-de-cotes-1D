"""Matériaux, courbes de dilatation en température et limites d'emploi.

Port de materiaux.m et alphaMateriau.m (application MATLAB). Les valeurs viennent de data/materiaux.json, extrait
du classeur Excel de l'application par tools/extraire_materiaux.py.

Toutes les grandeurs sont converties en déformation ε(T) = ΔL/L depuis 20 °C :
epsilon → valeur / 100 ; alpha_moyen → α·(T − 20) ; alpha_instantane → intégrale de α depuis 20 °C (trapèzes).
Un proxy recalé est mis à l'échelle par Facteur = α (onglet Matériaux) / α de la courbe.
"""

import functools
import math
import re

import numpy as np
from scipy.interpolate import PchipInterpolator

from chainecotes.core.donnees import chargerJson
from chainecotes.core.nombres import fr

PERSONNALISE = "Personnalise"
T_REFERENCE_TABLES = 20.0  # °C : origine des courbes et des α moyens du classeur


def _pchip(x: np.ndarray, y: np.ndarray, t):
    """Interpolation pchip (même schéma que pchip de MATLAB, y compris aux extrémités)."""
    if len(x) == 2:  # deux points : pchip de MATLAB est linéaire
        return np.interp(t, x, y)
    return PchipInterpolator(x, y)(t)


def _versEpsilon(points: list[dict]) -> np.ndarray:
    """Convertit les points d'une courbe en tableau [T, ε], avec (20, 0) ajouté, trié par T (port de versEpsilon)."""
    blocs = []
    e = [(p["T"], p["valeur"] / 100) for p in points if p["grandeur"] == "epsilon"]
    blocs += e
    m = [(p["T"], p["valeur"] * 1e-6 * (p["T"] - 20)) for p in points if p["grandeur"] == "alpha_moyen"]
    blocs += m
    inst = sorted((p["T"], p["valeur"] * 1e-6) for p in points if p["grandeur"] == "alpha_instantane")
    if inst:
        Ti = np.array([p[0] for p in inst])
        ai = np.array([p[1] for p in inst])
        # grille fine (pas ≤ 2 K) : α interpolé linéairement, ε intégré exactement (comme MATLAB)
        Tc = np.unique(np.append(Ti, 20.0))
        Tg = [Tc[0]]
        for s in range(len(Tc) - 1):
            n = max(1, math.ceil((Tc[s + 1] - Tc[s]) / 2))
            Tg += list(Tc[s] + np.arange(1, n + 1) * (Tc[s + 1] - Tc[s]) / n)
        Tg = np.array(Tg)
        ag = np.full_like(Tg, ai[0]) if len(Ti) == 1 else np.interp(np.clip(Tg, Ti[0], Ti[-1]), Ti, ai)
        eg = np.concatenate([[0.0], np.cumsum(np.diff(Tg) * (ag[1:] + ag[:-1]) / 2)])
        eg = eg - eg[np.flatnonzero(Tg == 20.0)[0]]
        blocs += [(t, v) for t, v in zip(Tg, eg, strict=True) if t != 20.0]
    blocs.append((20.0, 0.0))
    # une valeur par température : la dernière rencontrée l'emporte (unique 'last' de MATLAB)
    d = {}
    for t, v in blocs:
        d[float(t)] = float(v)
    return np.array(sorted(d.items()))


def _alphaReference(P: np.ndarray) -> float:
    """α de la courbe pour le recalage : moyen 20-100 °C si la courbe y va, sinon pente de ε en 20 °C."""
    if P[:, 0].max() >= 100:
        return float(_pchip(P[:, 0], P[:, 1], 100.0)) / 80
    return float(_pchip(P[:, 0], P[:, 1], 20.0) - _pchip(P[:, 0], P[:, 1], 19.0))


@functools.cache
def listeMateriaux() -> tuple:
    """Liste des matériaux avec leur courbe ε(T) (déjà recalée) et leurs limites d'emploi.

    Sortie : tuple de dict nom, famille, alpha (1/K), plage, fiabilite, sources, courbeNom, recale (bool),
    facteur, courbe (np.ndarray [T, ε] ou tableau vide), tmin, tmax, zmin, zmax (°C, nan si absent), motif.
    Le dernier élément est « Personnalise » (alpha nan : α saisi à la main).
    """
    d = chargerJson("materiaux.json")
    courbes = {c["cle"]: _versEpsilon(c["points"]) for c in d["courbes"]}
    affect = {a["nom"]: a for a in d["affectations"]}
    nan = float("nan")
    liste = []
    for m in d["materiaux"]:
        a = affect.get(m["nom"], {})
        cle = a.get("courbe", "")
        P = courbes.get(cle, np.zeros((0, 2)))
        alpha = m["alpha"] * 1e-6
        facteur = 1.0
        if cle and a.get("recalage"):
            aref = _alphaReference(P)
            if aref > 0:
                facteur = alpha / aref
        liste.append(
            {
                "nom": m["nom"],
                "famille": m["famille"],
                "alpha": alpha,
                "plage": m["plage"],
                "fiabilite": m["fiabilite"],
                "sources": m["sources"],
                "courbeNom": cle if cle in courbes else "",
                "recale": bool(cle and a.get("recalage")),
                "facteur": facteur,
                "courbe": np.column_stack([P[:, 0], P[:, 1] * facteur]) if len(P) else P,
                "tmin": nan if a.get("tmin") is None else a["tmin"],
                "tmax": nan if a.get("tmax") is None else a["tmax"],
                "zmin": nan if a.get("zmin") is None else a["zmin"],
                "zmax": nan if a.get("zmax") is None else a["zmax"],
                "motif": a.get("motif", ""),
            }
        )
    liste.append(
        {
            "nom": PERSONNALISE,
            "famille": "Autre",
            "alpha": nan,
            "plage": "-",
            "fiabilite": "-",
            "sources": "-",
            "courbeNom": "",
            "recale": False,
            "facteur": 1.0,
            "courbe": np.zeros((0, 2)),
            "tmin": nan,
            "tmax": nan,
            "zmin": nan,
            "zmax": nan,
            "motif": "",
        }  # fmt: skip
    )
    return tuple(liste)


def nomsMateriaux() -> list[str]:
    """Noms des matériaux dans l'ordre du classeur, « Personnalise » en dernier."""
    return [m["nom"] for m in listeMateriaux()]


def sourcesMateriaux() -> list[dict]:
    """Sources citées par le classeur des matériaux : liste de dict cle, source, lien."""
    return chargerJson("materiaux.json")["sources"]


def courbesMateriaux() -> list[dict]:
    """Courbes du classeur : liste de dict cle, description, points (bruts, comme dans l'onglet Courbes_T)."""
    return chargerJson("materiaux.json")["courbes"]


def _materiau(nom: str) -> dict | None:
    return next((m for m in listeMateriaux() if m["nom"] == nom), None)


def deformation(m: dict, t):
    """Déformation ε(t) = ΔL/L depuis 20 °C d'un matériau (port de deformation dans alphaMateriau.m).

    Entrées : m (élément de listeMateriaux), t (°C, nombre ou tableau).
    Sortie : ε (sans unité, même forme que t).
    """
    t = np.asarray(t, dtype=float)
    C, a0 = m["courbe"], m["alpha"]
    if len(C) == 0:
        return a0 * (t - 20)
    Tb, Th = C[0, 0], C[-1, 0]
    e = np.zeros_like(t)
    dedans = (t >= Tb) & (t <= Th)
    e[dedans] = _pchip(C[:, 0], C[:, 1], t[dedans])
    bas, haut = t < Tb, t > Th
    e[bas] = C[0, 1] / (Tb - 20) * (t[bas] - 20) if Tb < 20 else a0 * (t[bas] - 20)
    e[haut] = C[-1, 1] / (Th - 20) * (t[haut] - 20) if Th > 20 else a0 * (t[haut] - 20)
    return e


def alphaMateriau(nom: str, T, Tref: float = 20.0) -> dict:
    """Coefficient de dilatation moyen entre Tref et T d'un matériau, et contrôle de son domaine d'emploi.

    Entrées : nom du matériau, T (°C, nombre ou tableau), Tref (°C, température de définition des cotes).
    Sortie : dict alpha (1/K, nan si inconnu ou « Personnalise »), horsDomaine (bool, même forme que T),
    motif (texte, rempli seulement si T est un nombre seul hors domaine).
    Si T = Tref : pas de dilatation, alpha = α du tableau (pour l'affichage).
    """
    scalaire = np.ndim(T) == 0
    Ta = np.atleast_1d(np.asarray(T, dtype=float))
    a = np.full_like(Ta, np.nan)
    hors = np.zeros(Ta.shape, dtype=bool)
    m = _materiau(nom)
    if m is None or math.isnan(m["alpha"]):
        return {"alpha": float(a[0]) if scalaire else a, "horsDomaine": bool(hors[0]) if scalaire else hors,
                "motif": ""}  # fmt: skip
    dT = Ta - Tref
    proche = np.abs(dT) < 1e-6
    eref = float(deformation(m, Tref))
    a[~proche] = (deformation(m, Ta[~proche]) - eref) / dT[~proche]
    a[proche] = m["alpha"]
    raisons = []
    C = m["courbe"]
    for i, t in enumerate(Ta):
        r = []
        if t < m["tmin"]:
            r.append(f"sous T min d'emploi ({fr(m['tmin'], 'g')} °C)")
        if t > m["tmax"]:
            r.append(f"au-dessus de T max d'emploi ({fr(m['tmax'], 'g')} °C)")
        if m["zmin"] <= t <= m["zmax"]:
            r.append(f"zone sensible {fr(m['zmin'], 'g')}-{fr(m['zmax'], 'g')} °C")
        if len(C):
            if C[0, 0] < 20 and t < C[0, 0]:
                r.append(f"extrapolé sous {fr(C[0, 0], 'g')} °C")
            if C[-1, 0] > 20 and t > C[-1, 0]:
                r.append(f"extrapolé au-dessus de {fr(C[-1, 0], 'g')} °C")
        else:
            b = _bornesPlage(m["plage"])
            if b and (t < b[0] or t > b[1]):
                r.append(f"hors plage de la valeur ({m['plage']} °C)")
        hors[i] = bool(r)
        raisons.append(", ".join(r))
    motif = ""
    if scalaire and hors[0]:
        t = Ta[0]
        motif = raisons[0]
        if m["motif"] and (t < m["tmin"] or t > m["tmax"] or m["zmin"] <= t <= m["zmax"]):
            motif += " : " + m["motif"]
    return {"alpha": float(a[0]) if scalaire else a, "horsDomaine": bool(hors[0]) if scalaire else hors,
            "motif": motif}  # fmt: skip


def _bornesPlage(plage: str):
    """Bornes d'une plage écrite « a-b » (ex. « 20-100 »), None sinon."""
    b = re.match(r"^\s*(-?\d+)\s*-\s*(-?\d+)\s*$", plage or "")
    return (float(b.group(1)), float(b.group(2))) if b else None
