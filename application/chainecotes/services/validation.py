"""Dossier de validation HTML d'une chaîne de cotes (même esprit que validation_report.py de MecaStruct).

Les contrôles du §3 sont refaits « à la main » en Python simple, directement depuis la saisie et les tables de
data/iso286.json, sans appeler chainecotes.core.chaine ; ils sont ensuite comparés aux valeurs du solveur.
Bilan honnête : un contrôle impossible (exception, valeur manquante, nan inattendu) compte comme un écart.
"""

import json
import math
import platform
import re
from datetime import datetime
from pathlib import Path

from chainecotes.core.chaine import estVide
from chainecotes.core.donnees import chargerJson
from chainecotes.services.calcul import calculerChaine
from chainecotes.services.validation_html import (
    ECART,
    OK,
    SECTIONS,
    avertissementsHTML,
    bilanHTML,
    cartoucheHTML,
    esc,
    gabarit,
    graphiquesHTML,
    hypothesesHTML,
    num,
    saisieHTML,
    tableauControles,
)

TOL_REL = 1e-9
TOL_ABS = 1e-12  # mm : plancher pour les grandeurs attendues nulles (décalage thermique, jeu nominal nul…)
_NAN = math.nan
_DESIGNATION = re.compile(r"^\s*(?:(\d+(?:[.,]\d+)?)\s*)?([A-Za-z]{1,2})\s*(\d{1,2})\s*$")
# σ_i / (|a_i| IT_i) selon la loi (écrit ici, indépendamment du solveur) ; k = procédé garanti de la loi normale.
_SIGMA_LOI = {
    "normale": lambda k: 1 / (2 * k),
    "uniforme": lambda k: 1 / math.sqrt(12),
    "triangulaire": lambda k: 1 / math.sqrt(24),  # h = IT/2 et σ = h/√6, soit IT/√24
}
_GOLDEN = Path(__file__).resolve().parents[2] / "tests" / "golden" / "golden_exemples.json"
_CLES_GOLDEN = ("CF_nom", "CF_moy", "CF_min", "CF_max", "CF_sigma", "dJ_th")


def _isoMain(texte: str, cote: float) -> dict:
    """Écarts ISO 286 relus dans data/iso286.json (règle js/JS de MATLAB : ± IT/2), en mm."""
    t = chargerJson("iso286.json")
    m = _DESIGNATION.match(str(texte))
    if not m:
        raise ValueError(f"désignation {texte!r} illisible")
    d = float(m.group(1).replace(",", ".")) if m.group(1) else float(cote)
    lettre, q = m.group(2), int(m.group(3))
    if not 0 < d <= t["bornes"][-1]:
        raise ValueError(f"cote {d:g} mm hors des tables")
    i = next(k for k, b in enumerate(t["bornes"]) if d <= b)
    it = t["it"][str(q)][i]
    plage = f"]{0 if i == 0 else t['bornes'][i - 1]:g} ; {t['bornes'][i]:g}] mm, IT{q} = {it:g} µm"
    arbres = list(t["arbre"])
    alesages = list(t["alesage"])
    if lettre.lower() == "js":
        es, ei, lu = it / 2, -it / 2, "± IT/2 (règle MATLAB)"
    elif lettre.islower():
        if lettre in arbres[: arbres.index("h") + 1]:
            es = t["arbre"][lettre][i]
            ei, lu = es - it, f"colonne arbre « {lettre} » = es"
        else:
            col = {"j": {5: "j5-6", 6: "j5-6", 7: "j7", 8: "j8"}.get(q), "k": "k4-7" if 4 <= q <= 7 else "k"}
            col = col.get(lettre, lettre)
            ei = t["arbre"][col][i]
            es, lu = ei + it, f"colonne arbre « {col} » = ei"
    elif lettre.isupper():
        if lettre in alesages[: alesages.index("H") + 1]:
            ei = t["alesage"][lettre][i]
            es, lu = ei + it, f"colonne alésage « {lettre} » = EI"
        else:
            col = f"J{q}" if lettre == "J" else f"{lettre}<=8" if lettre in "KMN" and q <= 8 else lettre
            es = t["alesage"][col][i]
            lu = f"colonne alésage « {col} » = ES"
            if (lettre in ("K", "M", "N") and 3 <= q <= 8) or (lettre not in ("J", "K", "M", "N") and 3 <= q <= 7):
                delta = t["delta"][str(q)][i]
                es += delta
                lu += f" + Δ = {delta:g} µm"
            ei = es - it
    else:
        raise ValueError(f"position {lettre!r} : casse mêlée")
    return {"es": es / 1000, "ei": ei / 1000, "lecture": f"{plage} ; {lu}"}


