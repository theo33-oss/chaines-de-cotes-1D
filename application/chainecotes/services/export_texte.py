"""Texte de l'étude pour le bloc-notes (.txt) et pour une IA : données, résultats et démarche en clair.

Ne calcule rien : relit la saisie et le résultat d'un calcul déjà fait (calculerChaine). Ce module n'importe ni
streamlit ni plotly.
"""

import math

from chainecotes.core.nombres import fr, ppmLisible
from chainecotes.services.conclusion import conclusionEtude

CONSIGNE_IA = (
    "Tu es un ingénieur méthodes et tolérancement. Ci-dessous, l'étude d'une chaîne de cotes à une dimension "
    "(outil pédagogique : une seule dimension, lois normale, uniforme ou triangulaire indépendantes).\n"
    "1. Commence par présenter le problème en quelques phrases : la condition de jeu, les maillons, les unités "
    "(mm), les hypothèses et le résultat.\n"
    "2. Signale ce qui te paraît incohérent ou fragile (sens des cotes, tolérances, lois, capabilité).\n"
    "3. Ne refais pas le calcul et n'invente aucun chiffre : appuie-toi sur ceux de l'étude.\n"
    "4. Puis attends mes questions."
)


def _mm(v: float) -> str:
    return fr(float(v), ".4f")


def _ppm(x: float) -> str:
    """Taux hors tolérance lisible ; presque tout hors tolérance s'écrit en pourcentage."""
    return "environ 100 % (1·10⁶ ppm)" if x is not None and x >= 999_999 else ppmLisible(x)


def _limite(v: float) -> str:
    return "aucune" if not math.isfinite(v) else f"{_mm(v)} mm"


