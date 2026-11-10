"""Éléments HTML du dossier de validation : échappement, tableaux, sections et gabarit Jinja.

Ce module ne fait aucun calcul : il met en page les contrôles que chainecotes.services.validation a refaits. Il
n'importe ni streamlit ni plotly.
"""

import base64
import html
import math
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from chainecotes.core.chaine import estVide
from chainecotes.core.formules import texVersHtml
from chainecotes.services.cartouche import REVISIONS, lignesCartouche, revisions

OK, ECART = "OK", "ÉCART"
_TEMPLATES = Path(__file__).parent / "templates"

SECTIONS = (
    ("saisie", "1. Saisie du problème"),
    ("hypotheses", "2. Hypothèses et domaine d'application"),
    ("main", "3. Contrôles refaits à la main"),
    ("montecarlo", "4. Monte-Carlo face à la formule"),
    ("matlab", "5. Comparaison à l'application MATLAB"),
    ("avertissements", "6. Avertissements du calcul"),
    ("bilan", "7. Bilan"),
    ("graphiques", "8. Annexe : graphiques du calcul"),  # présente seulement si des graphiques sont fournis
)

HYPOTHESES = (
    "Chaîne linéaire à une dimension : chaque maillon est une cote portée par le même axe que la cote condition.",
    "Sens « + » ↔ θ = 0° (cos θ = +1, le maillon augmente le jeu) ; sens « − » ↔ θ = 180° (cos θ = −1).",
    "Coefficient libre (ajout au MATLAB, défaut sans effet) : aᵢ = facteur · cos θᵢ, l'angle saisi s'ajoutant à θ ; "
    "sans facteur ni angle, aᵢ = ±1.",
    "Chaque cote réalisée est centrée sur sa cote moyenne C_moy = C + (es + ei)/2 ; IT = es − ei.",
    "Procédé garanti à ± k σ : l'intervalle de tolérance vaut IT = 2 k σ (loi normale, σ_i = IT/(2k)).",
    "Loi uniforme (ajout au MATLAB) : cote équiprobable sur [C_moy − IT/2 ; C_moy + IT/2], σ_i = IT/√12.",
    "Loi triangulaire (ajout au MATLAB) : symétrique sur [C_moy − IT/2 ; C_moy + IT/2], σ_i = IT/(2√6).",
    "Décentrage (ajout au MATLAB, défaut 0) : la moyenne du jeu est décalée de d·σ_J vers la limite la plus "
    "proche ; Cpk, ppm et Monte-Carlo en tiennent compte, pas Cp ni le pire des cas.",
    "Dérive d'un maillon (ajout, défaut 0) : valeur conservée et contrôlée, non utilisée par ce calcul.",
    "Données : écarts ISO 286 lus dans data/iso286.json (contrôlés contre l'application MATLAB) ; dilatation des "
    "matériaux dans data/materiaux.json (sources et fiabilité de chaque matériau sur la page Matériaux). Les coûts "
    "de la répartition au coût minimal sont indicatifs et n'entrent pas dans ce dossier.",
    "Mesures de l'atelier (ajout au MATLAB, défaut sans effet) : l'écart type mesuré d'une cote remplace σ_i = IT·c "
    "de sa loi (loi normale) ; sa moyenne mesurée décale la moyenne du jeu, comme un décentrage.",
    "Tolérance géométrique (ajout au MATLAB, ISO 1101) : une zone de largeur t est un maillon de cote nulle et "
    "d'IT = t (± t/2 dans le sens de la chaîne) ; au maximum de matière, le bonus s'ajoute à t au pire des cas.",
    "Cotes indépendantes entre elles : les variances s'ajoutent (σ_J = √Σ σ_i²), aucune corrélation.",
    "Cp, Cpk et ppm supposent un jeu de loi normale (approximation du théorème central limite si lois non normales).",
    "Effet thermique linéaire : a_i = cos θ_i (1 + α_i ΔT_i), α_i lu sur les courbes du matériau (sécant entre "
    "Tref et T service) ou saisi ; pas de gradient dans une pièce, pas de contrainte mécanique.",
    "Limites : pas de jeu géométrique 2D/3D, pas de tolérance de forme ou de position, pas de déformation "
    "élastique ; un résultat hors de ce domaine doit être vérifié autrement.",
)


