"""Problème inverse : répartir les tolérances des maillons pour tenir la cote condition [Jmin ; Jmax].

Absent de l'application MATLAB : ajout du site, construit sur les mêmes conventions que le solveur (sensibilités
a_i = coef du solveur, σ_i = |a_i|·IT_i/(2k) en loi normale, |a_i|·IT_i/√12 en loi uniforme).

Critères :
- « pire_cas »    : Σ |a_i|·IT_i = Jmax − Jmin (garanti à 100 %) ;
- « statistique » : 2·k·σ_J = Jmax − Jmin, avec σ_J = √Σ σ_i² (même k que le procédé garanti).
Méthodes de répartition entre les maillons non figés :
- « egale »           : même IT pour tous ;
- « proportionnelle » : IT proportionnel à l'unité de tolérance ISO i = 0,45·∛D + 0,001·D (µm, D = cote en mm),
  c'est-à-dire une même qualité « continue » pour tous les maillons ;
- « iso »             : même qualité normalisée ISO 286 pour tous, la plus grossière qui tient le critère ;
- « cout_minimal »    : minimise Σ c_i·(IT_i/IT_ref)^(-n_i) (voir cout.py) sous le même critère, avec les bornes
  de qualité de chaque procédé ; sortie supplémentaire « cout » (coût relatif, gains, qualités équivalentes).
Les maillons figés gardent leurs écarts saisis. Les écarts des autres maillons sont centrés (± IT/2), puis un
maillon de réglage est décalé pour amener le jeu moyen au milieu de [Jmin ; Jmax].
"""

import math

import numpy as np

from chainecotes.core import cout as cout_mod
from chainecotes.core import iso286
from chainecotes.core.chaine import coefficientSigma, solveurChaine
from chainecotes.core.errors import ErreurChaine
from chainecotes.core.nombres import fr

METHODES = ("egale", "proportionnelle", "iso", "cout_minimal")
CRITERES = ("pire_cas", "statistique")
_ID = "Chaine:Inverse:"


def uniteTolerance(d: float) -> float:
    """Unité de tolérance ISO i = 0,45·∛D + 0,001·D.

    Entrée : D (mm, > 0). Sortie : i (µm).
    """
    return 0.45 * d ** (1 / 3) + 0.001 * d