def _tol2768(cote: float, classe: str) -> float:
    """Écart ± ISO 2768-1 lu directement dans data/iso2768.json (relecture indépendante de core/iso2768)."""
    t = chargerJson("iso2768.json")
    if classe not in t["ecarts"] or not t["inferieure"] <= cote <= t["bornes"][-1]:
        raise ValueError(f"tolérance générale ISO 2768-{classe} indisponible pour la cote {cote:g} mm")
    e = t["ecarts"][classe][next(k for k, b in enumerate(t["bornes"]) if cote <= b)]
    if e is None:
        raise ValueError(f"la classe {classe} n'a pas de valeur ISO 2768-1 pour la cote {cote:g} mm")
    return float(e)


def _lireSaisie(probleme: dict) -> dict:
    """Saisie relue sans le solveur : k, Tref, condition et, par maillon, cote, es, ei, facteur·cos θ, loi, ΔT."""
    r = probleme.get("reglages") or {}
    # mêmes règles que normaliserReglages / normaliserCondition : seul None vaut « défaut » ; '' ou nan sont des erreurs
    k = 3.0 if r.get("kSigma") is None else float(r["kSigma"])
    tref = 20.0 if r.get("tref") is None else float(r["tref"])
    uniforme = str(r.get("modeT", "uniforme")) == "uniforme"
    dec = 0.0 if r.get("decentrage") is None else float(r["decentrage"])
    if not math.isfinite(dec) or dec < 0:
        raise ValueError(f"décentrage {dec!r} invalide (nombre fini ≥ 0 attendu)")
    c = probleme.get("condition") or {}
    jmin = -math.inf if c.get("jmin") is None else float(c["jmin"])
    jmax = math.inf if c.get("jmax") is None else float(c["jmax"])
    if not all(math.isfinite(v) for v in (k, tref)) or math.isnan(jmin) or math.isnan(jmax):
        raise ValueError("k, Tref, Jmin et Jmax doivent être des nombres (Jmin et Jmax peuvent être absents)")
    maillons = []
    for m in probleme.get("maillons") or []:
        cote = float(m["cote"])
        iso = None if estVide(m.get("iso")) else str(m["iso"]).strip()
        if iso:
            lu = _isoMain(iso, cote)
            es, ei = lu["es"], lu["ei"]
        elif estVide(m.get("es")) and estVide(m.get("ei")) and not estVide(r.get("tolGenerale")):
            es = _tol2768(cote, str(r["tolGenerale"]).strip().lower())
            ei = -es
        else:
            es, ei = float(m["es"]), float(m["ei"])
        loi = "normale" if estVide(m.get("loi")) else str(m["loi"]).strip().lower()
        if loi not in _SIGMA_LOI:
            raise ValueError(f"loi {loi!r} inconnue")
        derive = 0.0 if estVide(m.get("derive")) else float(m["derive"])
        if not math.isfinite(derive):
            raise ValueError(f"dérive {derive!r} invalide (nombre fini attendu)")
        ts = r.get("tservice", tref) if uniforme else m.get("tservice", tref)
        ts = tref if estVide(ts) else float(ts)
        facteur = 1.0 if estVide(m.get("facteur")) else float(m["facteur"])
        angle = 0.0 if estVide(m.get("angle")) else float(m["angle"])
        if not (math.isfinite(facteur) and facteur > 0 and math.isfinite(angle)):
            raise ValueError(f"facteur {facteur!r} ou angle {angle!r} invalide (facteur > 0, angle fini attendus)")
        sigma_reel = None if estVide(m.get("sigma_reel")) else float(m["sigma_reel"])
        moyenne_reelle = None if estVide(m.get("moyenne_reelle")) else float(m["moyenne_reelle"])
        base = 1.0 if str(m.get("sens", "+")).strip().replace("−", "-") == "+" else -1.0
        maillons.append(
            {
                "nom": str(m.get("nom") or ""),
                "cote": cote,
                "iso": iso,
                "es": es,
                "ei": ei,
                "proj": base if facteur == 1.0 and angle == 0.0 else base * facteur * math.cos(math.radians(angle)),
                "loi": loi,
                "sigma_reel": sigma_reel,
                "moyenne_reelle": moyenne_reelle,
                "derive": derive,
                "dT": ts - tref,
            }
        )
    return {"k": k, "jmin": jmin, "jmax": jmax, "decentrage": dec, "maillons": maillons}


