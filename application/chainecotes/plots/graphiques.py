"""Graphiques des résultats d'une chaîne de cotes (port des graphiques de graphiques.m de l'application MATLAB).

Chaque fonction prend le bundle de calculerChaine et renvoie (figure Plotly, légende en une phrase).
"""

import math

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from chainecotes.core.chaine import TOL_COMPARAISON, libelleVerdict, risqueSelonCp
from chainecotes.core.sensibilite import indicesSensibilite
from chainecotes.plots._common import (
    BLEU,
    GRIS,
    ORANGE,
    ROUGE,
    VERMILLON,
    VERT,
    VERT_OI,
    etatThermique,
    figureMessage,
    fr,
    intervalle,
    miseEnPage,
    teinte,
)

_CP_REPERES = (1.0, 1.33, 1.67, 2.0)
_PLANCHER_PPM = 1e-3


def _titre(texte: str, res: dict, sousTitre: str) -> str:
    """Titre sur deux lignes, avec l'état en service si l'effet thermique est actif."""
    etat = etatThermique(res)
    return f"{texte}{' – ' + etat if etat else ''}<br><sup>{sousTitre}</sup>"


def _limites(fig: go.Figure, c: dict, verticale: bool = True, **kw) -> None:
    """Traits rouges des limites finies Jmin et Jmax (verticaux en abscisse, sinon horizontaux)."""
    for v, nom in ((c["jmin"], "Jmin"), (c["jmax"], "Jmax")):
        if math.isfinite(v):
            ajout = fig.add_vline if verticale else fig.add_hline
            ajout(v, line={"color": ROUGE, "width": 2.5}, annotation_text=nom, annotation_font_color=ROUGE, **kw)


def _ppm(v: float) -> str:
    """ppm écrit avec 3 chiffres significatifs."""
    return fr(v, ".3g")


def figurePareto(bundle: dict) -> tuple[go.Figure, str]:
    """Pareto des contributions : parts de variance et de pire cas de chaque maillon, triées (graph_pareto).

    Entrée : bundle (sortie de calculerChaine). Sortie : (figure, légende) ; parts en % du total de chaque série.
    """
    res = bundle["res"]
    lignes = sorted((c for c in bundle["contributions"] if c["pireCas"] > 0), key=lambda c: -c["partVariance"])
    if not lignes:
        return figureMessage(
            "Pareto des contributions", "Aucune tolérance non nulle dans la chaîne : pas de contribution."
        )
    noms = [c["nom"] for c in lignes]
    fig = go.Figure()
    for cle, nom, couleur in (
        ("partVariance", "Part de la variance", BLEU),
        ("partPireCas", "Part du pire cas", VERMILLON),
    ):
        valeurs = [c[cle] for c in lignes]
        fig.add_trace(
            go.Bar(
                x=noms,
                y=valeurs,
                name=nom,
                marker_color=couleur,
                text=[f"{fr(v, '.0f')} %" for v in valeurs],
                textposition="outside",
                cliponaxis=False,
            )
        )
    haut = lignes[0]
    miseEnPage(
        fig,
        _titre(
            "Pareto : quelle cote consomme le jeu ?",
            res,
            f"Cote critique : {haut['nom']} ({fr(haut['partVariance'], '.0f')} % de la variance)",
        ),
        420,
    )
    plafond = max(max(c["partVariance"], c["partPireCas"]) for c in lignes)
    fig.update_layout(barmode="group")
    fig.update_yaxes(title="Part (%)", range=[0, min(115, 1.2 * plafond)])
    legende = (
        f"Le maillon {haut['nom']} porte {fr(haut['partVariance'], '.0f')} % de la variance du jeu "
        f"et {fr(haut['partPireCas'], '.0f')} % de son pire cas."
    )
    return fig, legende


