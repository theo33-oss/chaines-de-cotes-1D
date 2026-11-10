"""Répartition des tolérances d'une chaîne (problème inverse) : orchestration, lignes du résultat, explication, procédés.

Le calcul est dans chainecotes.core.inverse ; ce module relie les choix de l'utilisateur (méthode, critère, maillons figés,
procédés, valeurs d'atelier) à ce calcul et prépare les données à afficher, sans aucune interface (utilisé par
l'application de bureau et par la page web). Ce module n'importe ni Qt, ni pandas, ni plotly.
"""

import copy
import math

from chainecotes.core import cout as cout_mod
from chainecotes.core.chaine import solveurChaine
from chainecotes.core.errors import ErreurChaine
from chainecotes.core.inverse import repartirTolerances
from chainecotes.core.nombres import fr

CHAMPS_ATELIER = ("c", "n", "itmin", "itmax")  # valeurs d'un procédé que l'atelier peut remplacer


def procedesDisponibles() -> dict[str, str]:
    """Procédés disponibles : identifiant → nom, dans l'ordre de data/procedes.json."""
    return {p["id"]: p["nom"] for p in cout_mod.listeProcedes()}


def specsProcedes(procedes: list, atelier: dict | None = None) -> list[dict]:
    """Un dict « procede » par maillon, complété des valeurs d'atelier qui diffèrent de data/procedes.json.

    Entrées : procedes (identifiant de procédé de chaque maillon ; vide ou None = premier procédé de la liste),
    atelier ({procédé: {c, n, itmin, itmax}}, valeurs partielles permises). Sortie : liste de dicts de modeleMaillon.
    """
    base = {p["id"]: p for p in cout_mod.listeProcedes()}
    atelier = atelier or {}
    specs = []
    for pid in procedes:
        pid = pid or next(iter(base))
        spec = {"procede": pid}
        for champ in CHAMPS_ATELIER:
            v = atelier.get(pid, {}).get(champ, base[pid][champ])
            if v != base[pid][champ]:
                spec[champ] = v
        specs.append(spec)
    return specs


def repartir(
    probleme: dict,
    methode: str,
    critere: str,
    figes: list[int],
    reglage: int,
    procedes: list | None = None,
    atelier: dict | None = None,
    arrondi: bool = False,
) -> dict:
    """Répartit les tolérances et garde le problème calculé avec les IT d'avant.

    Entrées : probleme (dict condition, reglages, maillons ; Jmin et Jmax obligatoires), methode (« egale »,
    « proportionnelle », « iso », « cout_minimal »), critere (« pire_cas », « statistique »), figes (indices des
    maillons gardés), reglage (indice du maillon de réglage), procedes (« cout_minimal » : procédé de chaque maillon),
    atelier (valeurs d'atelier), arrondi (« cout_minimal » : IT arrondis aux qualités ISO).
    Sortie : dict sortie (core.inverse.repartirTolerances), probleme (copie), itAvant (IT saisis, mm), specs (ou None).
    Erreur : ErreurChaine, voir repartirTolerances.
    """
    cout = methode == "cout_minimal"
    specs = specsProcedes(procedes or [None] * len(probleme["maillons"]), atelier) if cout else None
    sortie = repartirTolerances(probleme, methode, critere, figes, reglage, specs, bool(cout and arrondi))
    itAvant = [float(x) for x in solveurChaine(probleme)["IT"]]
    return {"sortie": sortie, "probleme": copy.deepcopy(probleme), "itAvant": itAvant, "specs": specs}


def problemeRepartition(garde: dict) -> dict:
    """Problème calculé avec les écarts de la répartition (ES / EI calculés, désignation ISO vidée).

    Entrée : garde (sortie de repartir). Sortie : copie du problème.
    """
    apres = copy.deepcopy(garde["probleme"])
    for m, ligne in zip(apres["maillons"], garde["sortie"]["maillons"], strict=True):
        m.update({"iso": None, "es": ligne["es"], "ei": ligne["ei"]})
    return apres


def coutMaillon(spec: dict, it: float) -> float | None:
    """Coût relatif c·(IT/IT_ref)^(-n) d'un maillon (None si IT ≤ 0 : coût non défini)."""
    if not it > 0:
        return None
    m = cout_mod.modeleMaillon(spec)
    return m["c"] * (it / cout_mod.refIT()) ** (-m["n"])