def texteEtude(bundle: dict) -> str:
    """Étude complète en texte simple (données, résultats, démarche).

    Entrée : bundle (sortie de calculerChaine : il contient déjà le problème et ses résultats).
    Sortie : texte (lignes séparées par « \n »).
    """
    res, v = bundle["res"], bundle["verdicts"]
    cond = res["condition"]
    k = res["k_sigma"]
    L = ["ÉTUDE DE CHAÎNE DE COTES (1D, unités : mm)", ""]
    L += ["DONNÉES", f"Condition : {cond['nom']}", f"  Jmin : {_limite(cond['jmin'])}", f"  Jmax : {_limite(cond['jmax'])}"]
    L += [f"Niveau statistique : ± {fr(k, 'g')} σ", f"Température de référence : {fr(res['Tref'], 'g')} °C"]
    thermique = bool(res.get("thermique_actif"))
    if thermique:
        L.append("Dilatation thermique : prise en compte (α et température de service de chaque cote ci-dessous).")
    L += ["", "Maillons (sens, cote nominale, écart sup. es, écart inf. ei, tolérance IT, loi) :"]
    for i, nom in enumerate(res["Nom"]):
        sens = "+" if res["proj"][i] > 0 else "−"
        ligne = (
            f"  {i + 1}. {nom} : {sens} {_mm(res['Cote'][i])}  es {_mm(res['ES'][i])}  ei {_mm(res['EI'][i])}"
            f"  IT {_mm(res['IT'][i])}  loi {res['loi'][i]}"
        )
        if thermique:
            ligne += f"  α {fr(float(res['alpha'][i]) * 1e6, '.2f')} µm/m/K  T service {fr(float(res['Tservice'][i]), 'g')} °C"
        m = (res.get("maillons") or [{}] * (i + 1))[i]
        facteur, theta = float(m.get("facteur", 1.0)), float(m.get("theta", 0.0))
        if abs(facteur - 1.0) > 1e-12 or min(abs(theta % 360), abs(theta % 360 - 180)) > 1e-9:  # levier ou angle (180° = cote « − »)
            ligne += f"  facteur {fr(facteur, 'g')}, angle {fr(theta, 'g')}° : la cote compte pour sa projection"
        L.append(ligne)
    L += ["", "RÉSULTATS"]
    L.append(f"Valeur nominale de {cond['nom']} : {_mm(res['CF_nom'])} mm" + (" (somme des cotes projetées, dilatation comprise)" if thermique else ""))
    if thermique:
        L.append(f"Décalage du jeu dû à la dilatation : {fr(float(res['dJ_th']), '+.4f')} mm")
    L.append(f"Moyenne : {_mm(res['CF_moy'])} mm ; écart-type σ : {fr(res['CF_sigma'], '.5f')} mm")
    pc, rk = v["pireCas"], v["rssK"]
    sansLimite = not (math.isfinite(cond["jmin"]) or math.isfinite(cond["jmax"]))
    if sansLimite:
        L.append(f"Pire des cas : de {_mm(pc['min'])} à {_mm(pc['max'])} mm")
        L.append(f"Statistique ± {fr(k, 'g')} σ : de {_mm(rk['min'])} à {_mm(rk['max'])} mm")
        L.append("Aucune limite exigée : pas de verdict ni de taux hors tolérance (renseignez Jmin et/ou Jmax).")
    else:
        L.append(f"Pire des cas : de {_mm(pc['min'])} à {_mm(pc['max'])} mm ({'tient' if pc['ok'] else 'ne tient pas'})")
        L.append(f"Statistique ± {fr(k, 'g')} σ : de {_mm(rk['min'])} à {_mm(rk['max'])} mm ({'tient' if rk['ok'] else 'ne tient pas'})")
        L.append(f"Cp : {fr(v['cp'], '.3f')} ; Cpk : {fr(v['cpk'], '.3f')} ; hors tolérance (formule normale) : {_ppm(v['ppm'])}")
    mc = bundle.get("mc")
    if mc:
        L.append(
            f"Monte-Carlo ({int(mc['n'])} tirages, graine {mc['graine']}) : moyenne {_mm(mc['moyenne'])} mm, "
            f"σ {fr(mc['ecartType'], '.5f')} mm" + ("" if sansLimite else f", hors tolérance {_ppm(mc['ppm'])}")
        )
    c = conclusionEtude(bundle)
    L += ["", "CONCLUSION", c["titre"]] + [f"- {t}" for t in c["details"] + c["conseils"]]
    L += ["", "CONTRIBUTIONS (part de la variance) :"]
    for x in sorted(bundle["contributions"], key=lambda x: -x["partVariance"]):
        L.append(f"  {x['nom']} : {fr(x['partVariance'], '.1f')} %")
    for a in bundle.get("avertissements") or []:
        L.append(f"Avertissement : {a}")
    L += [
        "",
        "DÉMARCHE",
        "1. Chaque cote est comptée positive ou négative selon son sens dans la chaîne (équation de fermeture).",
        "2. Pire des cas : on additionne les écarts de tous les maillons (jeu minimal et maximal garantis).",
        (
            "3. Statistique : chaque cote suit sa loi, indépendamment des autres ; σ de la condition = racine de la somme "
            f"des variances ; intervalle ± k·σ avec k = {fr(k, 'g')}."
        ),
        (
            "4. Cp = (Jmax − Jmin) / 6σ ; Cpk = distance de la moyenne à la limite la plus proche / 3σ ; "
            "ppm = pièces hors tolérance par million (taux déduit d'une loi normale, puis Monte-Carlo)."
        ),
        "5. Monte-Carlo : tirages aléatoires des cotes pour vérifier le résultat statistique.",
    ]
    return "\n".join(L) + "\n"


def texteIA(bundle: dict) -> str:
    """Consigne pour une IA suivie de l'étude complète (à coller dans une conversation).

    Entrée : bundle (comme texteEtude). Sortie : texte.
    """
    return f"{CONSIGNE_IA}\n\n--- ÉTUDE ---\n{texteEtude(bundle)}--- FIN DE L'ÉTUDE ---\n"