def figureMonteCarlo(bundle: dict) -> tuple[go.Figure, str]:
    """Histogramme en densité des jeux simulés, courbe normale de la formule, limites (graph_montecarlo).

    Entrée : bundle (sortie de calculerChaine). Sortie : (figure, légende) ; jeu en mm, densité en 1/mm.
    """
    res, mc = bundle["res"], bundle["mc"]
    if mc is None:
        motif = "toutes les tolérances sont nulles" if not res["CF_sigma"] > 0 else "la simulation n'a pas été demandée"
        return figureMessage("Histogramme Monte-Carlo", f"Pas de simulation Monte-Carlo : {motif}.")
    J, c = mc["J"], res["condition"]
    try:
        densite, bords = np.histogram(J, bins=80, density=True)
    except ValueError:  # valeurs non finies ou dispersion sous la résolution numérique
        return figureMessage(
            "Histogramme Monte-Carlo", "Histogramme impossible : jeux non finis ou dispersion trop faible."
        )
    centres = (bords[:-1] + bords[1:]) / 2
    mu, sg = res["CF_moy"], res["CF_sigma"]
    x = np.linspace(J.min(), J.max(), 400)
    ppmMc = f"< {_ppm(mc['resolutionPpm'])}" if mc["nHors"] == 0 else _ppm(mc["ppm"])
    ppmFormule = bundle["verdicts"]["ppm"]
    fig = go.Figure()
    fig.add_trace(
        go.Bar(x=centres, y=densite, width=bords[1] - bords[0], marker_color=teinte(BLEU, 0.6), name="Tirages")
    )
    fig.add_trace(
        go.Scatter(
            x=x,
            y=np.exp(-0.5 * ((x - mu) / sg) ** 2) / (sg * math.sqrt(2 * math.pi)),
            mode="lines",
            line={"color": VERMILLON, "width": 2.5},
            name="Loi normale (formule)",
        )
    )
    _limites(fig, {k: (v if J.min() <= v <= J.max() else math.inf) for k, v in c.items() if k != "nom"})
    sous = f"Hors tolérance : {ppmMc} ppm (simulation) | {_ppm(ppmFormule)} ppm (formule)"
    miseEnPage(fig, _titre(f"Monte-Carlo (N = {mc['n']} tirages)", res, sous), 420)
    fig.update_layout(bargap=0)
    fig.update_xaxes(title="Jeu (mm)")
    fig.update_yaxes(title="Densité (1/mm)")
    legende = (
        f"Sur {mc['n']} assemblages simulés, {ppmMc} ppm sortent de {intervalle(c['jmin'], c['jmax'])} mm, "
        f"contre {_ppm(ppmFormule)} ppm par la formule de la loi normale."
    )
    return fig, legende


def figureComparaison(bundle: dict) -> tuple[go.Figure, str]:
    """Plages du jeu selon la méthode (pire cas, RSS ± kσ, RSS ± 6σ, Monte-Carlo) face aux limites (graph_comparaison).

    Entrée : bundle (sortie de calculerChaine). Sortie : (figure, légende) ; jeu en mm.
    """
    res, v, mc = bundle["res"], bundle["verdicts"], bundle["mc"]
    c, k = res["condition"], res["k_sigma"]
    plages = [
        ("Pire des cas", v["pireCas"]["min"], v["pireCas"]["max"]),
        (f"RSS ± {fr(k, 'g')} σ", v["rssK"]["min"], v["rssK"]["max"]),
        ("RSS ± 6 σ", v["rss6"]["min"], v["rss6"]["max"]),
    ]
    if mc is not None:
        plages.append(("Monte-Carlo 0,135–99,865 %", mc["quantiles"]["bas"], mc["quantiles"]["haut"]))
    plages = [(nom, lo, hi, lo >= c["jmin"] - TOL_COMPARAISON and hi <= c["jmax"] + TOL_COMPARAISON) for nom, lo, hi in plages]
    fig = go.Figure()
    for nom, lo, hi, ok in reversed(plages):
        verdict = libelleVerdict(ok, c)
        fig.add_trace(
            go.Bar(
                y=[nom],
                x=[hi - lo],
                base=[lo],
                orientation="h",
                marker_color=teinte(VERT_OI if ok else VERMILLON, 0.75),
                text=[f"{intervalle(lo, hi)}  {verdict}"],
                textposition="outside",
                cliponaxis=False,
                showlegend=False,
            )
        )
    fig.add_vline(res["CF_nom"], line={"color": GRIS, "dash": "dash"})
    _limites(fig, c)
    bornes = [b for _, lo, hi, _ in plages for b in (lo, hi)] + [x for x in (c["jmin"], c["jmax"]) if math.isfinite(x)]
    larg = (max(bornes) - min(bornes)) or 1e-3
    miseEnPage(
        fig,
        _titre(
            "Comparaison des méthodes de tolérancement", res, "Trait rouge : limite exigée | pointillé : jeu nominal"
        ),
        380,
    )
    fig.update_xaxes(title="Jeu (mm)", range=[min(bornes) - 0.15 * larg, max(bornes) + 0.6 * larg])
    fig.update_layout(margin={"l": 175})
    legende = (
        "Face à "
        + intervalle(c["jmin"], c["jmax"])
        + " mm : "
        + ", ".join(
            f"{nom.lower() if nom.startswith('Pire') else nom} {libelleVerdict(ok, c).lower()}"
            for nom, _, _, ok in plages
        )
        + "."
    )
    return fig, legende


