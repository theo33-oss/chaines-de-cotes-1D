"""Page « Matériaux et dilatation » : tableau des matériaux, courbes ε(T) et α moyen, calculatrice, sources.

Toutes les valeurs viennent de data/materiaux.json par chainecotes.core.materiaux (même calcul que MATLAB).
"""

import math
import unicodedata

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from chainecotes.bureau import state
from chainecotes.bureau.widgets import Page, Zone
from chainecotes.core.materiaux import (
    PERSONNALISE,
    alphaMateriau,
    courbesMateriaux,
    deformation,
    listeMateriaux,
    sourcesMateriaux,
)
from chainecotes.plots._common import BLEU, GRIS, VERMILLON, fr, miseEnPage, teinte

T_MIN, T_MAX = -269.0, 600.0  # °C : de l'hélium liquide au haut des courbes du classeur


def domaineEmploi(m: dict) -> str:
    """Domaine d'emploi d'un matériau en clair : T min, T max, zone sensible et motif.

    Entrée : m (élément de listeMateriaux). Sortie : texte (°C), vide si rien n'est connu.
    """
    morceaux = []
    if not math.isnan(m["tmin"]) or not math.isnan(m["tmax"]):
        morceaux.append(f"{fr(m['tmin'], 'g')} à {fr(m['tmax'], 'g')} °C")
    if not math.isnan(m["zmin"]):
        morceaux.append(f"zone sensible {fr(m['zmin'], 'g')} à {fr(m['zmax'], 'g')} °C")
    if m["motif"]:
        morceaux.append(m["motif"])
    return " ; ".join(morceaux)


def intervallesHors(T: np.ndarray, hors: np.ndarray) -> list[tuple[float, float]]:
    """Intervalles de température contigus où le matériau est hors domaine.

    Entrées : T (°C, croissant), hors (bool, même forme). Sortie : liste de (début, fin) en °C.
    """
    zones, debut = [], None
    for t, h in zip(T, hors, strict=True):
        if h and debut is None:
            debut = t
        if not h and debut is not None:
            zones.append((debut, t))
            debut = None
    if debut is not None:
        zones.append((debut, T[-1]))
    return zones


def figureDilatation(m: dict, tref: float) -> tuple[go.Figure, str]:
    """Figure à deux étages : déformation ε(T) depuis 20 °C, puis α moyen entre Tref et T, de −269 à 600 °C.

    Entrées : m (élément de listeMateriaux), tref (°C). Sortie : (figure Plotly, légende en français).
    Les zones hors domaine d'emploi (ou extrapolées) sont grisées.
    """
    T = np.linspace(T_MIN, T_MAX, 870)
    eps = deformation(m, T) * 1e6  # µm/m
    r = alphaMateriau(m["nom"], T, tref)
    alpha = r["alpha"] * 1e6
    zones = intervallesHors(T, r["horsDomaine"])
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08)
    fig.add_trace(go.Scatter(x=T, y=eps, name="ε(T) depuis 20 °C", line={"color": BLEU, "width": 2}), row=1, col=1)
    fig.add_trace(
        go.Scatter(x=T, y=alpha, name=f"α moyen depuis {fr(tref, 'g')} °C", line={"color": VERMILLON, "width": 2}),
        row=2,
        col=1,
    )
    for a, b in zones:
        for ligne in (1, 2):
            fig.add_vrect(x0=a, x1=b, fillcolor=teinte(GRIS, 0.25), line_width=0, layer="below", row=ligne, col=1)
    miseEnPage(fig, f"Dilatation de {m['nom']} (zones grisées : hors domaine d'emploi ou extrapolé)", 560)
    fig.update_yaxes(title_text="ε (µm/m)", row=1, col=1)
    fig.update_yaxes(title_text="α moyen (10⁻⁶/K)", row=2, col=1)
    fig.update_xaxes(title_text="Température (°C)", row=2, col=1)
    legende = (
        f"{m['nom']} : déformation de {fr(eps[0], '.0f')} µm/m à {fr(T_MIN, 'g')} °C et {fr(eps[-1], '.0f')} µm/m à "
        f"{fr(T_MAX, 'g')} °C (nulle à 20 °C) ; α moyen depuis {fr(tref, 'g')} °C de {fr(np.nanmin(alpha), '.2f')} "
        f"à {fr(np.nanmax(alpha), '.2f')} × 10⁻⁶/K. "
    )
    if zones:
        legende += "Hors domaine : " + ", ".join(f"{fr(a, '.0f')} à {fr(b, '.0f')} °C" for a, b in zones) + "."
    else:
        legende += "Aucune zone hors domaine sur cette plage."
    return fig, legende


def _sansAccent(texte: str) -> str:
    """Texte en minuscules sans accents, pour comparer une recherche à un contenu."""
    return "".join(c for c in unicodedata.normalize("NFD", str(texte).lower()) if unicodedata.category(c) != "Mn")


def filtrerLignes(lignes: list[dict], texte: str, familles: list[str]) -> list[dict]:
    """Lignes du tableau dont la famille est choisie (toutes si vide) et qui contiennent tous les mots cherchés.

    Entrées : lignes (dict du tableau, colonnes « Famille » et textes), texte (mots séparés par des espaces),
    familles (liste de familles ; vide = toutes). Sortie : sous-liste de lignes, dans l'ordre.
    """
    mots = _sansAccent(texte).split()
    gardees = []
    for ligne in lignes:
        if familles and ligne["Famille"] not in familles:
            continue
        contenu = _sansAccent(" ".join(str(v) for v in ligne.values()))
        if all(mot in contenu for mot in mots):
            gardees.append(ligne)
    return gardees