def repartirTolerances(
    probleme: dict,
    methode: str = "egale",
    critere: str = "pire_cas",
    figes: list[int] | None = None,
    reglage: int | None = None,
    couts: list[dict | None] | None = None,
    arrondi: bool = False,
) -> dict:
    """Calcule les tolérances des maillons qui tiennent exactement la cote condition.

    Entrées : probleme (dict condition, reglages, maillons, comme solveurChaine ; Jmin et Jmax obligatoires),
    methode (« egale », « proportionnelle », « iso »), critere (« pire_cas », « statistique »),
    figes (indices 0..n-1 des maillons dont les écarts sont gardés), reglage (indice du maillon décalé pour
    centrer le jeu ; défaut : premier maillon non figé), couts (« cout_minimal » seulement : une entrée par
    maillon, None ou dict procede / c / n / itmin / itmax, voir cout.modeleMaillon ; défaut : procédé générique),
    arrondi (« cout_minimal » : arrondit chaque IT à une qualité ISO en gardant le critère tenu).
    Sortie : dict methode, critere, budget (mm, Jmax − Jmin), facteur (IT d'un poids unité, mm ; qualité ISO
    pour « iso »), qualite (int ou None), maillons (liste de dict nom, cote, fige, poids, IT, es, ei (mm),
    designation ; pour « cout_minimal », « cout » : dict total (relatif), egale, proportionnelle (coûts de ces
    répartitions soumises aux mêmes bornes de procédé que l'optimum, donc gains ≥ 0), gainEgale,
    gainProportionnelle (fractions, > 0 = économie), procedes, arrondi),
    decalage (mm, déplacement de la cote moyenne du maillon de réglage), reglage (indice),
    verification (sortie de solveurChaine sur la chaîne obtenue), tenue (bool), message (texte).
    Erreur : ErreurChaine si la condition n'a pas deux limites, si tout est figé, ou si les maillons figés
    consomment déjà tout le budget ; pour « cout_minimal », si un coût est invalide, si une cote est ≤ 0 ou s'il
    n'existe aucune solution dans les bornes des procédés.
    """
    if methode not in METHODES:
        raise ErreurChaine(
            _ID + "methode", f"Méthode inconnue : {methode!r} (egale, proportionnelle, iso, cout_minimal)."
        )
    if critere not in CRITERES:
        raise ErreurChaine(_ID + "critere", f"Critère inconnu : {critere!r} (pire_cas, statistique).")
    res = solveurChaine(probleme)
    c, k = res["condition"], res["k_sigma"]
    if not (math.isfinite(c["jmin"]) and math.isfinite(c["jmax"])):
        raise ErreurChaine(_ID + "limites", "Le problème inverse demande Jmin et Jmax (deux limites finies).")
    budget = c["jmax"] - c["jmin"]
    if budget <= 0:
        raise ErreurChaine(_ID + "limites", "Jmax doit être strictement supérieur à Jmin.")
    n = len(res["Nom"])
    figes = sorted({int(i) for i in (figes or []) if 0 <= int(i) < n})
    libres = [i for i in range(n) if i not in figes]
    if not libres:
        raise ErreurChaine(_ID + "figes", "Tous les maillons sont figés : il ne reste aucune tolérance à répartir.")
    a = np.abs(res["coef"])
    if np.all(a[libres] == 0):
        raise ErreurChaine(_ID + "figes", "Les maillons non figés n'ont aucune influence sur le jeu.")
    cs = np.array([coefficientSigma(loi, k) for loi in res["loi"]])
    it_fige = np.asarray(res["IT"])

    def tient(it):
        """Écart au critère (≤ 0 : tenu) pour un vecteur complet d'IT."""
        if critere == "pire_cas":
            return float(np.sum(a * it)) - budget
        return 2 * k * float(np.sqrt(np.sum((a * it * cs) ** 2))) - budget

    it = it_fige.copy()
    it[libres] = 0.0
    reste = -tient(it)
    if reste <= 0:
        raise ErreurChaine(
            _ID + "budget",
            "Les maillons figés consomment déjà toute la tolérance de la cote condition : libérez un maillon "
            "ou élargissez [Jmin ; Jmax].",
        )

    qualite = None
    cout_info = None
    cotes = np.asarray(res["Cote"])
    w = np.ones(n) if methode != "proportionnelle" else np.array([uniteTolerance(max(d, 1e-9)) for d in cotes])
    if methode in ("egale", "proportionnelle"):
        if critere == "pire_cas":
            facteur = (budget - float(np.sum(a[figes] * it_fige[figes]))) / float(np.sum(a[libres] * w[libres]))
        else:
            s_fige = float(np.sum((a[figes] * it_fige[figes] * cs[figes]) ** 2))
            facteur = math.sqrt((budget / (2 * k)) ** 2 - s_fige) / float(
                np.sqrt(np.sum((a[libres] * w[libres] * cs[libres]) ** 2))
            )
        it[libres] = w[libres] * facteur
    elif methode == "cout_minimal":
        if couts is not None and len(couts) != n:
            raise ErreurChaine(_ID + "couts", f"couts doit avoir une entrée par maillon ({n}).")
        mod = [cout_mod.modeleMaillon(couts[i] if couts else None) for i in range(n)]
        for i in libres:
            if not cotes[i] > 0:
                raise ErreurChaine(_ID + "cout", f"{res['Nom'][i]} : le modèle de coût demande une cote > 0.")
        cc, nn = (np.array([m[k] for m in mod], dtype=float) for k in ("c", "n"))
        lo, hi = (
            np.array([iso286.toleranceIT(cotes[i], mod[i][k]) / 1000 for i in libres]) for k in ("itmin", "itmax")
        )
        # sensibilité nulle : l'IT n'influe pas sur le jeu, on prend le plus lâche du procédé (coût minimal)
        actifs = [j for j, i in enumerate(libres) if a[i] > 0]
        p = 1 if critere == "pire_cas" else 2
        hh = a[libres] if p == 1 else (a[libres] * cs[libres]) ** 2
        if p == 1:
            cible = budget - float(np.sum(a[figes] * it_fige[figes]))
        else:
            cible = (budget / (2 * k)) ** 2 - float(np.sum((a[figes] * it_fige[figes] * cs[figes]) ** 2))
        x = hi.copy()
        x[actifs] = cout_mod.allouerCout(
            hh[actifs], p, cc[libres][actifs], nn[libres][actifs], lo[actifs], hi[actifs], cible
        )
        qs = None
        if arrondi:
            x, qs = cout_mod.arrondirIso(
                x, cotes[libres], [mod[i]["itmin"] for i in libres], [mod[i]["itmax"] for i in libres],
                hh, p, cc[libres], nn[libres], cible,
            )  # fmt: skip
        it[libres] = x
        facteur = None
        # références « égale » et « proportionnelle » soumises aux mêmes bornes de procédé que l'optimum,
        # pour que les gains soient comparables (un gain négatif n'aurait pas de sens métier)
        ref = {}
        for m, poids in (
            ("egale", np.ones(n)),
            ("proportionnelle", np.array([uniteTolerance(max(d, 1e-9)) for d in cotes])),
        ):
            xr = hi.copy()
            xr[actifs] = cout_mod.repartirBorne(hh[actifs], p, poids[libres][actifs], lo[actifs], hi[actifs], cible)
            ref[m] = cout_mod.coutTotal(xr, cc[libres], nn[libres])
        total = cout_mod.coutTotal(x, cc[libres], nn[libres])
        cout_info = {
            "total": total,
            "egale": ref["egale"],
            "proportionnelle": ref["proportionnelle"],
            "gainEgale": 1 - total / ref["egale"],
            "gainProportionnelle": 1 - total / ref["proportionnelle"],
            "procedes": [mod[i]["procede"] for i in libres],
            "arrondi": bool(arrondi),
        }
    else:
        for i in libres:
            if not cotes[i] > 0:
                raise ErreurChaine(_ID + "iso", f"{res['Nom'][i]} : une qualité ISO demande une cote > 0.")
        facteur = None
        for q in reversed(iso286.QUALITES):
            essai = it.copy()
            essai[libres] = [iso286.toleranceIT(cotes[i], q) / 1000 for i in libres]
            if tient(essai) <= 1e-12:
                qualite, facteur, it = q, float(q), essai
                break
        if qualite is None:
            raise ErreurChaine(_ID + "iso", "Même la qualité IT1 ne tient pas la cote condition avec ces maillons.")

    # écarts centrés, puis décalage du maillon de réglage pour centrer le jeu moyen
    es = np.asarray(res["ES"], dtype=float).copy()
    ei = np.asarray(res["EI"], dtype=float).copy()
    es[libres], ei[libres] = it[libres] / 2, -it[libres] / 2
    reglage = libres[0] if reglage is None or reglage not in libres else int(reglage)
    jmoy = float(np.sum((cotes + (es + ei) / 2) * res["coef"]))
    cible = (c["jmin"] + c["jmax"]) / 2
    decalage = 0.0
    if abs(res["coef"][reglage]) > 1e-9:  # cote à 90° : coef ≈ 6e-17, pas 0 exact
        decalage = (cible - jmoy) / float(res["coef"][reglage])
        es[reglage] += decalage
        ei[reglage] += decalage

    maillons = []
    for i in range(n):
        brut = dict(probleme["maillons"][i])
        brut.update({"iso": None, "es": float(es[i]), "ei": float(ei[i])})
        maillons.append(brut)
    verif = solveurChaine({**probleme, "maillons": maillons})
    if critere == "pire_cas":
        tenue = verif["CF_min"] >= c["jmin"] - 1e-9 and verif["CF_max"] <= c["jmax"] + 1e-9
    else:
        tenue = (
            verif["CF_moy"] - k * verif["CF_sigma"] >= c["jmin"] - 1e-9
            and verif["CF_moy"] + k * verif["CF_sigma"] <= c["jmax"] + 1e-9
        )
    lignes = []
    for i, m in enumerate(res["maillons"]):
        lignes.append(
            {
                "nom": m["nom"],
                "cote": float(cotes[i]),
                "fige": i in figes,
                "poids": None if methode in ("iso", "cout_minimal") else float(w[i]),
                "IT": float(es[i] - ei[i]),
                "es": float(es[i]),
                "ei": float(ei[i]),
                "designation": f"IT{qualite}" if (methode == "iso" and i in libres) else "",
            }
        )
        if methode == "cout_minimal" and i in libres:
            q = qs[libres.index(i)] if qs else cout_mod.qualiteEquivalente(cotes[i], float(es[i] - ei[i]))
            lignes[-1]["designation"] = "" if q is None else (f"IT{q}" if qs else f"≈ IT{q}")
            lignes[-1]["qualiteEquivalente"] = q
    nom_critere = "au pire des cas" if critere == "pire_cas" else f"en statistique (± {fr(k, 'g')} σ)"
    message = (
        f"Tolérances réparties {nom_critere} sur {len(libres)} maillon(s) ; "
        f"{'le jeu est conforme' if tenue else 'le jeu est non conforme'}."
    )
    if critere == "statistique" and verif["decentrage"] > 0:
        message += (
            f" Le critère suppose le procédé centré : avec le décentrage de {fr(verif['decentrage'], 'g')} σ saisi, "
            "la moyenne réelle du jeu s'écarte du milieu de [Jmin ; Jmax] (voir ppm et Cpk de la vérification)."
        )
    return {
        "methode": methode,
        "critere": critere,
        "budget": budget,
        "facteur": facteur,
        "qualite": qualite,
        "maillons": lignes,
        "decalage": decalage,
        "reglage": reglage,
        "verification": verif,
        "tenue": bool(tenue),
        "message": message,
        **({"cout": cout_info} if cout_info else {}),
    }