# ---------------------------------------------------------------- contrôles


def _statut(attendu: float, obtenu: float, tol: float | None) -> tuple[float, float, str]:
    """(écart absolu, tolérance, statut) ; nan des deux côtés = « sans objet » attendu par la règle écrite."""
    if math.isnan(attendu) and math.isnan(obtenu):
        return 0.0, 0.0, OK
    if tol is None:
        tol = TOL_REL * max(abs(attendu), abs(obtenu)) + TOL_ABS
    d = abs(attendu - obtenu)
    return d, tol, OK if d <= tol else ECART


class _Liste:
    """Accumule les contrôles d'une section ; lit la valeur du solveur sans laisser une exception s'échapper."""

    def __init__(self, section: str, methode: str):
        self.section, self.methode, self.lignes = section, methode, []

    def groupe(self, titre: str) -> None:
        self.lignes.append({"groupe": titre})

    def ajouter(self, nom: str, formule: str, attendu: float, lireObtenu, unite: str = "", tol=None) -> None:
        try:
            obtenu = float(lireObtenu())
        except Exception as err:  # valeur absente ou illisible chez le solveur : contrôle impossible
            self.impossible(nom, f"valeur du solveur illisible ({type(err).__name__} : {err})")
            return
        ecart, tolerance, statut = _statut(float(attendu), obtenu, tol)
        self.lignes.append(
            {
                "nom": nom,
                "attendu": float(attendu),
                "obtenu": obtenu,
                "ecart": ecart,
                "tolerance": tolerance,
                "statut": statut,
                "methode": self.methode,
                "formule": formule,
                "unite": unite,
                "section": self.section,
            }
        )

    def impossible(self, nom: str, raison: str) -> None:
        self.lignes.append(
            {
                "nom": f"{nom} : contrôle impossible",
                "attendu": _NAN,
                "obtenu": _NAN,
                "ecart": _NAN,
                "tolerance": _NAN,
                "statut": ECART,
                "methode": f"{self.methode} ; {raison}",
                "formule": "",
                "unite": "",
                "section": self.section,
            }
        )

    def controles(self) -> list[dict]:
        return [x for x in self.lignes if "groupe" not in x]


def _ppm(mu: float, sg: float, jmin: float, jmax: float) -> float:
    if not sg > 0:
        return _NAN
    p = 0.0
    if math.isfinite(jmin):
        p += 0.5 * math.erfc((mu - jmin) / (sg * math.sqrt(2)))
    if math.isfinite(jmax):
        p += 0.5 * math.erfc((jmax - mu) / (sg * math.sqrt(2)))
    return 1e6 * p


