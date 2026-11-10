"""Allocation de tolérances au coût minimal : cout_i = c_i·(IT_i/IT_ref)^(-n_i).

Plus la tolérance est serrée, plus c'est cher. On minimise Σ cout_i sous une contrainte du type Σ h_i·IT_i^p = T
(p = 1 : pire cas, h_i = |a_i| ; p = 2 : statistique, h_i = (|a_i|·cs_i)², comme dans inverse.py), avec des bornes
[IT_lo_i ; IT_hi_i] venant des qualités atteignables du procédé.
Conditions de Lagrange : IT = (n·c·IT_ref^n/(λ·p·h))^(1/(n+p)), borné à [lo ; hi] : la saturation est exacte, et
la contrainte est monotone en λ, donc résolue par brentq. Cas n identique et p = 1 : IT ∝ (c/|a|)^(1/(n+1)).
Les données des procédés sont dans data/procedes.json (valeurs indicatives).
"""

import math

import numpy as np
from scipy.optimize import brentq

from chainecotes.core import iso286
from chainecotes.core.donnees import chargerJson
from chainecotes.core.errors import ErreurChaine

_ID = "Chaine:Cout:"


def listeProcedes() -> list[dict]:
    """Liste des procédés de data/procedes.json (id, nom, c, n, itmin, itmax, source). Lecture seule."""
    return chargerJson("procedes.json")["procedes"]


def fiabiliteProcedes() -> str:
    """Niveau de fiabilité des valeurs de data/procedes.json, en clair (à afficher près de tout résultat de coût)."""
    return chargerJson("procedes.json")["fiabilite"]


def modeleMaillon(spec: dict | None) -> dict:
    """Résout le modèle de coût d'un maillon.

    Entrée : spec (None = procédé « generique », ou dict avec « procede » (id) et/ou « c », « n », « itmin »,
    « itmax » qui écrasent les valeurs du procédé).
    Sortie : dict c, n, itmin, itmax (qualités ISO), procede.
    Erreur : ErreurChaine si le procédé est inconnu, c ≤ 0, n ≤ 0 ou itmin > itmax.
    """
    spec = spec or {}
    pid = spec.get("procede") or "generique"
    base = next((p for p in listeProcedes() if p["id"] == pid), None)
    if base is None:
        raise ErreurChaine(_ID + "procede", f"Procédé inconnu : {pid!r}.")
    m = {k: spec.get(k) if spec.get(k) is not None else base[k] for k in ("c", "n", "itmin", "itmax")}
    if not m["c"] > 0:
        raise ErreurChaine(_ID + "c", f"Le coefficient de coût doit être > 0 (reçu {m['c']!r}).")
    if not m["n"] > 0:
        raise ErreurChaine(_ID + "n", f"L'exposant de coût doit être > 0 (reçu {m['n']!r}).")
    if not m["itmin"] <= m["itmax"]:
        raise ErreurChaine(_ID + "qualites", "La qualité ITmin doit être ≤ ITmax.")
    m["procede"] = pid
    return m


def refIT() -> float:
    """IT de référence du modèle de coût (mm), lu dans data/procedes.json."""
    return float(chargerJson("procedes.json")["it_ref_mm"])


def coutTotal(it, c, n) -> float:
    """Coût relatif Σ c_i·(IT_i/IT_ref)^(-n_i). Entrées : IT (mm, > 0), c, n (vecteurs). Sortie : nombre sans unité."""
    return float(np.sum(np.asarray(c) * (np.asarray(it) / refIT()) ** (-np.asarray(n))))


def allouerCout(h, p: int, c, n, lo, hi, cible: float) -> np.ndarray:
    """Allocation de coût minimal sous Σ h_i·x_i^p ≤ cible, avec lo_i ≤ x_i ≤ hi_i.

    Entrées : h (coefficients > 0), p (1 ou 2), c, n (coût), lo, hi (bornes d'IT en mm, lo ≤ hi), cible (> 0).
    Sortie : x (mm). Si tout à hi tient déjà, x = hi (le coût ne baisse plus). Sinon la contrainte est tenue à
    l'égalité. Erreur ErreurChaine si cible ≤ 0 ou si même x = lo dépasse la cible (aucune solution).
    """
    h, c, n, lo, hi = (np.asarray(v, dtype=float) for v in (h, c, n, lo, hi))
    if not cible > 0:
        raise ErreurChaine(_ID + "cible", "Il ne reste aucune tolérance à répartir.")
    if np.sum(h * lo**p) > cible * (1 + 1e-12):
        raise ErreurChaine(
            _ID + "infaisable",
            "Aucune solution : même les tolérances les plus serrées des procédés choisis dépassent le jeu visible.",
        )
    if np.sum(h * lo**p) >= cible:  # dépassement dans la tolérance numérique : lo est la seule borne possible
        return lo.copy()
    if np.sum(h * hi**p) <= cible:
        return hi.copy()
    k = n * c * refIT() ** n / (p * h)  # IT(λ) = (k/λ)^(1/(n+p))

    def x(t):
        with np.errstate(over="ignore"):
            return np.clip((k / math.exp(t)) ** (1 / (n + p)), lo, hi)

    # IT(t) vaut hi pour t ≤ ln k − (n+p)·ln hi et lo pour t ≥ ln k − (n+p)·ln lo : ces bornes encadrent la racine
    lk = np.log(k)
    a = float(np.min(lk - (n + p) * np.log(hi))) - 1.0
    b = float(np.max(lk - (n + p) * np.log(lo))) + 1.0
    t = brentq(lambda t: float(np.sum(h * x(t) ** p)) - cible, a, b, xtol=1e-14, rtol=1e-14, maxiter=1000)
    return x(t)