def qualiteAvant(cote: float, it: float) -> str:
    """Qualité ISO équivalente d'un IT saisi, en texte (« ≈ IT7 », ou « — » si non définie)."""
    try:
        q = cout_mod.qualiteEquivalente(cote, it) if cote > 0 and it > 0 else None
    except ErreurChaine:
        q = None
    return "—" if q is None else f"≈ IT{q}"


def coutsAvantApres(garde: dict) -> tuple[list, list] | None:
    """Coût relatif de chaque maillon avant et après (« cout_minimal » seulement, sinon None)."""
    specs = garde.get("specs")
    if not garde["sortie"].get("cout") or specs is None:
        return None
    lignes = garde["sortie"]["maillons"]
    avant = [coutMaillon(s, x) for s, x in zip(specs, garde["itAvant"], strict=True)]
    apres = [coutMaillon(s, m["IT"]) for s, m in zip(specs, lignes, strict=True)]
    return avant, apres


def colonnesRepartition(garde: dict) -> dict[str, list]:
    """Colonnes du tableau du résultat : maillon, cote, figé, IT avant et après, écarts, désignation (+ coûts).

    Entrée : garde (sortie de repartir). Sortie : dict {titre de colonne: valeurs}, valeurs brutes (mm).
    """
    sortie, itAvant, lignes = garde["sortie"], garde["itAvant"], garde["sortie"]["maillons"]
    colonnes = {
        "Maillon": [m["nom"] for m in lignes],
        "Cote (mm)": [m["cote"] for m in lignes],
        "Figé": [m["fige"] for m in lignes],
        "IT avant (mm)": list(itAvant),
        "IT après (mm)": [m["IT"] for m in lignes],
        "ES (mm)": [m["es"] for m in lignes],
        "EI (mm)": [m["ei"] for m in lignes],
        "Désignation": [m["designation"] or "—" for m in lignes],
    }
    couts = coutsAvantApres(garde)
    if sortie.get("cout") and couts:
        procedes = procedesDisponibles()
        colonnes |= {
            "Procédé": [procedes.get(s.get("procede"), "générique") for s in garde["specs"]],
            "Qualité avant": [qualiteAvant(m["cote"], x) for m, x in zip(lignes, itAvant, strict=True)],
            "Coût avant": couts[0],
            "Coût après": couts[1],
        }
    return colonnes


def tableProcedes(specs: list[dict]) -> dict:
    """Procédés utilisés par la répartition : coût c, exposant n, qualités IT, origine et source.

    Entrée : specs (liste de modeleMaillon, une par maillon). Sortie : dict legende, lignes (liste de dict Procédé, c, n,
    IT min, IT max, Origine, Source), avertissement (niveau de fiabilité des valeurs indicatives, ou None).
    """
    effectifs = {}
    for s in specs:  # valeurs réellement utilisées : celles de l'atelier si elles ont été saisies
        effectifs.setdefault(s.get("procede") or "generique", s)
    lignes = []
    for p in cout_mod.listeProcedes():
        if p["id"] not in effectifs:
            continue
        m = cout_mod.modeleMaillon(effectifs[p["id"]])
        atelier = any(m[c] != p[c] for c in CHAMPS_ATELIER)
        lignes.append(
            {
                "Procédé": p["nom"],
                "c": m["c"],
                "n": m["n"],
                "IT min": f"IT{m['itmin']}",
                "IT max": f"IT{m['itmax']}",
                "Origine": "Valeurs de l'atelier (saisies)" if atelier else "Indicatif, à valider",
                "Source": "Saisie de l'utilisateur" if atelier else p["source"],
            }
        )
    return {
        "legende": "Modèle de coût : coût = c × (IT / IT_ref)^(−n), IT_ref = 0,1 mm. Coûts relatifs, jamais des prix.",
        "lignes": lignes,
        "avertissement": cout_mod.fiabiliteProcedes() if any(x["Origine"].startswith("Indicatif") for x in lignes) else None,
    }


def _tex(v: float, fmt: str = ".4f") -> str:
    """Nombre à la française pour une formule (la virgule entre accolades n'ajoute pas d'espace)."""
    return fr(v, fmt).replace(",", "{,}")