def _calculMain(s: dict, alpha: list[float]) -> dict:
    """Jeu nominal, moyen, extrêmes, σ, Cp, Cpk, ppm et thermique, en Python simple (α du solveur en donnée)."""
    M, k = s["maillons"], s["k"]
    if len(alpha) != len(M):
        raise ValueError(f"{len(alpha)} coefficients α pour {len(M)} maillons")
    for m, a in zip(M, alpha, strict=True):
        m["alpha"] = float(a)
        m["cmoy"] = m["cote"] + (m["es"] + m["ei"]) / 2
        m["it"] = m["es"] - m["ei"]
        m["a"] = m["proj"] * (1 + m["alpha"] * m["dT"])
        m["c"] = _SIGMA_LOI[m["loi"]](k)
        m["sigma"] = abs(m["a"]) * (m["it"] * m["c"] if m["sigma_reel"] is None else m["sigma_reel"])
        m["dJ"] = m["cmoy"] * m["alpha"] * m["dT"] * m["proj"]
    h = {
        "nom": sum(m["cote"] * m["a"] for m in M),
        "moy": sum(m["cmoy"] * m["a"] for m in M),
        "demi": sum(abs(m["a"]) * m["it"] / 2 for m in M),
        "sigma": math.sqrt(sum(m["sigma"] ** 2 for m in M)),
        "dJ": sum(m["dJ"] for m in M),
    }
    h["min"], h["max"] = h["moy"] - h["demi"], h["moy"] + h["demi"]
    sg, jmin, jmax = h["sigma"], s["jmin"], s["jmax"]
    # moyenne mesurée : le procédé n'est plus centré sur la cote moyenne ; le décentrage s'applique ensuite
    h["decalageReel"] = sum(m["a"] * (m["moyenne_reelle"] - m["cmoy"]) for m in M if m["moyenne_reelle"] is not None)
    moyReelle = h["moy"] + h["decalageReel"]
    dmin = moyReelle - jmin if math.isfinite(jmin) else math.inf
    dmax = jmax - moyReelle if math.isfinite(jmax) else math.inf
    h["decalage"] = h["decalageReel"]
    if s["decentrage"] > 0 and not (math.isinf(dmin) and math.isinf(dmax)):
        h["decalage"] += -s["decentrage"] * sg if dmin <= dmax else s["decentrage"] * sg
    h["muProc"] = mu = h["moy"] + h["decalage"]
    h["cp"], h["cpk"] = _NAN, _NAN
    if sg > 0:
        cotes = [(mu - jmin) / (3 * sg)] if math.isfinite(jmin) else []
        cotes += [(jmax - mu) / (3 * sg)] if math.isfinite(jmax) else []
        h["cpk"] = min(cotes) if cotes else _NAN
        if len(cotes) == 2:
            h["cp"] = (jmax - jmin) / (6 * sg)
    h["ppm"] = _ppm(mu, sg, jmin, jmax)
    return h


