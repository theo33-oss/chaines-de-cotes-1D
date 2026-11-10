"""Conclusion en langage courant d'un calcul de chaîne : le jeu tient-il, sur quoi agir, quelles réserves.

Utilisée par le parcours guidé. Les seuils viennent de data/controles.json (cpk_cible). Ce module n'importe ni
streamlit ni plotly.
"""

import math

from chainecotes.core.donnees import chargerJson
from chainecotes.plots._common import fr

CPK_CIBLE = chargerJson("controles.json")["cpk_cible"]


def conclusionEtude(bundle: dict) -> dict:
    """Verdict et conseils d'un calcul, en phrases françaises.

    Entrée : bundle (sortie de calculerChaine).
    Sortie : dict niveau (« succes » : tient au pire des cas ; « avertissement » : tient en statistique seulement ou
    capabilité fragile ; « erreur » : ne tient pas ; « info » : aucune limite à tenir), titre (une phrase), details
    (phrases sur les chiffres), conseils (phrases sur ce qu'il faut faire) et principaux (les trois maillons qui pèsent
    le plus dans la variance : liste de dict nom, part en %).
    """
    v, c = bundle["verdicts"], bundle["res"]["condition"]
    k = bundle["res"]["k_sigma"]
    nom = c["nom"]
    contrib = sorted(bundle["contributions"], key=lambda x: -x["partVariance"])
    principaux = [{"nom": x["nom"], "part": x["partVariance"]} for x in contrib[:3]]
    details, conseils = [], []
    pc, rss = v["pireCas"], v["rssK"]
    details.append(f"Au pire des cas, {nom} varie de {fr(pc['min'], '.4f')} à {fr(pc['max'], '.4f')} mm.")
    if not (math.isfinite(c["jmin"]) or math.isfinite(c["jmax"])):
        return {
            "niveau": "info",
            "titre": f"{nom} n'a aucune limite : il n'y a pas de verdict.",
            "details": details,
            "conseils": ["Renseignez Jmin et/ou Jmax à l'étape « Cote condition » pour obtenir un verdict."],
            "principaux": principaux,
        }
    if pc["ok"]:
        niveau = "succes"
        titre = f"{nom} tient les limites dans tous les cas (pire des cas)."
    elif rss["ok"] and v["rssProc"]["ok"]:  # plage décalée par le décentrage ou les moyennes mesurées
        niveau = "avertissement"
        titre = f"{nom} ne tient pas au pire des cas, mais tient en statistique (± {fr(k, 'g')} σ)."
        conseils.append(
            f"C'est acceptable seulement si vos procédés garantissent réellement ± {fr(k, 'g')} σ sur chaque cote "
            "(capabilité mesurée) ; sinon resserrez les tolérances."
        )
    else:
        niveau = "erreur"
        titre = f"{nom} ne tient pas les limites, même en statistique."
        conseils.append(
            "Resserrez les tolérances des cotes qui pèsent le plus, "
            "ou élargissez les limites si le mécanisme le permet."
        )
        conseils.append("Le mode « Répartir les tolérances » les répartit, au besoin au moindre coût, pour tenir le jeu.")
    if principaux and principaux[0]["part"] > 0:
        haut = principaux[0]
        details.append(f"La cote « {haut['nom']} » pèse {fr(haut['part'], '.0f')} % de la variance du jeu.")
        if niveau != "succes":
            conseils.insert(0, f"Commencez par la cote « {haut['nom']} » : c'est elle qui fait le plus varier le jeu.")
    ppm, cpk = v["ppm"], v["cpk"]
    exact = bundle.get("ppmExact")
    if exact is not None:
        details.append(
            f"Taux hors tolérance selon la loi de chaque maillon : {fr(exact, '.3g')} ppm "
            f"(la formule normale, approchée, donne {fr(ppm, '.3g')} ppm)."
        )
    elif math.isfinite(ppm):
        details.append(f"Taux hors tolérance estimé (loi normale) : {fr(ppm, '.3g')} ppm.")
    if math.isfinite(cpk):
        details.append(f"Cpk du jeu : {fr(cpk, '.2f')}.")
        if cpk < CPK_CIBLE and niveau == "succes":
            niveau = "avertissement"
            conseils.append(
                f"Le jeu tient au pire des cas mais le Cpk ({fr(cpk, '.2f')}) est sous {fr(CPK_CIBLE, '.2f')} : "
                "la moyenne est proche d'une limite, centrez le jeu (cote de réglage)."
            )
    for a in bundle["avertissements"]:
        conseils.append(a)
    return {"niveau": niveau, "titre": titre, "details": details, "conseils": conseils, "principaux": principaux}