def esc(x) -> str:
    return html.escape(str(x), quote=False)


def num(x) -> str:
    if isinstance(x, float) and math.isnan(x):
        return "nan"
    if isinstance(x, float) and math.isinf(x):
        return "∞" if x > 0 else "−∞"
    return f"{x:.10g}"


# ---------------------------------------------------------------- lecture indépendante de la saisie


def tableauControles(liste) -> str:
    """Tableau HTML des contrôles ; `liste` est la liste de contrôles de validation.py (attribut `lignes`)."""
    if not liste.lignes:
        return ""
    h = (
        '<table class="hand"><tr><th>Grandeur</th><th>Formule avec valeurs</th><th>Attendu</th>'
        "<th>Solveur</th><th>Écart</th><th>Tolérance</th><th>Verdict</th></tr>"
    )
    for r in liste.lignes:
        if "groupe" in r:
            h += f'<tr><td colspan="7" class="grp">{esc(r["groupe"])}</td></tr>'
            continue
        un = f" {esc(r['unite'])}" if r["unite"] else ""
        v = '<span class="ok">concordent</span>' if r["statut"] == OK else f'<span class="ko">{ECART}</span>'
        fm = texVersHtml(r["formule"]) if r["formule"] else f'<span class="muted">{esc(r["methode"])}</span>'
        h += (
            f'<tr><td>{esc(r["nom"])}</td><td class="fm">{fm}</td><td class="n">{num(r["attendu"])}{un}</td>'
            f'<td class="n">{num(r["obtenu"])}{un}</td><td class="n">{r["ecart"]:.2g}</td>'
            f'<td class="n">{r["tolerance"]:.2g}</td><td>{v}</td></tr>'
        )
    return h + "</table>"


def kv(lignes) -> str:
    return (
        '<table class="kv">'
        + "".join(f'<tr><td>{esc(a)}</td><td class="v">{esc(b)}</td></tr>' for a, b in lignes)
        + "</table>"
    )


def cartoucheHTML(probleme: dict) -> str:
    """Cartouche du dossier (projet, indice, statut… et historique des révisions) ; vide s'il n'est pas rempli."""
    lignes, revs = lignesCartouche(probleme), revisions(probleme)
    h = kv(lignes) if lignes else ""
    if revs:
        h += (
            '<table><tr><th colspan="4">Historique des révisions</th></tr>'
            + "<tr>"
            + "".join(f"<th>{esc(t)}</th>" for _, t in REVISIONS)
            + "</tr>"
            + "".join("<tr>" + "".join(f"<td>{esc(r[c])}</td>" for c, _ in REVISIONS) + "</tr>" for r in revs)
            + "</table>"
        )
    return f'<div class="cartouche">{h}</div>' if h else ""