def repartirBorne(h, p: int, poids, lo, hi, cible: float) -> np.ndarray:
    """Répartition à IT proportionnel aux poids, bornée : x_i = clip(f·poids_i, lo_i, hi_i) avec Σ h·x^p = cible.

    Sert de base de comparaison réaliste (mêmes bornes de procédé que allouerCout) : c'est une solution
    admissible, donc au moins aussi chère que l'optimum. Entrées : h (> 0), p (1 ou 2), poids (> 0), lo, hi (mm).
    Sortie : x (mm). Si tout à hi tient déjà, x = hi ; si tout à lo dépasse la cible, x = lo.
    """
    h, w, lo, hi = (np.asarray(v, dtype=float) for v in (h, poids, lo, hi))

    def x(f):
        return np.clip(f * w, lo, hi)

    def ecart(f):
        return float(np.sum(h * x(f) ** p)) - cible

    if ecart(float(np.max(hi / w))) <= 0:
        return hi.copy()
    if ecart(float(np.min(lo / w))) >= 0:
        return lo.copy()
    return x(brentq(ecart, float(np.min(lo / w)), float(np.max(hi / w)), xtol=1e-15, rtol=1e-14, maxiter=1000))


def arrondirIso(x, cotes, qmin, qmax, h, p: int, c, n, cible: float):
    """Arrondit chaque IT à une qualité ISO 286 en gardant Σ h·IT^p ≤ cible.

    Démarche : tout à la qualité inférieure (IT ≤ x, donc contrainte tenue), puis montée d'une qualité à la fois
    pour le maillon qui gagne le plus de coût par unité de contrainte consommée, tant que ça tient.
    Entrées : x (mm), cotes (mm, > 0), qmin/qmax (qualités permises), h, p, c, n, cible comme allouerCout.
    Sortie : (IT arrondis en mm, qualités ISO entières). Erreur ErreurChaine si une cote sort des tables.
    """
    h, c, n = (np.asarray(v, dtype=float) for v in (h, c, n))
    tab = []  # par maillon : [(qualité, IT mm)] croissant en IT, sans doublon d'IT
    for d, a, b in zip(cotes, qmin, qmax, strict=True):
        lst = []
        for q in range(int(a), int(b) + 1):
            v = iso286.toleranceIT(d, q) / 1000
            if not lst or v > lst[-1][1]:
                lst.append((q, v))
        tab.append(lst)
    idx = [max([j for j, (_, v) in enumerate(t) if v <= xi * (1 + 1e-12)] or [0]) for t, xi in zip(tab, x, strict=True)]

    def val(i, j):
        return tab[i][j][1]

    def cout(i, j):
        return c[i] * (val(i, j) / refIT()) ** (-n[i])

    conso = float(sum(h[i] * val(i, idx[i]) ** p for i in range(len(x))))
    while True:
        meilleur = None
        for i in range(len(x)):
            j = idx[i]
            if j + 1 >= len(tab[i]):
                continue
            d_conso = h[i] * (val(i, j + 1) ** p - val(i, j) ** p)
            if conso + d_conso > cible * (1 + 1e-12):
                continue
            score = (cout(i, j) - cout(i, j + 1)) / d_conso
            if meilleur is None or score > meilleur[0]:
                meilleur = (score, i, d_conso)
        if meilleur is None:
            break
        idx[meilleur[1]] += 1
        conso += meilleur[2]
    return np.array([val(i, idx[i]) for i in range(len(x))]), [tab[i][idx[i]][0] for i in range(len(x))]


def qualiteEquivalente(cote: float, it: float) -> int | None:
    """Qualité ISO la plus grossière dont l'IT ne dépasse pas it (mm) ; None si même IT1 est plus grand que it.

    Entrées : cote (mm, > 0), it (mm). Erreur ErreurChaine si la cote sort des tables.
    """
    ok = [q for q in iso286.QUALITES if iso286.toleranceIT(cote, q) / 1000 <= it * (1 + 1e-9)]
    return max(ok) if ok else None
