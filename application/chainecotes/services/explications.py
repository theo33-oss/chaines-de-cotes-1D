"""Explications pas à pas d'un calcul de chaîne de cotes, avec les formules remplies par les valeurs du calcul.

Chaque section est un dict titre, texte (markdown, nombres à virgule décimale) et formules (LaTeX compatible
MathJax / st.latex). La démarche suit le solveur (chainecotes.core.chaine) : projection, cotes moyennes et IT,
jeu nominal et moyen, pire des cas, statistique, capabilité, Monte-Carlo, effet thermique, avertissements.
"""

import math

from chainecotes.core import iso286
from chainecotes.core.inertiel import analyseInertielle, verdictBender

MAX_TERMES = 8  # au-delà, les sommes sont résumées au lieu d'être écrites terme à terme


def _chiffres(x: float, d: int) -> str:
    """Nombre arrondi à d décimales, zéros inutiles retirés, point décimal."""
    s = f"{float(x):.{d}f}".rstrip("0").rstrip(".") if d > 0 else f"{float(x):.0f}"
    return "0" if s in ("-0", "") else s


def _fr(x: float, d: int = 4) -> str:
    """Nombre pour le texte markdown, en français (virgule décimale) ; ±∞ si infini."""
    if math.isinf(x):
        return "+∞" if x > 0 else "−∞"
    if math.isnan(x):
        return "non défini"
    return _chiffres(x, d).replace(".", ",")


def _tex(x: float, d: int = 4) -> str:
    """Nombre pour LaTeX, virgule décimale sans espace parasite ({,})."""
    if math.isinf(x):
        return r"+\infty" if x > 0 else r"-\infty"
    if math.isnan(x):
        return r"\text{non défini}"
    return _chiffres(x, d).replace(".", "{,}")


def _texp(x: float, d: int = 4) -> str:
    """Nombre pour LaTeX, entre parenthèses s'il est négatif (facteur d'un produit)."""
    s = _tex(x, d)
    return f"({s})" if s.startswith("-") else s


def _somme(termes: list[str], resume: str, total: str) -> str:
    """Somme écrite terme à terme (8 termes au plus), sinon résumée, suivie de son total."""
    if len(termes) <= MAX_TERMES:
        return " + ".join(termes) + " = " + total
    return resume + " = " + total


def _tableau(entetes: list[str], lignes: list[list[str]]) -> str:
    """Tableau markdown."""
    tete = "| " + " | ".join(entetes) + " |\n|" + "---|" * len(entetes) + "\n"
    return tete + "\n".join("| " + " | ".join(lg) + " |" for lg in lignes)