def _controlesMain(probleme: dict, bundle: dict) -> tuple[_Liste, dict | None]:
    """§3 : recalcul indépendant face au solveur."""
    L = _Liste("main", "recalcul à la main depuis la saisie")
    res = bundle.get("res") or {}
    try:
        s = _lireSaisie(probleme)
    except Exception as err:
        L.impossible("Lecture de la saisie", f"{type(err).__name__} : {err}")
        return L, None
    M = s["maillons"]
    if any(m["iso"] for m in M):
        L.groupe("Écarts ISO 286 relus dans data/iso286.json (µm convertis en mm)")
        for i, m in enumerate(M):
            if m["iso"]:
                lu = _isoMain(m["iso"], m["cote"])["lecture"]
                f = rf"\text{{{m['iso']} : {lu}}}"
                L.ajouter(f"{m['nom']} : es ({m['iso']})", f, m["es"], lambda i=i: res["ES"][i], "mm")
                L.ajouter(f"{m['nom']} : ei ({m['iso']})", f, m["ei"], lambda i=i: res["EI"][i], "mm")
    try:
        h = _calculMain(s, [float(a) for a in res["alpha"]])
    except Exception as err:
        L.impossible("Recalcul de la chaîne", f"{type(err).__name__} : {err}")
        return L, None
    L.groupe("Maillons : cote moyenne et intervalle de tolérance")
    for i, m in enumerate(M):
        L.ajouter(
            f"{m['nom']} : C_moy",
            rf"C+\frac{{es+ei}}{{2}}={num(m['cote'])}+\frac{{{num(m['es'])}+({num(m['ei'])})}}{{2}}",
            m["cmoy"],
            lambda i=i: res["C_moy"][i],
            "mm",
        )
        L.ajouter(
            f"{m['nom']} : IT",
            rf"es-ei={num(m['es'])}-({num(m['ei'])})",
            m["it"],
            lambda i=i: res["IT"][i],
            "mm",
        )
    L.groupe("Cote condition (a_i = cos θ_i (1 + α_i ΔT_i), α_i du solveur pris comme donnée)")
    termes = " + ".join(f"({num(m['a'])})·{num(m['cote'])}" for m in M)
    L.ajouter("J nominal", rf"\sum a_i C_i = {termes}", h["nom"], lambda: res["CF_nom"], "mm")
    termes = " + ".join(f"({num(m['a'])})·{num(m['cmoy'])}" for m in M)
    L.ajouter("J moyen", rf"\sum a_i C_{{moy,i}} = {termes}", h["moy"], lambda: res["CF_moy"], "mm")
    L.ajouter(
        "Demi-dispersion au pire des cas",
        r"\sum |a_i|\,IT_i/2 = " + num(h["demi"]),
        h["demi"],
        lambda: (res["CF_max"] - res["CF_min"]) / 2,
        "mm",
    )
    L.ajouter("J min", rf"J_{{moy}}-\Delta = {num(h['moy'])}-{num(h['demi'])}", h["min"], lambda: res["CF_min"], "mm")
    L.ajouter("J max", rf"J_{{moy}}+\Delta = {num(h['moy'])}+{num(h['demi'])}", h["max"], lambda: res["CF_max"], "mm")
    bas = {"normale": num(2 * s["k"]), "uniforme": r"\sqrt{12}", "triangulaire": r"\sqrt{24}"}
    termes = " + ".join(f"({num(abs(m['a']) * m['it'])}/{bas[m['loi']]})^2" for m in M)
    L.ajouter("σ_J", rf"\sqrt{{{termes}}}", h["sigma"], lambda: res["CF_sigma"], "mm")
    L.groupe("Capabilité (jeu supposé normal ; nan = sans objet : σ nul ou limite absente)")
    sg = num(h["sigma"])
    L.ajouter(
        "Cp",
        rf"\frac{{J_{{max}}-J_{{min}}}}{{6\sigma_J}}=\frac{{{num(s['jmax'])}-{num(s['jmin'])}}}{{6\cdot{sg}}}",
        h["cp"],
        lambda: bundle["verdicts"]["cp"],
    )
    L.ajouter(
        "Cpk",
        r"\min\left(\frac{\mu-J_{min}}{3\sigma_J},\frac{J_{max}-\mu}{3\sigma_J}\right),"
        rf"\ \mu={num(h['muProc'])},\ \sigma_J={sg}",
        h["cpk"],
        lambda: bundle["verdicts"]["cpk"],
    )
    L.ajouter(
        "ppm hors tolérance",
        r"10^6\left[\tfrac12\operatorname{erfc}\frac{\mu-J_{min}}{\sigma_J\sqrt2}+\tfrac12\operatorname{erfc}\frac{J_{max}-\mu}{\sigma_J\sqrt2}\right]",
        h["ppm"],
        lambda: bundle["verdicts"]["ppm"],
        "ppm",
    )
    if s["decentrage"] > 0:
        L.groupe("Décentrage du procédé (moyenne décalée vers la limite la plus proche)")
        L.ajouter(
            "Décalage de la moyenne",
            rf"\pm d\,\sigma_J = {num(s['decentrage'])}\cdot{sg}",
            h["decalage"],
            lambda: res["decalage"],
            "mm",
        )
        L.ajouter(
            "Moyenne du procédé",
            rf"J_{{moy}}+\Delta\mu = {num(h['moy'])}+({num(h['decalage'])})",
            h["muProc"],
            lambda: res["CF_moy_proc"],
            "mm",
        )
        L.ajouter("Décentrage d (σ_J)", "d", s["decentrage"], lambda: bundle["decentrage"], "σ")
    L.groupe("Effet thermique (décalage du jeu moyen ; α_i du solveur pris comme donnée)")
    for i, m in enumerate(M):
        L.ajouter(
            f"{m['nom']} : ΔJ_th",
            rf"C_{{moy}}\,\alpha\,\Delta T\cos\theta={num(m['cmoy'])}\cdot{num(m['alpha'])}"
            rf"\cdot{num(m['dT'])}\cdot({num(m['proj'])})",
            m["dJ"],
            lambda i=i: res["dJ_th_i"][i],
            "mm",
        )
    L.ajouter("ΔJ_th total", r"\sum \Delta J_{th,i}", h["dJ"], lambda: res["dJ_th"], "mm")
    return L, h