def saisieHTML(probleme: dict) -> str:
    c, r = probleme.get("condition") or {}, probleme.get("reglages") or {}

    def lim(v):
        return "pas de limite" if estVide(v) else f"{v:g} mm"

    h = "<h3>Cote condition</h3>" + kv(
        [("Nom", c.get("nom", "Jeu J")), ("J min", lim(c.get("jmin"))), ("J max", lim(c.get("jmax")))]
    )
    h += "<h3>Réglages</h3>" + kv(
        [
            ("Procédé garanti à ± k σ", r.get("kSigma", 3)),
            ("Température de référence", f"{r.get('tref', 20)} °C"),
            ("Mode de température", r.get("modeT", "uniforme")),
            ("Température de service (mode uniforme)", f"{r.get('tservice', r.get('tref', 20))} °C"),
            ("Décentrage du procédé", f"{r.get('decentrage') or 0:g} σ_J"),
            ("Tolérance générale", f"ISO 2768-{r['tolGenerale']}" if r.get("tolGenerale") else "aucune"),
        ]
    )
    cols = ("nom", "sens", "cote", "iso", "es", "ei", "loi", "materiau", "alpha", "tservice", "derive")
    tete = (
        "Nom",
        "Sens",
        "Cote (mm)",
        "ISO",
        "es (mm)",
        "ei (mm)",
        "Loi",
        "Matériau",
        "α (1e-6/K)",
        "T service (°C)",
        "Dérive (µm/1000)",
    )
    maillons = probleme.get("maillons") or []
    if any(not estVide(m.get(k)) for m in maillons for k in ("facteur", "angle")):  # coefficients libres saisis
        cols, tete = cols + ("facteur", "angle"), tete + ("Facteur", "Angle (°)")
    if any(not estVide(m.get(k)) for m in maillons for k in ("sigma_reel", "moyenne_reelle")):  # mesures de l'atelier
        cols, tete = cols + ("sigma_reel", "moyenne_reelle"), tete + ("σ mesuré (mm)", "Moyenne mesurée (mm)")
    h += "<h3>Maillons</h3><table><tr>" + "".join(f"<th>{x}</th>" for x in tete) + "</tr>"
    for m in maillons:
        h += "<tr>" + "".join(f"<td>{'' if estVide(m.get(k)) else esc(m.get(k))}</td>" for k in cols) + "</tr>"
    return h + "</table>"


def hypothesesHTML(bundle: dict) -> str:
    h = "<ul>" + "".join(f"<li>{esc(x)}</li>" for x in HYPOTHESES) + "</ul>"
    hors = [m["nom"] for m in (bundle.get("res") or {}).get("maillons", []) if m.get("horsDomaine")]
    if hors:
        h += (
            '<p class="warnbox">Matériau(x) employé(s) hors du domaine de leur courbe de dilatation : '
            f"{esc(', '.join(hors))} (voir §6).</p>"
        )
    return h


def avertissementsHTML(bundle: dict) -> str:
    av = bundle.get("avertissements") or []
    if not av:
        return "<p>Aucun avertissement pour ce calcul.</p>"
    return '<ul class="warnbox">' + "".join(f"<li>{esc(x)}</li>" for x in av) + "</ul>"


def bilanHTML(nOk: int, nTotal: int, bilan: str) -> str:
    if nTotal == 0:
        return '<span class="ko">aucun contrôle de calcul n\'a pu être fait</span>.'
    h = f'<span class="{"ok" if nOk == nTotal else "ko"}">{esc(bilan)}</span>'
    if nOk < nTotal:
        h += f' ; <span class="ko">{nTotal - nOk} {ECART}(S) à examiner</span>'
    return h + "."


def gabarit():
    return Environment(loader=FileSystemLoader(_TEMPLATES), autoescape=True).get_template("validation.html.j2")


def graphiquesHTML(graphiques: list[dict]) -> str:
    """Annexe HTML : un graphique par bloc, avec sa légende.

    Entrée : graphiques (sortie de services.graphiques_dossier.graphiquesDossier : titre, legende, fig, png).
    Sortie : HTML. Image PNG incluse dans la page si elle existe ; sinon graphique Plotly interactif (bibliothèque
    chargée depuis un CDN, une seule fois pour toute la page).
    """
    blocs, jsDejaCharge = [], False
    for g in graphiques:
        if g.get("png"):
            corps = f'<img src="data:image/png;base64,{base64.b64encode(g["png"]).decode()}" alt="{esc(g["titre"])}">'
        else:
            corps = g["fig"].to_html(full_html=False, include_plotlyjs=False if jsDejaCharge else "cdn")
            jsDejaCharge = True
        blocs.append(f"<figure><h3>{esc(g['titre'])}</h3>{corps}<figcaption>{esc(g['legende'])}</figcaption></figure>")
    return "".join(blocs) or "<p>Aucun graphique.</p>"