class PageMateriaux(Page):
    def rendre(self, z: Zone) -> None:
        self.materiaux = [m for m in listeMateriaux() if m["nom"] != PERSONNALISE]
        self.noms = [m["nom"] for m in self.materiaux]
        z.titre("Matériaux et dilatation")
        z.texte(
            f"Les {len(self.materiaux)} matériaux de l'application MATLAB, avec leur coefficient de dilatation α à "
            "température ambiante, leur courbe de dilatation en température et leurs limites d'emploi. Le calcul de la "
            "chaîne utilise α moyen entre la température de référence des cotes (Tref) et la température de service : "
            "ΔL = α · L · (T − Tref)."
        )
        z.sousTitre("Tableau des matériaux")
        familles = sorted({m["famille"] for m in self.materiaux})
        cherche, choix = z.colonnes([2, 1])
        relance = lambda: self.tableau.rafraichir()  # noqa: E731
        cherche.saisie(
            "Rechercher un matériau", "materiaux.recherche", apres=relance,
            indice="Nom, famille, source, courbe… (ex. inox, aluminium 6061, NIST)",
            aide="Les mots sont cherchés sans tenir compte des majuscules ni des accents ; tous doivent être présents.",
        )  # fmt: skip
        choix.multi("Catégories", familles, "materiaux.categories", apres=relance,
                    aide="Familles de matériaux à afficher ; aucune cochée : toutes.")  # fmt: skip
        self.tableau = z.section(self._tableau)
        z.sousTitre("Courbe de dilatation et calculatrice")
        self.calculatrice = z.section(self._calculatrice)
        z.sousTitre("Sources")
        z.tableau(pd.DataFrame(sourcesMateriaux()).rename(columns={"cle": "Clé", "source": "Source", "lien": "Lien"}))
        z.sousTitre("Courbes de dilatation du classeur")
        z.tableau(
            pd.DataFrame(
                [
                    {
                        "Courbe": c["cle"],
                        "Description": c["description"],
                        "Points": len(c["points"]),
                        "Températures (°C)": f"{fr(min(p['T'] for p in c['points']), 'g')} à "
                        f"{fr(max(p['T'] for p in c['points']), 'g')}",
                    }
                    for c in courbesMateriaux()
                    if c["points"]
                ]
            )
        )
        z.legende(
            "Une courbe « recalée » est celle d'un matériau voisin, mise à l'échelle pour redonner l'α du tableau. "
            "Au-delà des points d'une courbe, la déformation est extrapolée linéairement : la zone est grisée."
        )

    def _tableau(self, z: Zone) -> None:
        lignes = [
            {
                "Matériau": m["nom"],
                "Famille": m["famille"],
                "α (10⁻⁶/K)": m["alpha"] * 1e6,
                "Plage de α (°C)": m["plage"],
                "Fiabilité": m["fiabilite"],
                "Sources": m["sources"],
                "Courbe": m["courbeNom"] + (" (recalée)" if m["recale"] else ""),
                "Domaine d'emploi": domaineEmploi(m),
            }
            for m in self.materiaux
        ]
        lignes = filtrerLignes(lignes, state.v.get("materiaux.recherche", ""), state.v.get("materiaux.categories", []))
        z.legende(f"{len(lignes)} matériau(x) sur {len(self.materiaux)}.")
        if lignes:
            z.tableau(pd.DataFrame(lignes), {"α (10⁻⁶/K)": "%.2f"})
        else:
            z.info("Aucun matériau ne correspond : essayez moins de mots ou retirez une catégorie.")

    def _calculatrice(self, z: Zone) -> None:
        relance = lambda: self.calculatrice.rafraichir()  # noqa: E731
        noms = self.noms
        c1, c2, c3 = z.colonnes([2, 1, 1])
        nom = c1.liste("Matériau", noms, "materiaux.nom", defaut="Acier C45" if "Acier C45" in noms else noms[0],
                       apres=relance)  # fmt: skip
        tref = c2.nombre("Tref (°C)", "materiaux.tref", 20.0, decimales=2, apres=relance,
                         aide="Température à laquelle les cotes sont définies (20 °C en général).")  # fmt: skip
        temperature = c3.nombre("T de service (°C)", "materiaux.t", 100.0, decimales=2, mini=-273.15, apres=relance)
        m = self.materiaux[noms.index(nom)]
        r = alphaMateriau(nom, temperature, tref)
        z.metriques(
            [
                ("α moyen entre Tref et T", f"{fr(r['alpha'] * 1e6, '.3f')} × 10⁻⁶/K"),
                ("Allongement relatif ΔL/L", f"{fr(r['alpha'] * (temperature - tref) * 1e6, '.1f')} µm/m",
                 "Allongement d'une cote de 1 m entre Tref et T (négatif : contraction)."),
            ],
            2,
        )  # fmt: skip
        a100 = alphaMateriau(nom, 100.0, 20.0)["alpha"]
        if m["courbeNom"] and not m["recale"] and abs(a100 / m["alpha"] - 1) > 0.05:
            z.avertissement(
                f"Le calcul suit la courbe générique {m['courbeNom']} : α moyen 20-100 °C = "
                f"{fr(a100 * 1e6, '.2f')} × 10⁻⁶/K (tableau : {fr(m['alpha'] * 1e6, '.2f')})."
            )
        if r["horsDomaine"]:
            z.avertissement(f"Hors domaine à {fr(temperature, 'g')} °C : {r['motif']}.")
        elif math.isnan(m["tmin"]) and math.isnan(m["tmax"]):
            z.avertissement("Domaine d'emploi non renseigné pour ce matériau : vérifiez qu'il tient à cette température.")
        else:
            z.succes(f"{fr(temperature, 'g')} °C est dans le domaine d'emploi connu de ce matériau.")
        z.figure(*figureDilatation(m, tref))