def figureDistribution(bundle: dict) -> tuple[go.Figure, str]:
    """Loi normale du jeu (RSS), zones hors tolérance, pire cas, Cp, Cpk et ppm (graph_distribution).

    Entrée : bundle (sortie de calculerChaine). Sortie : (figure, légende) ; jeu en mm, densité en 1/mm.
    """
    res, v = bundle["res"], bundle["verdicts"]
    mu, sg, c = res["CF_moy"], res["CF_sigma"], res["condition"]
    if not sg > 0:
        return figureMessage("Distribution du jeu", "Tolérances nulles : pas de distribution à tracer.")
    bornes = [mu - 4 * sg, mu + 4 * sg, res["CF_min"], res["CF_max"]]
    bornes += [x for x in (c["jmin"], c["jmax"]) if math.isfinite(x) and abs(x - mu) < 8 * sg]
    a, b = min(bornes), max(bornes)
    x = np.linspace(a - 0.05 * (b - a), b + 0.05 * (b - a), 800)
    y = np.exp(-0.5 * ((x - mu) / sg) ** 2) / (sg * math.sqrt(2 * math.pi))
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x,
            y=y,
            mode="lines",
            fill="tozeroy",
            line={"color": BLEU},
            fillcolor=teinte(BLEU, 0.25),
            name="Loi normale (RSS)",
        )
    )
    for masque in (x <= c["jmin"], x >= c["jmax"]):
        if masque.sum() > 1:
            fig.add_trace(
                go.Scatter(
                    x=x[masque],
                    y=y[masque],
                    mode="lines",
                    fill="tozeroy",
                    line={"color": ROUGE, "width": 0},
                    fillcolor=teinte(ROUGE, 0.5),
                    name="Hors tolérance",
                    showlegend=False,
                )
            )
    fig.add_vline(mu, line={"color": GRIS, "width": 2}, annotation_text="Moyenne")
    for s in (-3, 3):
        fig.add_vline(mu + s * sg, line={"color": ORANGE, "dash": "dash"})
    for xp in (res["CF_min"], res["CF_max"]):
        fig.add_vline(xp, line={"color": ROUGE, "dash": "dot"})
    _limites(fig, c)
    cp = f"Cp = {fr(v['cp'], '.2f')} | " if math.isfinite(v["cp"]) else ""
    sous = f"{cp}Cpk = {fr(v['cpk'], '.2f')} | hors tolérance : {_ppm(v['ppm'])} ppm"
    sous += " (orange : ± 3 σ, pointillé rouge : pire cas)"
    miseEnPage(fig, _titre(f"Distribution du jeu (RSS) – σ = {fr(sg)} mm", res, sous), 420)
    fig.update_xaxes(title="Jeu (mm)")
    fig.update_yaxes(title="Densité (1/mm)")
    legende = (
        f"Le jeu suit une loi normale de moyenne {fr(mu)} mm et d'écart-type {fr(sg)} mm : "
        f"{cp.replace(' | ', ', ')}Cpk = {fr(v['cpk'], '.2f')}, soit {_ppm(v['ppm'])} ppm hors tolérance."
    )
    return fig, legende