def explicationsCalcul(bundle: dict) -> list[dict]:
    """Démarche du calcul expliquée section par section, avec les valeurs du calcul.

    Entrée : bundle (sortie de chainecotes.services.calcul.calculerChaine ; mc peut valoir None).
    Sortie : liste de dict titre (texte), texte (markdown), formules (liste de chaînes LaTeX remplies ;
    longueurs en mm, températures en °C, α en 1e-6/K). Les sections Cp / Cpk / ppm, Monte-Carlo, effet thermique
    et avertissements n'apparaissent que si elles s'appliquent.
    """
    res, v, mc = bundle["res"], bundle["verdicts"], bundle["mc"]
    M = res["maillons"]
    n = len(M)
    idx = range(n)
    a = [float(x) for x in res["coef"]]
    proj = [float(x) for x in res["proj"]]
    cote = [float(x) for x in res["Cote"]]
    cmoy = [float(x) for x in res["C_moy"]]
    it = [float(x) for x in res["IT"]]
    sig = [float(x) for x in res["sigma_i"]]
    k = float(res["k_sigma"])
    c = res["condition"]
    jmin, jmax = float(c["jmin"]), float(c["jmax"])
    mu, sJ = float(res["CF_moy"]), float(res["CF_sigma"])
    muP, dec, decal = float(res["CF_moy_proc"]), float(res["decentrage"]), float(res["decalage"])
    th = bool(res["thermique_actif"])
    sections = []

    # 1. Projection et sens
    f1 = [
        r"\text{sens } + \;:\; \theta_i = 0^\circ,\ \cos\theta_i = +1"
        r"\qquad \text{sens } - \;:\; \theta_i = 180^\circ,\ \cos\theta_i = -1",
        r"a_i = f_i\,\cos\theta_i \,\left(1 + \alpha_i\,\Delta T_i\right)",
    ]
    if th:
        f1 += [
            rf"a_{{{i + 1}}} = {_texp(proj[i], 0)} \times \left(1 + {_tex(res['alpha'][i] * 1e6, 3)}\cdot 10^{{-6}}"
            rf" \times {_texp(res['dT'][i], 2)}\right) = {_tex(a[i], 8)}"
            for i in idx[:MAX_TERMES]
        ]
    texte1 = (
        "Chaque maillon est projeté sur l'axe de la cote condition : un maillon de sens « + » agrandit le jeu, "
        "un maillon de sens « − » le diminue. En service, la dilatation thermique multiplie la projection par "
        "(1 + α ΔT) ; c'est le coefficient a_i. Le facteur f_i (levier, 1 par défaut) et l'angle de la cote "
        "(ajouté à θ_i, 0° par défaut) donnent un coefficient libre : sans eux, cos θ_i vaut +1 ou −1."
        + ("" if th else " Sans effet thermique, a_i = f_i · cos θ_i.")
        + "\n\n"
        + _tableau(
            ["Maillon", "Sens", "θ (°)", "f_i", "f_i · cos θ", "a_i en service"],
            [
                [
                    M[i]["nom"],
                    M[i]["sens"],
                    _fr(M[i]["theta"], 2),
                    _fr(M[i]["facteur"], 4),
                    _fr(proj[i], 4),
                    _fr(a[i], 8),
                ]
                for i in idx
            ],
        )
    )
    sections.append({"titre": "1. Projection et sens des maillons", "texte": texte1, "formules": f1})

    # 2. Cote moyenne et IT
    lignes2, f2 = [], [r"\bar C_i = C_i + \frac{ES_i + EI_i}{2} \qquad IT_i = ES_i - EI_i"]
    for i in idx:
        m = M[i]
        if m["iso"]:
            r = iso286.lireDesignation(m["iso"], m["cote"])
            iso = f"{r['designation']} ({r['type']}, IT{r['qualite']} = {_fr(r['IT'], 1)} µm, {r['plage']})"
        else:
            iso = "écarts saisis"
        lignes2.append([m["nom"], _fr(cote[i]), iso, _fr(m["es"]), _fr(m["ei"]), _fr(it[i]), _fr(cmoy[i]), m["loi"]])
        if i < MAX_TERMES:
            f2.append(
                rf"\bar C_{{{i + 1}}} = {_tex(cote[i])} + \frac{{{_tex(m['es'])} + {_texp(m['ei'])}}}{{2}}"
                rf" = {_tex(cmoy[i])} \qquad IT_{{{i + 1}}} = {_tex(m['es'])} - {_texp(m['ei'])} = {_tex(it[i])}"
            )
    texte2 = (
        "Pour chaque maillon, les écarts viennent de la désignation ISO 286 (lue dans la table) ou de la saisie. "
        "La cote moyenne est le milieu de la zone de tolérance, l'IT sa largeur (mm).\n\n"
        + _tableau(
            ["Maillon", "Cote (mm)", "ISO 286", "ES (mm)", "EI (mm)", "IT (mm)", "Cote moyenne (mm)", "Loi"], lignes2
        )  # fmt: skip
    )
    if n > MAX_TERMES:
        texte2 += f"\n\nLes formules ne détaillent que les {MAX_TERMES} premiers maillons ; le tableau les donne tous."
    sections.append({"titre": "2. Cote moyenne et intervalle de tolérance", "texte": texte2, "formules": f2})

    # 3. Jeu nominal et jeu moyen
    f3 = [
        "J_{nom} = \\sum a_i\\,C_i = "
        + _somme(
            [f"{_texp(a[i], 6)} \\times {_texp(cote[i])}" for i in idx],
            rf"\sum_{{i=1}}^{{{n}}} a_i\,C_i",
            _tex(res["CF_nom"]),
        ),  # fmt: skip
        "J_{moy} = \\sum a_i\\,\\bar C_i = "
        + _somme(
            [f"{_texp(a[i], 6)} \\times {_texp(cmoy[i])}" for i in idx],
            rf"\sum_{{i=1}}^{{{n}}} a_i\,\bar C_i",
            _tex(mu),
        ),  # fmt: skip
    ]
    texte3 = (
        f"Le jeu nominal ({c['nom']}) est la somme des cotes nominales projetées : {_fr(res['CF_nom'])} mm. "
        f"Le jeu moyen, somme des cotes moyennes projetées, vaut {_fr(mu)} mm."
    )
    sections.append({"titre": "3. Jeu nominal et jeu moyen", "texte": texte3, "formules": f3})

    # 4. Pire des cas
    demi = (res["CF_max"] - res["CF_min"]) / 2
    pc = v["pireCas"]
    f4 = [
        "\\frac{\\Delta J}{2} = \\sum \\frac{|a_i|\\,IT_i}{2} = "
        + _somme(
            [f"\\frac{{{_tex(abs(a[i]), 6)} \\times {_tex(it[i])}}}{{2}}" for i in idx],
            rf"\sum_{{i=1}}^{{{n}}} \frac{{|a_i|\,IT_i}}{{2}}",
            _tex(demi),
        ),  # fmt: skip
        rf"J_{{min}} = J_{{moy}} - \frac{{\Delta J}}{{2}} = {_tex(mu)} - {_tex(demi)} = {_tex(pc['min'])}",
        rf"J_{{max}} = J_{{moy}} + \frac{{\Delta J}}{{2}} = {_tex(mu)} + {_tex(demi)} = {_tex(pc['max'])}",
    ]
    exige = f"exigé [{_fr(jmin)} ; {_fr(jmax)}] mm"
    texte4 = (
        "Au pire des cas, tous les maillons sont à leur limite défavorable en même temps : le jeu varie de la "
        f"demi-dispersion {_fr(demi)} mm de part et d'autre du jeu moyen, soit de {_fr(pc['min'])} à "
        f"{_fr(pc['max'])} mm ({exige}). Verdict : **{'conforme' if pc['ok'] else 'non conforme'}**."
    )
    sections.append({"titre": "4. Pire des cas", "texte": texte4, "formules": f4})

    # 5. Statistique
    f5 = [
        r"\sigma_i = \frac{|a_i|\,IT_i}{2k} \;(\text{loi normale}) \qquad "
        r"\sigma_i = \frac{|a_i|\,IT_i}{\sqrt{12}} \;(\text{loi uniforme}) \qquad "
        r"\sigma_i = \frac{|a_i|\,IT_i}{2\sqrt{6}} \;(\text{loi triangulaire})"
    ]
    reel = [float(x) for x in res["sigma_reel"]]
    for i in list(idx)[:MAX_TERMES]:
        if not math.isnan(reel[i]):
            f5.append(
                rf"\sigma_{{{i + 1}}} = |a_{{{i + 1}}}| \times \sigma_{{\text{{mesuré}}}} = "
                rf"{_tex(abs(a[i]), 6)} \times {_tex(reel[i], 6)} = {_tex(sig[i], 6)}"
            )
            continue
        bas = {"normale": f"2 \\times {_tex(k, 3)}", "uniforme": "\\sqrt{12}"}.get(res["loi"][i], "2\\sqrt{6}")
        f5.append(
            rf"\sigma_{{{i + 1}}} = \frac{{{_tex(abs(a[i]), 6)} \times {_tex(it[i])}}}{{{bas}}} = {_tex(sig[i], 6)}"
        )
    f5.append(
        "\\sigma_J = \\sqrt{\\sum \\sigma_i^2} = \\sqrt{"
        + (" + ".join(f"{_tex(s, 6)}^2" for s in sig) if n <= MAX_TERMES else rf"\sum_{{i=1}}^{{{n}}} \sigma_i^2")
        + "} = "
        + _tex(sJ, 6)
    )
    rk = v["rssK"]
    f5.append(
        rf"J_{{moy}} \pm k\,\sigma_J = {_tex(mu)} \pm {_tex(k, 3)} \times {_tex(sJ, 6)}"
        rf" = [{_tex(rk['min'])} \;;\; {_tex(rk['max'])}]"
    )
    if sJ > 0:
        texte5 = (
            "Les maillons ne sont pas tous à leur limite en même temps : on additionne les variances. "
            f"Le procédé est garanti à ± {_fr(k, 3)} σ (loi normale : IT = 2kσ ; loi uniforme : σ = IT/√12 ; "
            "loi triangulaire : σ = IT/(2√6)). "
            f"L'écart-type du jeu vaut σ_J = {_fr(sJ, 6)} mm ; à ± {_fr(k, 3)} σ, le jeu va de {_fr(rk['min'])} à "
            f"{_fr(rk['max'])} mm ({exige}). Verdict : **{'conforme' if rk['ok'] else 'non conforme'}**."
        )
    else:
        texte5 = (
            "Toutes les tolérances sont nulles : σ_J = 0, le jeu ne varie pas et il n'y a pas de calcul statistique."
        )
    sections.append({"titre": "5. Calcul statistique (RSS)", "texte": texte5, "formules": f5})

    # 5 ter. Capabilités mesurées à l'atelier
    mesures = [i for i in idx if not math.isnan(reel[i]) or not math.isnan(float(res["moyenne_reelle"][i]))]
    if mesures:
        dr = float(res["decalage_reel"])
        noms = ", ".join(M[i]["nom"] for i in mesures)
        fm = [
            r"\Delta\mu_{\text{mesuré}} = \sum a_i\,(x_{\text{mesuré},i} - C_{moy,i})"
            rf" = {_tex(dr, 6)}",
            rf"\mu = J_{{moy}} + \Delta\mu_{{\text{{mesuré}}}} = {_tex(mu)} + {_texp(dr, 6)}",
        ]
        textem = (
            f"Cotes avec mesures de l'atelier : {noms}. L'écart type mesuré remplace celui déduit de l'IT et de "
            "la loi ; "
            "la moyenne mesurée remplace la cote moyenne pour la moyenne du procédé. Le décalage obtenu "
            f"({_fr(dr, 6)} mm) agit sur Cpk, les ppm et la simulation Monte-Carlo, comme un décentrage ; le pire des "
            "cas et Cp n'en dépendent pas."
        )
        sections.append({"titre": "5 ter. Mesures de l'atelier", "texte": textem, "formules": fm})

    # 5 bis. Décentrage du procédé
    if dec > 0:
        proche = "Jmin" if decal < 0 else "Jmax"
        fd = [
            rf"\Delta\mu = d\,\sigma_J = {'-' if decal < 0 else '+'}{_tex(dec, 3)} \times {_tex(sJ, 6)}"
            rf" = {_tex(decal, 6)}",
            rf"\mu = J_{{moy}} + \Delta\mu = {_tex(mu)} + {_texp(decal, 6)} = {_tex(muP)}",
        ]
        texted = (
            f"Le procédé est décentré de {_fr(dec, 3)} σ_J vers la limite la plus défavorable ({proche}) : la "
            f"moyenne du jeu passe de {_fr(mu)} mm à {_fr(muP)} mm (décalage {_fr(decal, 6)} mm). Cp et le pire des "
            "cas ne changent pas ; Cpk, les ppm et la simulation Monte-Carlo utilisent la moyenne décalée."
            if decal != 0
            else "Le décentrage demandé est sans effet : aucune limite finie vers laquelle décaler la moyenne."
        )
        sections.append({"titre": "5 bis. Décentrage du procédé", "texte": texted, "formules": fd})

    # 6. Cp, Cpk, ppm
    if sJ > 0 and (math.isfinite(jmin) or math.isfinite(jmax)):
        f6 = []
        if math.isfinite(jmin) and math.isfinite(jmax):
            f6.append(
                rf"C_p = \frac{{J_{{max}} - J_{{min}}}}{{6\,\sigma_J}} = \frac{{{_tex(jmax)} - {_texp(jmin)}}}"
                rf"{{6 \times {_tex(sJ, 6)}}} = {_tex(v['cp'], 3)}"
            )
        cotes = []
        if math.isfinite(jmin):
            cotes.append(rf"\frac{{{_tex(muP)} - {_texp(jmin)}}}{{3 \times {_tex(sJ, 6)}}}")
        if math.isfinite(jmax):
            cotes.append(rf"\frac{{{_tex(jmax)} - {_texp(muP)}}}{{3 \times {_tex(sJ, 6)}}}")
        sep = r" \;;\; "
        f6.append(rf"C_{{pk}} = \min\left({sep.join(cotes)}\right) = {_tex(v['cpk'], 3)}")
        termes = []
        if math.isfinite(jmin):
            termes.append(rf"\Phi\!\left(\frac{{{_tex(jmin)} - {_texp(muP)}}}{{{_tex(sJ, 6)}}}\right)")
        if math.isfinite(jmax):
            termes.append(rf"\Phi\!\left(\frac{{{_tex(muP)} - {_texp(jmax)}}}{{{_tex(sJ, 6)}}}\right)")
        f6.append(rf"\text{{ppm}} = 10^6 \left[{' + '.join(termes)}\right] = {_tex(v['ppm'], 1)}")
        texte6 = (
            "Les indices de capabilité comparent la dispersion du jeu (6 σ_J) à l'intervalle exigé : "
            f"Cp = {_fr(v['cp'], 3)}, Cpk = {_fr(v['cpk'], 3)} (Cpk ≥ 1,33 est l'objectif usuel). "
            f"Avec un jeu de loi normale, la part hors tolérance attendue est de {_fr(v['ppm'], 1)} ppm "
            "(pièces par million)."
        )
        sections.append({"titre": "6. Capabilité Cp, Cpk et taux hors tolérance", "texte": texte6, "formules": f6})

    # 7. Monte-Carlo
    if mc is not None:
        f7 = [
            rf"J = \sum a_i\,X_i,\quad N = {mc['n']},\ \text{{graine}} = {mc['graine']}",
            rf"\text{{ppm}}_{{simulé}} = 10^6 \times \frac{{{mc['nHors']}}}{{{mc['n']}}} = {_tex(mc['ppm'], 1)}"
            rf" \qquad \text{{ppm}}_{{formule}} = {_tex(v['ppm'], 1)}",
            rf"\bar J = {_tex(mc['moyenne'])} \qquad s_J = {_tex(mc['ecartType'], 6)}",
        ]
        texte7 = (
            f"{mc['n']} assemblages virtuels sont tirés au hasard (graine {mc['graine']}, résultat reproductible), "
            "chaque maillon suivant sa loi autour de sa cote moyenne. "
            f"Jeu moyen simulé {_fr(mc['moyenne'])} mm, écart-type {_fr(mc['ecartType'], 6)} mm ; "
            f"{mc['nHors']} tirages hors tolérance, soit {_fr(mc['ppm'], 1)} ppm contre {_fr(v['ppm'], 1)} ppm par "
            f"la formule (la simulation ne distingue pas mieux que {_fr(mc['resolutionPpm'], 1)} ppm)."
        )
        sections.append({"titre": "7. Simulation de Monte-Carlo", "texte": texte7, "formules": f7})

    # 8. Effet thermique
    if th:
        f8 = [r"\Delta J_{th,i} = \cos\theta_i\,\bar C_i\,\alpha_i\,\Delta T_i"]
        for i in list(idx)[:MAX_TERMES]:
            f8.append(
                rf"\Delta J_{{th,{i + 1}}} = {_texp(proj[i], 0)} \times {_tex(cmoy[i])} \times "
                rf"{_tex(res['alpha'][i] * 1e6, 3)}\cdot 10^{{-6}} \times {_texp(res['dT'][i], 2)}"
                rf" = {_tex(res['dJ_th_i'][i], 6)}"
            )
        f8.append(
            r"\Delta J_{th} = J_{moy}(T_{service}) - J_{moy}(T_{ref}) = "
            rf"{_tex(mu)} - {_texp(res['CF_moy_ref'])} = {_tex(res['dJ_th'], 6)}"
        )
        texte8 = (
            f"Entre la température de référence ({_fr(res['Tref'], 2)} °C) et la température de service, chaque "
            "maillon se dilate de C α ΔT. Le jeu moyen se décale de "
            f"{_fr(res['dJ_th'], 6)} mm (de {_fr(res['CF_moy_ref'])} mm à {_fr(mu)} mm).\n\n"
            + _tableau(
                ["Maillon", "α (1e-6/K)", "T service (°C)", "ΔT (K)", "a_i", "ΔJ_th,i (mm)"],
                [
                    [
                        M[i]["nom"],
                        _fr(res["alpha"][i] * 1e6, 3),
                        _fr(res["Tservice"][i], 2),
                        _fr(res["dT"][i], 2),
                        _fr(a[i], 8),
                        _fr(res["dJ_th_i"][i], 6),
                    ]  # fmt: skip
                    for i in idx
                ],
            )
        )
        sections.append({"titre": "8. Effet thermique", "texte": texte8, "formules": f8})

    # 8 bis. Méthodes complémentaires : Bender et tolérancement inertiel
    if sJ > 0:
        b, ine = verdictBender(res), analyseInertielle(res)
        fc = [
            r"\Delta_{Bender} = 1{,}5\,\sqrt{\sum \left(|a_i|\,IT_i/2\right)^2}"
            rf" = {_tex(b['demi'], 6)}",
            rf"J_{{moy}} \pm \Delta_{{Bender}} = [{_tex(b['min'])} \;;\; {_tex(b['max'])}]",
            r"I_J = \sqrt{\sigma_J^2 + \delta_J^2} = \sqrt{"
            + rf"{_tex(sJ, 6)}^2 + {_texp(ine['ecartCible'], 6)}^2"
            + "}"
            rf" = {_tex(ine['inertieJeu'], 6)}",
        ]
        textec = (
            f"**Statistique majorée de Bender** : la tolérance de fermeture vaut 1,5 fois la somme quadratique des "
            f"demi-tolérances, soit ± {_fr(b['demi'], 5)} mm autour du jeu moyen "
            f"({_fr(b['min'])} à {_fr(b['max'])} mm) : "
            f"**{'conforme' if b['ok'] else 'non conforme'}** pour {exige}. Elle se place entre le pire des cas et la "
            "somme quadratique pure. **Tolérancement inertiel (Pillet)** : l'inertie du jeu mêle dispersion et "
            f"décentrage par rapport à la cible ({_fr(ine['cible'])} mm) ; elle vaut {_fr(ine['inertieJeu'], 6)} mm"
        )
        if math.isfinite(ine["inertieMax"]):
            fc.append(
                rf"Cpi = I_{{max}}/I_J = {_tex(ine['inertieMax'], 6)} / {_tex(ine['inertieJeu'], 6)}"
                rf" = {_tex(ine['cpi'], 3)}"
            )
            textec += f" pour une inertie maxi de {_fr(ine['inertieMax'], 6)} mm, soit un Cpi de {_fr(ine['cpi'], 3)}."
        else:
            textec += " ; sans les deux limites, l'inertie maxi et le Cpi ne sont pas définis."
        sections.append({"titre": "8 bis. Méthodes complémentaires (Bender, inertie)", "texte": textec, "formules": fc})

    # 9. Avertissements
    if bundle["avertissements"]:
        texte9 = "\n".join(f"- {t}" for t in bundle["avertissements"])
        sections.append({"titre": "9. Avertissements", "texte": texte9, "formules": []})
    return sections
