"""Pont entre la page web (JavaScript) et le calcul Python de l'application : entrées et sorties en JSON.

Le navigateur appelle ces fonctions par Pyodide ; elles servent aussi aux essais en Python ordinaire (essai_pont.py).
Rien n'est calculé en JavaScript : la page ne fait qu'afficher ce que ce module renvoie.
"""

import json
import math

from chainecotes.core import ajustement as ajust
from chainecotes.core import cout as cout_mod
from chainecotes.core.chaine import capabilitesMaillons, libelleVerdict
from chainecotes.core.donnees import chargerJson
from chainecotes.core.construction import construireChaines, exempleAssistant, lireSaisie, surfaces
from chainecotes.core.errors import ErreurChaine
from chainecotes.core.formules import texVersHtml
from chainecotes.core.inertiel import analyseInertielle, verdictBender
from chainecotes.core.iso286 import (
    COTES_USUELLES,
    LETTRES_ALESAGE,
    LETTRES_ARBRE,
    QUALITES,
    USAGE_QUALITE,
    libellesPlages,
    lireDesignation,
)
from chainecotes.core.materiaux import (
    PERSONNALISE,
    alphaMateriau,
    courbesMateriaux,
    domaineEmploi,
    filtrerLignes,
    listeMateriaux,
    nomsMateriaux,
    sourcesMateriaux,
)
from chainecotes.core.nombres import fr
from chainecotes.core.sensibilite import gainSiResserre, indicesSensibilite
from chainecotes.plots import graphiques
from chainecotes.plots._common import intervalle
from chainecotes.plots.ajustement import figureZones
from chainecotes.plots.assistant import figureConstruction
from chainecotes.plots.materiaux import figureDilatation
from chainecotes.plots.optimisation import figureCoutsMaillons, figureITAvantApres, figureScenarios
from chainecotes.plots.schema import figureSchema
from chainecotes.plots.mecanisme import figureCpkMecanisme
from chainecotes.services import mecanisme as meca
from chainecotes.services import procedes_atelier, projet_io
from chainecotes.services import repartition as rep
from chainecotes.services.cartouche import CHAMPS as CHAMPS_CARTOUCHE
from chainecotes.services.cartouche import STATUTS, empreinte
from chainecotes.services.scenarios import comparerScenarios
from chainecotes.services.calcul import apercuChaine, calculerChaine
from chainecotes.services.conclusion import conclusionEtude
from chainecotes.services.controles import controlerProbleme
from chainecotes.services.exemples import chargerExemple, lignesMaillons, listeExemples, texteCondition
from chainecotes.services.explications import explicationsCalcul

N_TIRAGES = 100_000  # plus léger que le bureau (200 000) : la page tourne sur le processeur du visiteur
TOL = 1e-9  # mm, même tolérance de comparaison que le solveur
CLASSE = {"Conforme": "succes", "Non conforme": "erreur", "Sans limite": "info"}


# ---------- exemples, matériaux ----------


def exemples() -> str:
    """Liste des exemples (id, titre, description) en JSON."""
    return json.dumps([{k: e[k] for k in ("id", "titre", "description") if k in e} for e in listeExemples()])


def charger(identifiant: str) -> str:
    """Problème d'un exemple en JSON."""
    return json.dumps(chargerExemple(identifiant), allow_nan=False)


def materiaux() -> str:
    """Noms des matériaux connus (JSON) ; « Personnalisé » est exclu : la colonne α sert aux valeurs libres."""
    return json.dumps([n for n in nomsMateriaux() if n != PERSONNALISE])


# ---------- saisie de la page → problème ----------