def explicationRepartition(sortie: dict) -> list[dict]:
    """Méthode retenue et formule du critère remplie avec les valeurs obtenues.

    Entrée : sortie (core.inverse.repartirTolerances). Sortie : liste de blocs {texte (markdown), formules (LaTeX)}, dans
    l'ordre : critère, méthode, centrage.
    """
    v = sortie["verification"]
    k = v["k_sigma"]
    c = v["condition"]
    a = [abs(float(x)) for x in v["coef"]]
    it = [float(x) for x in v["IT"]]
    budget = f"J_{{max}} - J_{{min}} = {_tex(c['jmax'])} - {_tex(c['jmin'])} = {_tex(sortie['budget'])}"
    if sortie["critere"] == "pire_cas":
        texte = (
            "**Critère du pire des cas** : la somme des IT (pondérés par la sensibilité |aᵢ| de chaque maillon) "
            "doit égaler l'intervalle autorisé ; le jeu est alors garanti à 100 %."
        )
        termes = " + ".join(f"{_tex(ai, 'g')} \\times {_tex(x)}" for ai, x in zip(a, it, strict=True))
        total = sum(ai * x for ai, x in zip(a, it, strict=True))
        formules = [f"\\sum_i |a_i|\\,IT_i = {termes} = {_tex(total)}"]
    else:
        texte = (
            f"**Critère statistique** : avec des cotes indépendantes, les écarts types s'ajoutent en quadrature ; "
            f"l'intervalle ± {fr(k, 'g')} σ du jeu doit égaler l'intervalle autorisé. σᵢ = |aᵢ|·ITᵢ/(2k) en loi "
            "normale, |aᵢ|·ITᵢ/√12 en loi uniforme."
        )
        sig = [
            ai * x / (2 * k) if loi == "normale" else ai * x / math.sqrt(12)
            for ai, x, loi in zip(a, it, v["loi"], strict=True)
        ]
        termes = " + ".join(f"{_tex(s, '.5f')}^2" for s in sig)
        total = 2 * k * math.sqrt(sum(s * s for s in sig))
        formules = [f"2k\\,\\sigma_J = 2 \\times {_tex(k, 'g')} \\times \\sqrt{{{termes}}} = {_tex(total)}"]
    blocs = [{"texte": texte, "formules": [*formules, budget]}]
    if sortie["methode"] == "egale":
        blocs.append(
            {
                "texte": f"**Répartition égale** : tous les maillons non figés reçoivent le même IT, "
                f"ici {fr(sortie['facteur'] * 1000, '.1f')} µm.",
                "formules": [],
            }
        )
    elif sortie["methode"] == "proportionnelle":
        blocs.append(
            {
                "texte": "**Répartition proportionnelle à l'unité de tolérance ISO** : un maillon long reçoit un IT plus "
                "large, comme dans la norme ISO 286 (même qualité « continue » pour tous).",
                "formules": [
                    f"IT_i = f \\cdot i(D_i), \\quad i(D) = 0{{,}}45\\,\\sqrt[3]{{D}} + 0{{,}}001\\,D \\;(\\mu m), "
                    f"\\quad f = {_tex(sortie['facteur'] * 1000, '.3f')}"
                ],
            }
        )
    elif sortie["methode"] == "cout_minimal":
        blocs.append(
            {
                "texte": "**Coût minimal** : chaque maillon reçoit l'IT qui minimise la somme des coûts c × (IT / 0,1 mm)^(−n) "
                "de son procédé, sous le critère choisi et dans les qualités que ce procédé tient (multiplicateurs de "
                "Lagrange). Les coûts sont relatifs et indicatifs.",
                "formules": [],
            }
        )
    else:
        blocs.append(
            {
                "texte": f"**Qualité ISO la plus proche** : on essaie les qualités ISO 286 de la plus grossière à la plus fine ; "
                f"IT{sortie['qualite']} est la plus grossière qui tient le critère (les maillons non figés reçoivent "
                "l'IT de leur cote dans cette qualité).",
                "formules": [],
            }
        )
    nomReglage = sortie["maillons"][sortie["reglage"]]["nom"]
    blocs.append(
        {
            "texte": f"**Centrage** : les écarts des maillons non figés sont centrés (± IT/2), puis « {nomReglage} » est décalé "
            f"de {fr(sortie['decalage'] * 1000, '+.1f')} µm pour amener le jeu moyen au milieu de [Jmin ; Jmax].",
            "formules": [],
        }
    )
    return blocs