def figureRisqueCp(bundle: dict) -> tuple[go.Figure, str]:
    """Risque hors tolérance (ppm, échelle log) selon le Cp du procédé, de 0,5 à 2,5 (graph_risque_cp).

    Entrée : bundle (sortie de calculerChaine). Sortie : (figure, légende) ; ppm plafonnés en bas à 0,001.
    """
    res, c = bundle["res"], bundle["res"]["condition"]
    if not res["CF_sigma"] > 0:
        return figureMessage("Risque selon le Cp", "Tolérances nulles : le risque ne dépend pas du Cp du procédé.")
    cps = np.linspace(0.5, 2.5, 200)
    ppm = np.maximum(np.asarray(risqueSelonCp(res, cps)["ppm"]), _PLANCHER_PPM)
    reperes = risqueSelonCp(res, _CP_REPERES)["ppm"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=cps, y=ppm, mode="lines", line={"color": BLEU, "width": 2.5}, name="ppm hors tolérance"))
    if np.all(ppm <= _PLANCHER_PPM):
        fig.add_annotation(
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            text="Jeu très loin des limites : aucun risque dans cette plage",
            showarrow=False,
        )
    else:
        for cp, p in zip(_CP_REPERES, reperes, strict=True):
            fig.add_trace(
                go.Scatter(
                    x=[cp],
                    y=[max(p, _PLANCHER_PPM)],
                    mode="markers+text",
                    marker={"color": ORANGE, "size": 9},
                    text=[f"Cp {fr(cp, '.2f')} : {_ppm(p)} ppm"],
                    textposition="top right",
                    showlegend=False,
                )
            )
    sous = f"Jeu moyen {fr(res['CF_moy'])} mm, limites {intervalle(c['jmin'], c['jmax'], '.4g')}"
    miseEnPage(fig, _titre("Quel Cp d'usinage faut-il ?", res, sous), 420)
    fig.update_xaxes(title="Cp du procédé")
    fig.update_yaxes(title="Hors tolérance (ppm)", type="log", range=[-3, 6])
    sous1 = cps[ppm < 1]
    if sous1.size and sous1[0] == cps[0]:
        legende = "Le risque reste sous 1 ppm dès un Cp de 0,5 : le jeu moyen est loin des limites."
    elif sous1.size:
        legende = f"Il faut un Cp d'usinage d'au moins {fr(sous1[0], '.2f')} pour rester sous 1 ppm hors tolérance."
    else:
        legende = (
            f"Même avec un Cp de 2,5, le risque reste de {_ppm(ppm[-1])} ppm : le jeu moyen est trop près d'une limite."
        )
    return fig, legende


def figureEffetThermique(bundle: dict) -> tuple[go.Figure, str]:
    """Contributions thermiques de chaque maillon (µm) et jeu à Tref et en service face aux limites.

    Entrée : bundle (sortie de calculerChaine).
    Sortie : (figure à deux panneaux, légende) ; port de graph_effet_thermique.
    """
    res, c = bundle["res"], bundle["res"]["condition"]
    if not res["thermique_actif"]:
        return figureMessage(
            "Effet thermique", "Pas d'effet thermique : aucun maillon dilatable hors de la température de référence."
        )
    dj = 1000 * np.asarray(res["dJ_th_i"])
    fig = make_subplots(rows=1, cols=2, column_widths=[0.6, 0.4], horizontal_spacing=0.14)
    fig.add_trace(
        go.Bar(
            x=res["Nom"],
            y=dj,
            marker_color=ORANGE,
            text=[fr(d, "+.1f") for d in dj],
            textposition="outside",
            cliponaxis=False,
            name="ΔJ thermique (µm)",
        ),
        row=1,
        col=1,
    )
    etats = [
        (f"Tref ({fr(res['Tref'], 'g')} °C)", res["CF_min_ref"], res["CF_max_ref"], res["CF_nom_ref"], GRIS),
        ("En service", res["CF_min"], res["CF_max"], res["CF_nom"], BLEU),
    ]
    oks = []
    for nom, lo, hi, nominal, couleur in etats:
        ok = lo >= c["jmin"] - TOL_COMPARAISON and hi <= c["jmax"] + TOL_COMPARAISON
        oks.append(ok)
        fig.add_trace(
            go.Bar(
                x=[nom],
                y=[max(hi - lo, 1e-6)],
                base=[lo],
                marker_color=teinte(couleur, 0.7),
                showlegend=False,
                text=[f"{fr(lo)} – {fr(hi)}<br>{'OK' if ok else 'HORS TOL.'}"],
                textposition="outside",
                cliponaxis=False,
                textfont={"color": VERT if ok else ROUGE},
            ),
            row=1,
            col=2,
        )
        fig.add_trace(
            go.Scatter(
                x=[nom],
                y=[nominal],
                mode="markers",
                marker={"symbol": "line-ew-open", "size": 30, "color": VERT, "line": {"width": 3}},
                showlegend=False,
            ),
            row=1,
            col=2,
        )
    _limites(fig, c, verticale=False, row=1, col=2)
    sous = f"Décalage du jeu moyen ΔJ = {fr(res['dJ_th'], '+.4f')} mm | trait rouge : limites exigées"
    miseEnPage(fig, _titre("Effet thermique", res, sous), 440)
    fig.update_layout(showlegend=False)
    fig.update_yaxes(title="ΔJ par maillon (µm)", row=1, col=1)
    fig.update_yaxes(title="Jeu au pire des cas (mm)", row=1, col=2)
    legende = (
        f"La dilatation décale le jeu moyen de {fr(1000 * res['dJ_th'], '+.1f')} µm : au pire des cas, le jeu est "
        f"{'conforme' if oks[0] else 'non conforme'} à Tref et "
        f"{'conforme' if oks[1] else 'non conforme'} {etatThermique(res)}."
    )
    return fig, legende