def _controlesMonteCarlo(bundle: dict, h: dict | None, s: dict | None) -> tuple[_Liste, str]:
    """§4 : moyenne et ppm simulés face aux formules (tolérances statistiques explicites)."""
    L = _Liste("montecarlo", "Monte-Carlo face à la formule")
    mc = bundle.get("mc")
    if h is None:
        L.impossible("Monte-Carlo", "recalcul à la main indisponible (voir §3)")
        return L, ""
    if not h["sigma"] > 0:
        return L, "<p>Toutes les tolérances sont nulles : pas de dispersion, pas de simulation Monte-Carlo.</p>"
    if mc is None:
        return L, "<p>Simulation Monte-Carlo non demandée pour ce calcul : aucun contrôle de ce type.</p>"
    try:
        n = int(mc["n"])
        tolMoy = 4 * h["sigma"] / math.sqrt(n)
    except Exception as err:
        L.impossible("Monte-Carlo", f"résultat illisible ({type(err).__name__} : {err})")
        return L, ""
    L.ajouter(
        "Moyenne simulée du jeu",
        rf"|\bar J - \mu| \le 4\sigma_J/\sqrt N = 4\cdot{num(h['sigma'])}/\sqrt{{{n}}}",
        h["muProc"],
        lambda: mc["moyenne"],
        "mm",
        tolMoy,
    )
    p = h["ppm"] / 1e6
    tolPpm = 1e6 * (4 * math.sqrt(p * (1 - p) / n) + 1 / n)
    formule = rf"|ppm_{{MC}}-ppm| \le 10^6\left(4\sqrt{{p(1-p)/N}}+1/N\right),\ p={num(p)}"
    if all(m["loi"] == "normale" for m in s["maillons"]):
        L.ajouter("ppm simulé", formule, h["ppm"], lambda: mc["ppm"], "ppm", tolPpm)
        return L, ""
    try:
        ecart = abs(float(mc["ppm"]) - h["ppm"])
        texte = (
            f"ppm simulé {num(float(mc['ppm']))} contre {num(h['ppm'])} par la formule (écart {num(ecart)}, "
            f"tolérance statistique {num(tolPpm)})"
        )
    except Exception as err:
        texte = f"ppm simulé illisible ({type(err).__name__} : {err})"
    return L, (
        "<p><strong>Contrôle informatif (non compté) :</strong> au moins une loi n'est pas normale ; "
        f"le jeu n'est donc pas exactement normal et la formule des ppm n'est qu'une approximation. {esc(texte)}.</p>"
    )


def _exempleIdentique(probleme: dict) -> str | None:
    """Identifiant de l'exemple de data/exemples.json dont le problème est identique à la saisie, sinon None."""
    for e in chargerJson("exemples.json")["exemples"]:
        if {k: e[k] for k in ("condition", "reglages", "maillons")} == {
            k: probleme.get(k) for k in ("condition", "reglages", "maillons")
        }:
            return e["id"]
    return None


def _controlesMatlab(probleme: dict, bundle: dict) -> tuple[_Liste, str]:
    """§5 : solveur face aux valeurs calculées par MATLAB (tests/golden/golden_exemples.json)."""
    L = _Liste("matlab", "référence MATLAB (tests/golden/golden_exemples.json)")
    ident = _exempleIdentique(probleme)
    if ident is None:
        return L, (
            "<p>Ce problème n'est identique à aucun exemple de la bibliothèque : pas de valeur MATLAB de référence "
            "pour lui. La concordance avec MATLAB est établie par les tests du logiciel sur les exemples.</p>"
        )
    try:
        g = next(x for x in json.loads(_GOLDEN.read_text(encoding="utf-8"))["exemples"] if x["id"] == ident)
    except Exception as err:
        L.impossible(f"Référence MATLAB de « {ident} »", f"fichier golden illisible ({type(err).__name__} : {err})")
        return L, ""
    res, ver = bundle.get("res") or {}, bundle.get("verdicts") or {}

    def ref(v):
        return _NAN if v is None else float(v)

    for cle in _CLES_GOLDEN:
        L.ajouter(cle, rf"\text{{MATLAB : {cle}}}", ref(g["resultats"][cle]), lambda c=cle: res[c], "mm")
    for cle in ("cp", "cpk", "ppm"):
        L.ajouter(cle, rf"\text{{MATLAB : {cle}}}", ref(g["graphiques"][cle]), lambda c=cle: ver[c])
    return L, f"<p>Problème identique à l'exemple « {esc(ident)} » : valeurs de {esc(g.get('source', ''))}.</p>"


