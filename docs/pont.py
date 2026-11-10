"""Pont entre la page web (JavaScript) et le calcul Python de l'application : entrées et sorties en JSON.

Le navigateur appelle ces fonctions par Pyodide ; elles servent aussi aux essais en Python ordinaire (essai_pont.py).
Rien n'est calculé en JavaScript : la page ne fait qu'afficher ce que ce module renvoie.
"""

import json
import math

from chainecotes.core.chaine import capabilitesMaillons, libelleVerdict
from chainecotes.core.errors import ErreurChaine
from chainecotes.core.formules import texVersHtml
from chainecotes.core.inertiel import analyseInertielle, verdictBender
from chainecotes.core.materiaux import PERSONNALISE, nomsMateriaux
from chainecotes.core.nombres import fr
from chainecotes.core.sensibilite import gainSiResserre, indicesSensibilite
from chainecotes.plots import graphiques
from chainecotes.plots._common import intervalle
from chainecotes.plots.schema import figureSchema
from chainecotes.services import projet_io
from chainecotes.services.calcul import apercuChaine, calculerChaine
from chainecotes.services.conclusion import conclusionEtude
from chainecotes.services.controles import controlerProbleme
from chainecotes.services.exemples import chargerExemple, listeExemples
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