def figureJeuTemperature(bundle: dict) -> tuple[go.Figure, str]:
    """Jeu nominal, mini et maxi selon une température uniforme, face aux limites (graph_jeu_temperature).

    Entrée : bundle (sortie de calculerChaine). Sortie : (figure, légende) ; T en °C, jeu en mm.
    """
    res, jt = bundle["res"], bundle["jeuT"]
    if jt is None:
        return figureMessage(
            "Jeu selon la température",
            "Aucun maillon n'a de coefficient de dilatation : le jeu ne dépend pas de la température.",
        )
    c = res["condition"]
    T, jn, jmn, jmx = (np.asarray(jt[k]) for k in ("T", "nom", "min", "max"))
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=T, y=jmx, mode="lines", line={"color": BLEU}, name="Jeu maxi"))
    fig.add_trace(
        go.Scatter(
            x=T, y=jmn, mode="lines", line={"color": BLEU}, fill="tonexty", fillcolor=teinte(BLEU, 0.2), name="Jeu mini"
        )
    )
    fig.add_trace(go.Scatter(x=T, y=jn, mode="lines", line={"color": VERT_OI, "width": 2.5}, name="Jeu nominal"))
    _limites(fig, c, verticale=False)
    fig.add_vline(res["Tref"], line={"color": GRIS, "dash": "dash"}, annotation_text="Tref")
    if res["mode_thermique"] == "uniforme":
        fig.add_vline(res["reglages"]["tservice"], line={"color": ORANGE, "dash": "dash"}, annotation_text="T service")
    ok = (jmn >= c["jmin"] - TOL_COMPARAISON) & (jmx <= c["jmax"] + TOL_COMPARAISON)
    if np.ptp(jn) < 1e-12 and np.ptp(jmn) < 1e-12:
        bilan = "Coefficients de dilatation nuls : le jeu ne dépend pas de la température"
    elif ok.all():
        bilan = f"Conforme au pire des cas sur toute la plage balayée ({fr(T[0], '.0f')} à {fr(T[-1], '.0f')} °C)"
    elif not ok.any():
        bilan = f"Non conforme au pire des cas sur toute la plage balayée ({fr(T[0], '.0f')} à {fr(T[-1], '.0f')} °C)"
    else:
        # shortcut: première et dernière température conforme (comme MATLAB), même si la plage a un trou
        bilan = f"Conforme au pire des cas entre {fr(T[ok][0], '.0f')} et {fr(T[ok][-1], '.0f')} °C"
    if res["mode_thermique"] == "par_cote":
        bilan += " (courbe calculée pour une température uniforme)"
    miseEnPage(fig, f"Jeu selon la température<br><sup>{bilan}</sup>", 420)
    fig.update_xaxes(title="Température uniforme (°C)")
    fig.update_yaxes(title="Jeu (mm)")
    return fig, bilan + "."