def _vide(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def _nettoyer(p: dict, garderCartouche: bool = False) -> dict:
    """Cases vides de la page (texte vide) → None pour la condition et les réglages, champ absent pour un maillon."""
    sortie = {
        "condition": {k: (None if _vide(v) else v) for k, v in p.get("condition", {}).items()},
        "reglages": {k: (None if _vide(v) else v) for k, v in p.get("reglages", {}).items()},
        "maillons": [{k: v for k, v in m.items() if not _vide(v)} for m in p.get("maillons", [])],
    }
    if garderCartouche and p.get("cartouche"):
        sortie["cartouche"] = p["cartouche"]
    return sortie


def _figure(ident: str, titre: str, fig, legende: str) -> dict:
    return {"id": ident, "titre": titre, "legende": legende, "fig": json.loads(fig.to_json())}


def _table(entetes: list[str], lignes: list[list], classes: list[str] | None = None) -> dict:
    """Tableau pour la page : en-têtes, lignes de textes, et si besoin une classe de couleur par ligne."""
    return {"entetes": entetes, "lignes": [[str(c) for c in ligne] for ligne in lignes], "classes": classes}


def apercu(texte: str) -> str:
    """Aperçu pendant la saisie : schéma de la chaîne, pire des cas et contrôles de cohérence (sans Monte-Carlo).

    Sortie JSON : fig, legende (schéma), erreur (texte ou null), pireCas (niveau, texte, ou null) et controles
    (liste de niveau, maillon, message).
    """
    probleme = _nettoyer(json.loads(texte))
    ap = apercuChaine(probleme)
    fig, legende = figureSchema(probleme, ap)
    pire = None
    if "erreur" not in ap:
        c, p = ap["res"]["condition"], ap["verdicts"]["pireCas"]
        verdict = libelleVerdict(p["ok"], c)
        pire = {
            "niveau": CLASSE[verdict],
            "texte": f"Pire des cas : {verdict.lower()}. Jeu de {fr(p['min'])} à {fr(p['max'])} mm, "
            f"limites exigées {intervalle(c['jmin'], c['jmax'])} mm.",
        }
    return json.dumps(
        {
            "fig": json.loads(fig.to_json()),
            "legende": legende,
            "erreur": ap.get("erreur"),
            "pireCas": pire,
            "controles": [{k: x[k] for k in ("niveau", "maillon", "message")} for x in controlerProbleme(probleme)],
        },
        allow_nan=False,
    )


# ---------- calcul complet ----------


def _resultats(bundle: dict) -> dict:
    """Valeurs clés, verdicts par méthode et tableau des maillons (onglet « Résultats »)."""
    res, v, mc = bundle["res"], bundle["verdicts"], bundle["mc"]
    c, k = res["condition"], res["k_sigma"]
    exact = bundle.get("ppmExact")
    if mc is None:
        ppmMc = "—"
    else:
        ppmMc = f"< {fr(mc['resolutionPpm'], '.3g')} ppm" if mc["nHors"] == 0 else f"{fr(mc['ppm'], '.4g')} ppm"
    valeurs = [
        ["Jeu nominal", f"{fr(res['CF_nom'])} mm"],
        ["Jeu moyen", f"{fr(res['CF_moy'])} mm"],
        ["Jeu mini", f"{fr(res['CF_min'])} mm"],
        ["Jeu maxi", f"{fr(res['CF_max'])} mm"],
        ["Écart-type σ", f"{fr(res['CF_sigma'], '.5f')} mm"],
        ["Cp", fr(v["cp"], ".3g")],
        ["Cpk", fr(v["cpk"], ".3g")],
        ["ppm (formule normale)" if exact is not None else "ppm (formule)", f"{fr(v['ppm'], '.4g')} ppm"],
        *([["ppm (lois des maillons)", f"{fr(exact, '.4g')} ppm"]] if exact is not None else []),
        ["ppm (Monte-Carlo)", ppmMc],
        *([["Décalage thermique", f"{fr(res['dJ_th'], '+.4f')} mm"]] if res["thermique_actif"] else []),
    ]
    plages = [
        ("Pire des cas", v["pireCas"]),
        (f"RSS ± {fr(k, 'g')} σ", v["rssK"]),
        ("RSS ± 6 σ", v["rss6"]),
        *([(f"RSS ± {fr(k, 'g')} σ (moyenne du procédé)", v["rssProc"])] if res["decalage"] != 0 else []),
        ("Statistique majorée (Bender, × 1,5)", verdictBender(res)),
    ]
    lignes = [[nom, fr(p["min"]), fr(p["max"]), libelleVerdict(p["ok"], c)] for nom, p in plages]
    if mc is not None:
        bas, haut = mc["quantiles"]["bas"], mc["quantiles"]["haut"]
        ok = bas >= c["jmin"] - TOL and haut <= c["jmax"] + TOL
        lignes.append(["Monte-Carlo 0,135–99,865 %", fr(bas), fr(haut), libelleVerdict(ok, c)])
    maillons = _table(
        ["Maillon", "ES (mm)", "EI (mm)", "IT (mm)", "C moy (mm)", "α (1e-6/K)", "Part pire cas (%)", "Part statistique (%)"],
        [
            [nom, fr(es), fr(ei), fr(it), fr(cm), fr(1e6 * float(a), ".2f"), fr(x["partPireCas"], ".1f"), fr(x["partVariance"], ".1f")]
            for nom, es, ei, it, cm, a, x in zip(
                res["Nom"], res["ES"], res["EI"], res["IT"], res["C_moy"], res["alpha"], bundle["contributions"], strict=True
            )
        ],
    )
    caps = capabilitesMaillons(res)
    capabilite = None
    if any(x["mesure"] for x in caps):
        capabilite = _table(
            ["Maillon", "Origine", "Moyenne (mm)", "σ (mm)", "Cp", "Cpk"],
            [
                [x["nom"], "Mesures de l'atelier" if x["mesure"] else "Modèle de la loi", fr(x["moyenne"]),
                 fr(x["sigma"], ".5f"), fr(x["cp"], ".2f"), fr(x["cpk"], ".2f")]
                for x in caps
            ],
        )
    return {
        "metriques": valeurs,
        "verdicts": _table(["Méthode", "Jeu mini (mm)", "Jeu maxi (mm)", "Verdict"], lignes, [CLASSE[x[3]] for x in lignes]),
        "limites": f"Limites exigées : {intervalle(c['jmin'], c['jmax'])} mm.",
        "maillons": maillons,
        "legendeMaillons": "Part pire cas : |aᵢ|·ITᵢ/2 rapporté à la somme. Part statistique : σᵢ² rapporté à la variance du jeu.",
        "capabilite": capabilite,
    }


def _statistiques(bundle: dict) -> dict:
    """Tirage Monte-Carlo (tableau) et tolérancement inertiel de Pillet."""
    res, v, mc = bundle["res"], bundle["verdicts"], bundle["mc"]
    sortie = {"monteCarlo": None, "inertiel": None}
    if mc is not None:
        q = mc["quantiles"]
        ppmMc = f"< {fr(mc['resolutionPpm'], '.3g')} ppm" if mc["nHors"] == 0 else f"{fr(mc['ppm'], '.4g')} ppm"
        sortie["monteCarlo"] = {
            "texte": f"{mc['n']:,} tirages (graine {mc['graine']}).".replace(",", " "),
            "table": _table(
                ["Grandeur", "Monte-Carlo", "Formule"],
                [
                    ["Moyenne (mm)", fr(mc["moyenne"], ".5f"), fr(res["CF_moy"], ".5f")],
                    ["Écart-type (mm)", fr(mc["ecartType"], ".5f"), fr(res["CF_sigma"], ".5f")],
                    ["Quantile 0,135 % (mm)", fr(q["bas"], ".5f"), ""],
                    ["Médiane (mm)", fr(q["mediane"], ".5f"), ""],
                    ["Quantile 99,865 % (mm)", fr(q["haut"], ".5f"), ""],
                    ["Tirages hors limites", f"{mc['nHors']} sur {mc['n']}", ""],
                    ["ppm", ppmMc, f"{fr(v['ppm'], '.4g')} ppm"],
                    ["Cp", fr(mc["cp"], ".3g"), fr(v["cp"], ".3g")],
                    ["Cpk", fr(mc["cpk"], ".3g"), fr(v["cpk"], ".3g")],
                ],
            ),
        }
    r = analyseInertielle(res)
    inertiel = {
        "metriques": [
            ["Inertie du jeu", f"{fr(r['inertieJeu'], '.5f')} mm"],
            ["Cible du jeu", f"{fr(r['cible'], '.4f')} mm"],
            ["Inertie maxi", f"{fr(r['inertieMax'], '.5f')} mm"],
            ["Cpi", fr(r["cpi"], ".3g")],
        ],
        "table": None,
        "info": None,
    }
    if math.isfinite(r["inertieMax"]):
        inertiel["table"] = _table(
            ["Maillon", "σ (mm)", "Écart à la cote moyenne (mm)", "Inertie (mm)", "IT inertiel possible (mm)",
             "IT égal au pire des cas (mm)"],
            [[x["nom"], fr(x["sigma"]), fr(x["ecart"]), fr(x["inertie"]), fr(x["itInertiel"]), fr(x["itPireCas"])]
             for x in r["liens"]],
        )
    else:
        inertiel["info"] = "Le tolérancement inertiel demande les deux limites Jmin et Jmax de la cote condition."
    sortie["inertiel"] = inertiel
    return sortie


def _sensibilite(bundle: dict) -> dict:
    """Indices de Sobol (figure et tableau) et gain si un seul maillon est resserré à 50 % de son IT."""
    res = bundle["res"]
    fig, legende = graphiques.figureSensibilite(bundle)
    sortie = {"figure": _figure("sensibilite", "Sensibilité", fig, legende), "table": None}
    if res["CF_sigma"] > 0:
        indices, gains = indicesSensibilite(res), gainSiResserre(res, 0.5)
        sortie["table"] = _table(
            ["Maillon", "Rang", "Indice de Sobol (%)", "Part pire cas (%)", "σ du jeu si resserré (mm)",
             "Gain sur σ (%)", "Cpk si resserré", "ppm si resserré"],
            [
                [x["nom"], x["rang"], fr(100 * x["indice"], ".1f"), fr(100 * x["partPireCas"], ".1f"),
                 fr(g["sigma"], ".5f"), fr(g["gainSigmaPct"], ".1f"), fr(g["cpk"], ".3f"), fr(g["ppm"], ".3g")]
                for x, g in zip(indices, gains, strict=True)
            ],
        )
    return sortie


def calculer(texte: str) -> str:
    """Calcul complet d'un problème (JSON) : verdict, conseil, tableaux, figures Plotly (JSON), explications.

    Sortie JSON : {"erreur": message} si la saisie est invalide, sinon niveau, titre, conseil, details,
    avertissements, resultats, statistiques, figuresStatistiques, figuresGraphiques, sensibilite, explications.
    """
    try:
        probleme = _nettoyer(json.loads(texte))
        ap = apercuChaine(probleme)
        if "erreur" in ap:
            return json.dumps({"erreur": ap["erreur"]})
        bundle = calculerChaine(probleme, n=N_TIRAGES)
        conclusion = conclusionEtude(bundle)
        graphiquesVoulus = [
            ("comparaison", "Comparaison des méthodes", graphiques.figureComparaison),
            ("pareto", "Pareto", graphiques.figurePareto),
        ]
        if bundle["res"]["thermique_actif"]:
            graphiquesVoulus.append(("thermique", "Effet thermique", graphiques.figureEffetThermique))
        if bundle["jeuT"] is not None:
            graphiquesVoulus.append(("temperature", "Jeu selon la température", graphiques.figureJeuTemperature))
        statistiquesVoulues = [
            ("montecarlo", "Monte-Carlo", graphiques.figureMonteCarlo),
            ("distribution", "Distribution", graphiques.figureDistribution),
            ("risque", "Risque selon le Cp", graphiques.figureRisqueCp),
        ]
        return json.dumps(
            {
                "niveau": conclusion["niveau"],
                "titre": conclusion["titre"],
                "conseil": conclusion["conseils"][0] if conclusion["conseils"] else "",
                "conseils": conclusion["conseils"],
                "details": conclusion["details"],
                "avertissements": bundle["avertissements"],
                "resultats": _resultats(bundle),
                "statistiques": _statistiques(bundle),
                "figuresStatistiques": [_figure(i, t, *f(bundle)) for i, t, f in statistiquesVoulues],
                "figuresGraphiques": [_figure(i, t, *f(bundle)) for i, t, f in graphiquesVoulus],
                "sensibilite": _sensibilite(bundle),
                "explications": [
                    {"titre": s["titre"], "texte": s["texte"], "formules": [texVersHtml(f) for f in s["formules"]]}
                    for s in explicationsCalcul(bundle)
                ],
            },
            allow_nan=False,
        )
    except ErreurChaine as e:
        return json.dumps({"erreur": e.message})
    except (ValueError, TypeError, KeyError) as e:
        return json.dumps({"erreur": f"Saisie incomplète : {e}"})


# ---------- bibliothèque d'exemples ----------


def _g(v) -> str:
    """Valeur d'un tableau d'exemple : nombre à la française, vide pour une case absente."""
    return "" if v is None else (fr(v, "g") if isinstance(v, (int, float)) else str(v))


def cartes() -> str:
    """Une carte par exemple : présentation, cote condition, maillons et pire des cas (sans Monte-Carlo), en JSON."""
    sortie = []
    for e in listeExemples():
        probleme = chargerExemple(e["id"])
        ap = apercuChaine(probleme)
        lignes = lignesMaillons(probleme, ap)
        carte = {
            "id": e["id"], "titre": e["titre"], "description": e["description"], "source": e.get("source", ""),
            "methodologie": e.get("methodologie", []), "condition": texteCondition(probleme["condition"]),
            "maillons": _table(list(lignes[0]), [[_g(v) for v in ligne.values()] for ligne in lignes]),
            "erreur": ap.get("erreur"), "pireCas": None,
        }
        if "erreur" not in ap:
            p = ap["verdicts"]["pireCas"]
            carte["pireCas"] = {"mini": f"{fr(p['min'])} mm", "maxi": f"{fr(p['max'])} mm", "ok": p["ok"]}
        sortie.append(carte)
    return json.dumps(sortie, allow_nan=False)


def schemaExemple(identifiant: str) -> str:
    """Schéma d'un exemple (construit à la demande : une figure par carte alourdirait la page)."""
    fig, legende = figureSchema(chargerExemple(identifiant))
    return json.dumps({"fig": json.loads(fig.to_json()), "legende": legende})


# ---------- tables ISO 286 ----------


def _ecarts(r: dict, titre: str) -> dict:
    """Écarts d'une désignation lue, en texte : ES/EI (alésage) ou es/ei (arbre), IT et zone de cote."""
    sup, inf = ("ES", "EI") if r["type"] == "alésage" else ("es", "ei")
    return {
        "titre": titre,
        "valeurs": [[f"{sup} (mm)", fr(r["es"], "g")], [f"{inf} (mm)", fr(r["ei"], "g")], ["IT (µm)", fr(r["IT"], "g")]],
        "legende": f"{r['designation']} ({r['type']}) : cote de {fr(r['cote'] + r['ei'], 'g')} à "
        f"{fr(r['cote'] + r['es'], 'g')} mm ; plage de la table : {r['plage']}.",
    }


def iso286Donnees() -> str:
    """Tables ISO 286 et listes de la calculatrice (valeurs de data/iso286.json, rien n'est recopié), en JSON."""
    t = chargerJson("iso286.json")
    plages = libellesPlages(t["bornes"])

    def tableau(colonnes: dict) -> dict:
        return {"plages": plages, "colonnes": colonnes}

    return json.dumps(
        {
            "cotesUsuelles": list(COTES_USUELLES),
            "borneMax": t["bornes"][-1],
            "lettresArbre": list(LETTRES_ARBRE),
            "lettresAlesage": list(LETTRES_ALESAGE),
            "qualites": [{"q": q, "texte": f"IT{q}" + (f" · {USAGE_QUALITE[q]}" if q in USAGE_QUALITE else "")} for q in QUALITES],
            "it": tableau({f"IT{q}": t["it"][str(q)] for q in QUALITES}),
            "arbre": tableau(t["arbre"]),
            "alesage": tableau(t["alesage"]),
            "delta": tableau({f"Δ qualité {q}": v for q, v in t["delta"].items()}),
            "source": t["Source"],
        }
    )


def iso286Lire(texte: str) -> str:
    """Lit une désignation (« 50 H7 ») : valeur de l'application MATLAB et valeur normalisée ISO 286-1 (JSON)."""
    try:
        matlab, norme = lireDesignation(texte, arrondiJs=False), lireDesignation(texte, arrondiJs=True)
    except ErreurChaine as e:
        return json.dumps({"erreur": e.message})
    if (matlab["es"], matlab["ei"]) == (norme["es"], norme["ei"]):
        titre = f"{matlab['designation']} : valeur normalisée, identique à l'application MATLAB"
        return json.dumps({"avertissement": "", "valeurs": [_ecarts(matlab, titre)]})
    return json.dumps(
        {
            "avertissement": matlab["avertissement"],
            "valeurs": [
                _ecarts(matlab, "Valeur de l'application MATLAB (utilisée par le calcul de la chaîne)"),
                _ecarts(norme, "Valeur normalisée ISO 286-1"),
            ],
        }
    )


# ---------- assistant d'ajustement ----------


def ajustementFonctions() -> str:
    """Fonctions d'ajustement proposées (JSON {code: libellé}) et cotes usuelles."""
    return json.dumps({"fonctions": ajust.fonctionsDisponibles(), "cotes": list(COTES_USUELLES), "borneMax": chargerJson("iso286.json")["bornes"][-1]})


def ajustement(cote: float, fonction: str, systeme: str, choix: str = "") -> str:
    """Ajustements candidats classés, et détail (écarts, jeux, schéma) de celui qui est choisi (le premier par défaut)."""
    try:
        candidats = ajust.choisirAjustement(float(cote), fonction, systeme)
    except ErreurChaine as e:
        return json.dumps({"erreur": e.message})
    if not candidats:
        return json.dumps({"erreur": None, "candidats": None, "choisi": None})
    noms = [c["designation"] for c in candidats]
    c = candidats[noms.index(choix)] if choix in noms else candidats[0]
    trou, arbre = ajust.pieces(c["designation"], float(cote))
    fig, legende = figureZones(c["designation"], float(cote))
    pieces = []
    for piece, titre in ((trou, "Alésage"), (arbre, "Arbre")):
        sup, inf = ("ES", "EI") if piece["type"] == "alésage" else ("es", "ei")
        pieces.append([[f"{titre} {sup} (mm)", fr(piece["es"], "g")], [f"{titre} {inf} (mm)", fr(piece["ei"], "g")],
                       [f"{titre} IT (µm)", fr(piece["IT"], "g")]])
    return json.dumps(
        {
            "erreur": None,
            "noms": noms,
            "candidats": _table(
                ["Rang", "Ajustement", "Jeu mini (mm)", "Jeu maxi (mm)", "Nature", "IT alésage (µm)", "IT arbre (µm)", "Usage"],
                [[x["rang"], x["designation"], fr(x["jeuMini"], ".4f"), fr(x["jeuMaxi"], ".4f"), x["nature"],
                  fr(x["ITAlesage"], "g"), fr(x["ITArbre"], "g"), x["usage"]] for x in candidats],
            ),
            "choisi": {
                "designation": c["designation"], "pieces": pieces, "description": c["description"],
                "usage": f"Usage : {c['usage']} Risque : {c['risque']}", "avertissement": c["avertissement"],
                "jeux": [["Jeu mini", f"{fr(c['jeuMini'], '.4f')} mm"], ["Jeu maxi", f"{fr(c['jeuMaxi'], '.4f')} mm"]],
                "nature": f"Nature à cette cote : {c['nature']}.",
            },
            "fig": json.loads(fig.to_json()),
            "legende": legende,
        },
        allow_nan=False,
    )


def maillonsAjustement(designation: str, cote: float, nomsPris: str = "[]", tref: float = 20.0) -> str:
    """Alésage (sens +) et arbre (sens −) d'un ajustement, prêts à ajouter à la chaîne de la page « Analyser » (JSON)."""
    try:
        return json.dumps({"maillons": ajust.maillonsAjustement(designation, float(cote), json.loads(nomsPris), float(tref))})
    except ErreurChaine as e:
        return json.dumps({"erreur": e.message})


# ---------- matériaux et dilatation ----------


def _lignesMateriaux() -> list[dict]:
    return [
        {
            "Matériau": m["nom"], "Famille": m["famille"], "α (10⁻⁶/K)": m["alpha"] * 1e6, "Plage de α (°C)": m["plage"],
            "Fiabilité": m["fiabilite"], "Sources": m["sources"],
            "Courbe": m["courbeNom"] + (" (recalée)" if m["recale"] else ""), "Domaine d'emploi": domaineEmploi(m),
        }
        for m in listeMateriaux()
        if m["nom"] != PERSONNALISE
    ]


def materiauxTableau(texte: str = "", familles: str = "[]") -> str:
    """Tableau des matériaux filtré par mots et par familles (JSON) ; liste de toutes les familles."""
    toutes = _lignesMateriaux()
    lignes = filtrerLignes(toutes, texte, json.loads(familles))
    return json.dumps(
        {
            "familles": sorted({x["Famille"] for x in toutes}),
            "total": len(toutes),
            "tableau": _table(list(toutes[0]), [[fr(v, ".2f") if isinstance(v, float) else v for v in x.values()] for x in lignes]),
        }
    )


def materiauxSources() -> str:
    """Sources citées et courbes de dilatation du classeur (JSON)."""
    courbes = [c for c in courbesMateriaux() if c["points"]]
    return json.dumps(
        {
            "sources": _table(["Clé", "Source", "Lien"], [[s["cle"], s["source"], s["lien"]] for s in sourcesMateriaux()]),
            "courbes": _table(
                ["Courbe", "Description", "Points", "Températures (°C)"],
                [[c["cle"], c["description"], len(c["points"]),
                  f"{fr(min(p['T'] for p in c['points']), 'g')} à {fr(max(p['T'] for p in c['points']), 'g')}"] for c in courbes],
            ),
        }
    )


def dilatation(nom: str, tref: float, temperature: float) -> str:
    """α moyen et allongement d'un matériau entre Tref et T, avis sur le domaine d'emploi et courbe de dilatation."""
    m = next((x for x in listeMateriaux() if x["nom"] == nom and x["nom"] != PERSONNALISE), None)
    if m is None:
        return json.dumps({"erreur": f"Matériau inconnu : {nom!r}."})
    tref, temperature = float(tref), float(temperature)
    if temperature < -273.15 or tref < -273.15:
        return json.dumps({"erreur": "Une température ne peut pas être sous le zéro absolu (−273,15 °C)."})
    r = alphaMateriau(nom, temperature, tref)
    messages = []
    a100 = alphaMateriau(nom, 100.0, 20.0)["alpha"]
    if m["courbeNom"] and not m["recale"] and abs(a100 / m["alpha"] - 1) > 0.05:
        messages.append({"niveau": "avertissement", "texte": f"Le calcul suit la courbe générique {m['courbeNom']} : α moyen 20-100 °C = "
                         f"{fr(a100 * 1e6, '.2f')} × 10⁻⁶/K (tableau : {fr(m['alpha'] * 1e6, '.2f')})."})
    if r["horsDomaine"]:
        messages.append({"niveau": "avertissement", "texte": f"Hors domaine à {fr(temperature, 'g')} °C : {r['motif']}."})
    elif math.isnan(m["tmin"]) and math.isnan(m["tmax"]):
        messages.append({"niveau": "avertissement", "texte": "Domaine d'emploi non renseigné pour ce matériau : vérifiez qu'il tient à cette température."})
    else:
        messages.append({"niveau": "succes", "texte": f"{fr(temperature, 'g')} °C est dans le domaine d'emploi connu de ce matériau."})
    fig, legende = figureDilatation(m, tref)
    return json.dumps(
        {
            "metriques": [
                ["α moyen entre Tref et T", f"{fr(r['alpha'] * 1e6, '.3f')} × 10⁻⁶/K"],
                ["Allongement relatif ΔL/L", f"{fr(r['alpha'] * (temperature - tref) * 1e6, '.1f')} µm/m"],
            ],
            "messages": messages,
            "fig": json.loads(fig.to_json()),
            "legende": legende,
        },
        allow_nan=False,
    )


# ---------- répartition des tolérances ----------


def procedes() -> str:
    """Procédés de fabrication et leurs valeurs indicatives (c, n, qualités IT), en JSON ; avis de fiabilité."""
    return json.dumps({"procedes": cout_mod.listeProcedes(), "fiabilite": cout_mod.fiabiliteProcedes()})


def repartir(texte: str, methode: str, critere: str, figes: str = "[]", reglage: int = 0, procedesMaillons: str = "[]",
             atelier: str = "{}", arrondi: bool = False) -> str:
    """Répartit les tolérances de la chaîne pour tenir [Jmin ; Jmax] (JSON, voir services/repartition.py).

    Entrées : texte (problème), methode, critere, figes (indices des maillons gardés), reglage (indice du maillon de
    réglage), procedesMaillons (procédé de chaque maillon, « cout_minimal »), atelier (valeurs de l'atelier), arrondi.
    Sortie JSON : {"erreur"} ou message, tenue, schéma après répartition, valeurs clés, tableau, figures, explication,
    procédés utilisés, et ecarts (ES / EI à écrire dans l'étude pour « Appliquer »).
    """
    try:
        probleme = _nettoyer(json.loads(texte))
        garde = rep.repartir(probleme, methode, critere, json.loads(figes), int(reglage), json.loads(procedesMaillons),
                             json.loads(atelier), bool(arrondi))
        sortie, itAvant = garde["sortie"], garde["itAvant"]
        apres = rep.problemeRepartition(garde)
        schema, legendeSchema = figureSchema(apres, apercuChaine(apres))
    except ErreurChaine as e:
        return json.dumps({"erreur": e.message})
    except (ValueError, TypeError, KeyError, IndexError) as e:
        return json.dumps({"erreur": f"Saisie incomplète : {e}"})
    lignes, info = sortie["maillons"], sortie.get("cout")
    nomReglage = lignes[sortie["reglage"]]["nom"]
    valeurs = [["Budget Jmax − Jmin", f"{fr(sortie['budget'])} mm"]]
    if sortie["qualite"] is not None:
        valeurs.append(["Qualité ISO retenue", f"IT{sortie['qualite']}"])
    valeurs.append([f"Décalage de « {nomReglage} »", f"{fr(sortie['decalage'] * 1000, '+.1f')} µm"])
    colonnes = rep.colonnesRepartition(garde)
    formats = {"Cote (mm)": ".3f", "IT avant (mm)": ".4f", "IT après (mm)": ".4f", "ES (mm)": "+.4f", "EI (mm)": "+.4f",
               "Coût avant": ".3f", "Coût après": ".3f"}

    def texte_case(titre, v):
        if v is None:
            return "—"
        if isinstance(v, bool):
            return "oui" if v else "non"
        return fr(v, formats[titre]) if titre in formats else str(v)

    tableau = _table(list(colonnes), [[texte_case(t, colonnes[t][i]) for t in colonnes] for i in range(len(lignes))])
    figures = [_figure("it", "IT avant et après", *figureITAvantApres(sortie, itAvant))]
    metriquesCout = None
    if info:
        avant, apresCout = rep.coutsAvantApres(garde)
        figures.append(_figure("couts", "Coût par maillon", *figureCoutsMaillons([m["nom"] for m in lignes], avant, apresCout)))
        metriquesCout = [
            ["Coût relatif optimisé", fr(info["total"], ".2f")],
            ["Gain vs répartition égale", fr(info["gainEgale"] * 100, "+.1f") + " %"],
            ["Gain vs proportionnelle", fr(info["gainProportionnelle"] * 100, "+.1f") + " %"],
        ]
    pr = rep.tableProcedes(garde["specs"]) if info else None
    return json.dumps(
        {
            "tenue": bool(sortie["tenue"]), "message": sortie["message"],
            "schema": {"fig": json.loads(schema.to_json()), "legende": legendeSchema},
            "valeurs": valeurs, "metriquesCout": metriquesCout, "tableau": tableau, "figures": figures,
            "explication": [{"texte": b["texte"], "formules": [texVersHtml(f) for f in b["formules"]]} for b in rep.explicationRepartition(sortie)],
            "procedes": None if pr is None else {
                "legende": pr["legende"], "avertissement": pr["avertissement"],
                "tableau": _table(list(pr["lignes"][0]), [[fr(v, "g") if isinstance(v, float) else v for v in x.values()] for x in pr["lignes"]]),
            },
            "ecarts": [{"es": m["es"], "ei": m["ei"]} for m in lignes],
            "apres": apres,
        },
        allow_nan=False,
    )


def atelierExporter(valeurs: str) -> str:
    """Fichier des valeurs d'atelier (même format que le bureau) ; JSON {"contenu"} ou {"erreur"}."""
    try:
        return json.dumps({"contenu": procedes_atelier.exporterProcedes(json.loads(valeurs))})
    except ErreurChaine as e:
        return json.dumps({"erreur": e.message})


def atelierImporter(texte: str) -> str:
    """Valeurs d'atelier relues d'un fichier (JSON {"valeurs"} ou {"erreur"})."""
    try:
        return json.dumps({"valeurs": procedes_atelier.importerProcedes(texte)})
    except ErreurChaine as e:
        return json.dumps({"erreur": e.message})


# ---------- comparaison de deux scénarios ----------


def comparer(texteA: str, texteB: str, nomB: str = "B") -> str:
    """Compare deux problèmes (A = étude en cours, B = variante) : phrases, écarts, tolérances et barres jumelées."""
    try:
        a, b = _nettoyer(json.loads(texteA)), _nettoyer(json.loads(texteB))
        cmp = comparerScenarios(calculerChaine(a, False), calculerChaine(b, False))
    except ErreurChaine as e:
        return json.dumps({"erreur": e.message})
    except (ValueError, TypeError, KeyError) as e:
        return json.dumps({"erreur": f"Saisie incomplète : {e}"})

    def f(v):
        return "—" if v is None else fr(v, ".4f")

    libelles = {"jeuMini": "Jeu mini (mm)", "jeuMaxi": "Jeu maxi (mm)", "cpk": "Cpk", "ppm": "ppm"}
    fig, legende = figureScenarios(cmp["maillons"], "A (étude en cours)", nomB)
    return json.dumps(
        {
            "phrases": cmp["phrases"], "identiques": cmp["identiques"],
            "grandeurs": _table(["Grandeur", "A", "B", "Écart B − A"], [[lib, f(cmp[k]["a"]), f(cmp[k]["b"]), f(cmp[k]["delta"])] for k, lib in libelles.items()]),
            "maillons": _table(["Maillon", "Statut", "IT A (mm)", "IT B (mm)", "Écart (mm)"],
                               [[m["nom"], m["statut"], f(m["itA"]), f(m["itB"]), f(m["delta"])] for m in cmp["maillons"]]),
            "fig": json.loads(fig.to_json()), "legende": legende,
        },
        allow_nan=False,
    )


# ---------- mécanisme (plusieurs chaînes) ----------

CLASSE_VERDICT = {"conforme au pire des cas": "succes", "conforme en statistique seulement": "avertissement",
                  "non conforme": "erreur", "erreur de calcul": "info"}


def mecaChaine(texte: str) -> str:
    """Chaîne de la page « Analyser » prête à entrer dans un mécanisme : nettoyée et validée (JSON {"probleme"} ou {"erreur"})."""
    try:
        p = _nettoyer(json.loads(texte), garderCartouche=True)
        return json.dumps({"probleme": projet_io.importerProbleme(projet_io.exporterProbleme(p))}, allow_nan=False)
    except ErreurChaine as e:
        return json.dumps({"erreur": e.message})


def cfFusionner(texte: str) -> str:
    """Deux chaînes d'un même assemblage (fichier de mécanisme) → une étude à deux cotes condition (JSON {"commun"} ou {"erreur"}).

    Entrée : JSON {"chaines": [chaîne 1, chaîne 2]}. Les maillons identiques (tout sauf le sens) sont réunis sur une ligne :
    « sens » est son sens dans la CF1, « sens2 » dans la CF2 (texte vide = hors de cette chaîne). Les réglages de la CF1 sont gardés.
    """
    try:
        chaines = json.loads(texte).get("chaines", [])
        if len(chaines) != 2:
            return json.dumps({"erreur": f"Ce fichier contient {len(chaines)} chaînes : la page Étude en accepte 2 (utilisez la page Mécanisme)."})
        p1, p2 = chaines
        maillons = [{**m, "sens2": ""} for m in p1["maillons"]]
        for m in p2["maillons"]:
            cle = {k: v for k, v in m.items() if k != "sens"}
            for x in maillons:
                if x["sens2"] == "" and {k: v for k, v in x.items() if k not in ("sens", "sens2")} == cle:
                    x["sens2"] = m["sens"]
                    break
            else:
                maillons.append({**m, "sens": "", "sens2": m["sens"]})
        commun = {"condition": p1["condition"], "condition2": p2["condition"], "reglages": p1["reglages"], "maillons": maillons}
        if p1.get("cartouche"):
            commun["cartouche"] = p1["cartouche"]
        avert = "" if p1["reglages"] == p2["reglages"] else "Les deux chaînes avaient des réglages différents : ceux de la CF1 sont gardés."
        return json.dumps({"commun": commun, "avertissement": avert}, allow_nan=False)
    except (KeyError, TypeError, AttributeError, ValueError):
        return json.dumps({"erreur": "Fichier de mécanisme non exploitable."})


def mecaImporter(texte: str) -> str:
    """Relit un mécanisme, ou un fichier d'étude simple promu en mécanisme d'une chaîne (JSON nom + chaines, ou erreur)."""
    try:
        return json.dumps(meca.importerMecanisme(texte), allow_nan=False)
    except ErreurChaine as e:
        return json.dumps({"erreur": e.message})


def mecaExporter(texte: str) -> str:
    """Fichier d'un mécanisme (même format que le bureau) : JSON {"contenu"} ou {"erreur"}."""
    try:
        return json.dumps({"contenu": meca.exporterMecanisme(json.loads(texte))})
    except ErreurChaine as e:
        return json.dumps({"erreur": e.message})


def mecaCalculer(texte: str, n: int = 50_000, graine: int = 1, seuil: float = 1.33) -> str:
    """Calcule toutes les chaînes d'un mécanisme ; une chaîne en erreur n'empêche pas les autres (JSON)."""
    try:
        r = meca.calculerMecanisme(json.loads(texte), int(n), int(graine), float(seuil))
    except ErreurChaine as e:
        return json.dumps({"erreur": e.message})
    niveau, phrase = meca.verdictGlobal(r)
    g, cols = r["global"], meca.colonnesTableauDeBord(r["lignes"], float(seuil))
    lignes = [[cols[t][i] for t in cols] for i in range(len(r["lignes"]))]
    fig, legende = figureCpkMecanisme(r["lignes"], float(seuil))
    pire = g["pireCpk"]
    csv = "\r\n".join(";".join(projet_io._neutre(c) for c in ligne) for ligne in [list(cols), *lignes])  # ; et virgule décimale : Excel en français
    return json.dumps(
        {
            "niveau": niveau, "phrase": phrase,
            "reduit": f"Monte-Carlo réduit à {r['nTirages']} tirages par chaîne pour tenir le temps de calcul." if r["nTirages"] < int(n) else "",
            "metriques": [["Pire Cpk", fr(pire, ".3g") if pire is not None else "—"], ["Chaînes hors tolérance", f"{len(g['horsTolerance'])} sur {g['nChaines']}"]],
            "pireChaine": g["chainePireCpk"] or "",
            "enErreur": [{"nom": x["nom"], "message": x["erreur"]} for x in r["lignes"] if x["erreur"]],
            "tableau": {**_table(list(cols), lignes), "colonneClasse": 1,
                        "classes": [CLASSE_VERDICT.get(x["verdict"], "info") for x in r["lignes"]]},
            "fig": json.loads(fig.to_json()), "legende": legende, "csv": csv,
        },
        allow_nan=False,
    )


# ---------- dossier de validation ----------


def cartouche() -> str:
    """Champs du cartouche d'un dossier (clé, libellé) et statuts possibles, en JSON."""
    return json.dumps({"champs": [{"cle": c, "libelle": lib} for c, lib in CHAMPS_CARTOUCHE], "statuts": list(STATUTS)})


def empreinteProbleme(texte: str) -> str:
    """Empreinte du problème (posée au statut « Validé ») : la même que celle que le bureau recalcule à l'ouverture."""
    return empreinte(_nettoyer(json.loads(texte)))


def dossier(texte: str) -> str:
    """Dossier de validation HTML : contrôles refaits sans le solveur, bilan et graphiques (JSON, voir validation.py).

    Les graphiques sont interactifs (Plotly) : le navigateur n'a pas de moteur d'images pour les PNG du bureau.
    """
    from chainecotes.services.graphiques_dossier import graphiquesDossier  # kaleido n'est pas demandé (avecImages=False)
    from chainecotes.services.validation import dossierValidation

    try:
        probleme = _nettoyer(json.loads(texte), garderCartouche=True)
        bundle = calculerChaine(probleme)
        d = dossierValidation(probleme, bundle, graphiquesDossier(bundle, avecImages=False))
    except ErreurChaine as e:
        return json.dumps({"erreur": e.message})
    except (ValueError, TypeError, KeyError) as e:
        return json.dumps({"erreur": f"Saisie incomplète : {e}"})
    ecarts = [{"nom": c["nom"], "attendu": fr(c["attendu"], ".6g"), "obtenu": fr(c["obtenu"], ".6g")} for c in d["controles"] if c["statut"] != "OK"]
    return json.dumps({"html": d["html"], "nOk": d["nOk"], "nTotal": d["nTotal"], "bilan": d["bilan"], "ecarts": ecarts}, allow_nan=False)


# ---------- assistant de chaîne ----------


def assistantExemple() -> str:
    """Exemple de l'assistant (arbre dans un carter fermé par un couvercle), en JSON."""
    return json.dumps(exempleAssistant(), allow_nan=False)


def assistant(cotes: str, contacts: str, depart: str = "", arrivee: str = "", nom: str = "Jeu J", jmin: float = 0.0,
              jmax: float = 1.0, choix: int = 0) -> str:
    """Chaînes minimales entre deux surfaces, à partir des cotes des pièces et de leurs contacts (JSON).

    Entrées : cotes (liste de dict piece, de, vers, cote, iso, es, ei, loi, nom), contacts (liste de dict a, b),
    depart et arrivee (« Pièce.surface » ; une surface inconnue est remplacée par une surface connue), nom, jmin, jmax
    (cote condition), choix (indice de la chaîne si plusieurs ont la même longueur).
    Sortie JSON : surfaces ; puis info, ou erreur, ou la chaîne choisie : tableau, plan, avertissements, maillons et condition
    à envoyer vers la page Analyser, manquants (tolérances absentes).
    """
    try:
        cotes, contacts = json.loads(cotes), json.loads(contacts)
        noeuds = surfaces(cotes)
        sortie = {"surfaces": noeuds}
        if len(noeuds) < 2:
            return json.dumps({**sortie, "info": "Décrivez au moins une cote (pièce, deux surfaces, valeur) pour choisir les surfaces du jeu."})
        depart = depart if depart in noeuds else noeuds[0]  # surface renommée ou supprimée : on repart d'une surface connue
        arrivee = arrivee if arrivee in noeuds else noeuds[1]
        sortie |= {"depart": depart, "arrivee": arrivee}
        chaines = construireChaines(cotes, contacts, depart, arrivee)
        lues, liens = lireSaisie(cotes, contacts)
    except ErreurChaine as e:
        return json.dumps({**locals().get("sortie", {"surfaces": []}), "erreur": e.message})
    except (ValueError, TypeError, KeyError) as e:
        return json.dumps({**locals().get("sortie", {"surfaces": []}), "erreur": f"Saisie incomplète : {e}"})
    i = min(max(int(choix), 0), len(chaines) - 1)
    chaine = chaines[i]
    jmin, jmax, nominal = float(jmin), float(jmax), chaine["nominal"]
    avertissements = list(chaine["avertissements"])
    if not jmin <= nominal <= jmax:
        avertissements.append(
            f"Le jeu nominal de cette chaîne ({fr(nominal, 'g')} mm) est hors de [{fr(jmin, 'g')} ; {fr(jmax, 'g')}] mm : "
            "ce peut être normal si les tolérances sont dissymétriques, sinon un sens ou une cote est faux."
        )
    manquants = [m["nom"] for m in chaine["maillons"] if not m["iso"] and (m["es"] is None or m["ei"] is None)]
    if manquants:
        avertissements.append("Tolérance manquante (désignation ISO, ou ES et EI) : " + ", ".join(manquants) + ".")
    fig, legende = figureConstruction(lues, liens, depart, arrivee, chaine)
    return json.dumps(
        {
            **sortie,
            "plusieurs": [f"Chaîne {j + 1} : {len(c['maillons'])} cotes, jeu nominal {fr(c['nominal'], 'g')} mm" for j, c in enumerate(chaines)] if len(chaines) > 1 else [],
            "choisi": i,
            "avertissements": avertissements,
            "tableau": _table(["Maillon", "Sens", "Cote (mm)", "ISO 286", "ES (mm)", "EI (mm)"],
                              [[m["nom"], "−" if m["sens"] == "-" else "+", fr(m["cote"], "g"), m["iso"] or "", fr(m["es"], "g") if m["es"] is not None else "",
                                fr(m["ei"], "g") if m["ei"] is not None else ""] for m in chaine["maillons"]]),
            "fig": json.loads(fig.to_json()), "legende": legende,
            "maillons": chaine["maillons"], "condition": {"nom": nom or "Jeu J", "jmin": jmin, "jmax": jmax},
            "utilisable": not manquants,
        },
        allow_nan=False,
    )


# ---------- fichiers d'étude (.json du bureau) ----------


def ouvrir(texte: str) -> str:
    """Relit une étude enregistrée (par le bureau ou par cette page) et la contrôle ; JSON probleme + revisions."""
    try:
        return json.dumps(projet_io.importerProjet(texte), allow_nan=False)
    except ErreurChaine as e:
        return json.dumps({"erreur": e.message})


def sauver(texteProbleme: str, texteRevisions: str = "[]") -> str:
    """Texte du fichier d'étude (même format que le bureau) ; JSON {"contenu"} ou {"erreur"} si la saisie est invalide."""
    try:
        probleme = _nettoyer(json.loads(texteProbleme), garderCartouche=True)
        contenu = projet_io.exporterProjet(probleme, json.loads(texteRevisions))
        projet_io.importerProjet(contenu)  # le fichier doit se rouvrir : mêmes contrôles qu'à l'ouverture
        return json.dumps({"contenu": contenu})
    except ErreurChaine as e:
        return json.dumps({"erreur": e.message})