# ---------------------------------------------------------------- rendu


def dossierValidation(probleme: dict, bundle: dict | None = None, graphiques: list[dict] | None = None) -> dict:
    """Dossier de validation HTML autonome d'un problème : contrôles indépendants du solveur et bilan.

    Entrées : probleme (dict condition, reglages, maillons), bundle (sortie de calculerChaine ; calculé si None),
    graphiques (sortie de graphiquesDossier : ajoute l'annexe « graphiques du calcul » à la page ; None : sans).
    Sortie : dict html (page complète, str ; formules en vrais caractères, sans script distant), controles (liste de dict nom, attendu,
    obtenu, ecart, tolerance (unités de la grandeur : mm, ppm ou sans unité), statut « OK » ou « ÉCART »,
    methode, plus formule, unite, section), nOk, nTotal (entiers), bilan (« N / M contrôles de calcul concordent »).
    Erreur : ErreurChaine si bundle est None et que le problème ne se calcule pas.
    """
    if bundle is None:
        bundle = calculerChaine(probleme)
    main, h = _controlesMain(probleme, bundle)
    try:
        s = _lireSaisie(probleme)
    except Exception:
        s = None
    mc, mcTexte = _controlesMonteCarlo(bundle, h, s)
    matlab, matlabTexte = _controlesMatlab(probleme, bundle)
    controles = main.controles() + mc.controles() + matlab.controles()
    nTotal = len(controles)
    nOk = sum(c["statut"] == OK for c in controles)
    bilan = f"{nOk} / {nTotal} contrôles de calcul concordent"
    impossibles = [c for c in controles if math.isnan(c["attendu"]) and math.isnan(c["obtenu"]) and c["statut"] != OK]
    bilanSection = f"<p>{bilanHTML(nOk, nTotal, bilan)}</p>"
    if impossibles:
        bilanSection += (
            "<p>Contrôles impossibles, comptés comme non concordants : "
            + "; ".join(esc(f"{c['nom']} ({c['methode']})") for c in impossibles)
            + ".</p>"
        )
    bilanSection += (
        "<p>Tolérance des contrôles déterministes : 10⁻⁹ en relatif plus 10⁻¹² en absolu ; Monte-Carlo : "
        "tolérances statistiques écrites au §4. Un contrôle impossible ou une valeur nan inattendue n'est jamais "
        "compté comme concordant.</p>"
    )
    contenus = {
        "saisie": saisieHTML(probleme),
        "hypotheses": hypothesesHTML(bundle),
        "main": "<p>Chaque grandeur est recalculée en Python simple depuis la saisie (ISO 286 relu dans "
        "data/iso286.json), sans appeler le solveur, puis comparée à la valeur du solveur. Les coefficients "
        "de dilatation α_i sont ceux du solveur, pris comme données (lus sur les courbes des matériaux).</p>"
        + tableauControles(main),
        "montecarlo": mcTexte + tableauControles(mc),
        "matlab": matlabTexte + tableauControles(matlab),
        "avertissements": avertissementsHTML(bundle),
        "bilan": bilanSection,
    }
    if graphiques is not None:
        contenus["graphiques"] = graphiquesHTML(graphiques)
    sections = [
        {"id": i, "titre": t, "titre_court": t.split(". ", 1)[1], "html": contenus[i]}
        for i, t in SECTIONS
        if i in contenus
    ]
    nomJ = (probleme.get("condition") or {}).get("nom") or "Jeu J"
    page = gabarit().render(
        titre=f"chaîne de cotes « {nomJ} »",
        date=datetime.now().strftime("%d/%m/%Y %H:%M"),
        python=platform.python_version(),
        bilan=bilanHTML(nOk, nTotal, bilan),
        cartouche=cartoucheHTML(probleme),
        sections=sections,
    )
    return {"html": page, "controles": controles, "nOk": nOk, "nTotal": nTotal, "bilan": bilan}