def figureSensibilite(bundle: dict) -> tuple[go.Figure, str]:
    """Indices de Sobol du premier ordre de chaque maillon, en barres horizontales triées (le plus influent en haut).

    Entrée : bundle (sortie de calculerChaine). Sortie : (figure, légende) ; indices en % de la variance du jeu.
    Sans dispersion (σ du jeu nul), la figure est un message explicatif.
    """
    res = bundle["res"]
    lignes = sorted(indicesSensibilite(res), key=lambda s: s["rang"])
    if not res["CF_sigma"] > 0:
        return figureMessage("Sensibilité du jeu", "Toutes les tolérances sont nulles : pas de dispersion à répartir.")
    fig = go.Figure(
        go.Bar(
            y=[s["nom"] for s in lignes],
            x=[100 * s["indice"] for s in lignes],
            orientation="h",
            marker_color=BLEU,
            text=[f"{fr(100 * s['indice'], '.1f')} %" for s in lignes],
            textposition="outside",
            cliponaxis=False,
            name="Indice de Sobol",
        )
    )
    haut = lignes[0]
    miseEnPage(
        fig,
        _titre(
            "Sensibilité : quelle tolérance resserrer ?",
            res,
            f"Maillon le plus influent : {haut['nom']} ({fr(100 * haut['indice'], '.0f')} % de la variance)",
        ),
        max(300, 60 + 42 * len(lignes)),
    )
    fig.update_layout(showlegend=False)
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(title="Indice de Sobol du premier ordre (%)", range=[0, min(125, 100 * haut["indice"] * 1.25 + 5)])
    legende = (
        f"Le maillon {haut['nom']} explique {fr(100 * haut['indice'], '.1f')} % de la variance du jeu : "
        "c'est sa tolérance qu'il faut resserrer en premier."
    )
    return fig, legende


def figureDerive(bundle: dict, serie: dict, seuilPpm: float | None = None) -> tuple[go.Figure, str]:
    """Jeu moyen et ppm hors tolérance en fonction du nombre de pièces produites, avec l'intervalle de re-réglage.

    Entrées : bundle (sortie de calculerChaine), serie (core.derive.deriveSerie), seuilPpm (trait horizontal ou None).
    Sortie : (figure à deux graphiques superposés, légende). Les ppm sont tracés en échelle logarithmique
    (plancher 1e-3 ppm pour les valeurs nulles).
    """
    res, c = bundle["res"], bundle["res"]["condition"]
    n, mu = np.asarray(serie["n"]), np.asarray(serie["mu"])
    ppm = np.maximum(np.asarray(serie["ppm"], dtype=float), _PLANCHER_PPM)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1)
    fig.add_trace(go.Scatter(x=n, y=mu, mode="lines", line={"color": BLEU, "width": 2.5}, name="Jeu moyen"), 1, 1)
    for v, nom in ((c["jmin"], "Jmin"), (c["jmax"], "Jmax")):
        if math.isfinite(v):
            fig.add_hline(
                v, line={"color": ROUGE, "width": 2.5}, annotation_text=nom, annotation_font_color=ROUGE, row=1, col=1
            )
    fig.add_trace(go.Scatter(x=n, y=ppm, mode="lines", line={"color": VERMILLON, "width": 2.5}, name="ppm"), 2, 1)
    if seuilPpm is not None and seuilPpm > 0:
        fig.add_hline(
            seuilPpm,
            line={"color": ORANGE, "dash": "dash", "width": 2},
            annotation_text="Seuil de ppm",
            row=2,
            col=1,
        )
    inter = serie["intervalleRecalage"]
    if inter is not None and inter <= n[-1]:
        fig.add_vline(inter, line={"color": VERT_OI, "dash": "dash", "width": 2}, annotation_text="Re-réglage")
    if inter is None:
        bilan = "La dérive ne sort jamais le procédé des limites : aucun re-réglage nécessaire"
    else:
        bilan = f"Re-régler au plus tard toutes les {fr(inter, ',.0f').replace(',', ' ')} pièces"
    miseEnPage(fig, _titre("Dérive du procédé et re-réglage", res, bilan), 560)
    fig.update_yaxes(title="Jeu moyen (mm)", row=1, col=1)
    fig.update_yaxes(title="Hors tolérance (ppm)", type="log", row=2, col=1)
    fig.update_xaxes(title="Pièces produites depuis le réglage", row=2, col=1)
    return fig, bilan + "."
