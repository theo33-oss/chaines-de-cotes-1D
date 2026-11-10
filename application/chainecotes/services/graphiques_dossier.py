"""Graphiques du calcul pour les dossiers de validation (HTML, PDF, Word).

Chaque graphique est construit par chainecotes.plots ; l'image PNG vient de kaleido (navigateur Chrome ou Chromium
sur la machine). Sans kaleido ou sans navigateur, `png` vaut None : le HTML garde le graphique interactif (Plotly)
et le PDF / Word le signalent. Ce module n'importe pas streamlit.
"""

import threading
import warnings

import plotly.io as pio

from chainecotes.core.derive import deriveSerie
from chainecotes.plots import graphiques
from chainecotes.plots.schema import figureSchema

LARGEUR_PX = 900
SEUIL_PPM_DERIVE = 1000.0  # seuil de ppm du graphique de dérive, comme la valeur par défaut de la page Calcul
PIECES_PAR_DEFAUT = 10_000  # horizon de la courbe de dérive quand aucun re-réglage n'est calculable
_VERROU = threading.Lock()  # le serveur kaleido est unique : un export à la fois


def _figures(bundle: dict) -> list[tuple[str, object, str]]:
    """Couples (titre, figure, légende) de tous les graphiques du calcul, dans l'ordre de la page Calcul."""
    p = bundle["probleme"]
    constructeurs = [
        ("Schéma de la chaîne", lambda: figureSchema(p)),
        ("Pareto des contributions", lambda: graphiques.figurePareto(bundle)),
        ("Histogramme Monte-Carlo", lambda: graphiques.figureMonteCarlo(bundle)),
        ("Comparaison des méthodes", lambda: graphiques.figureComparaison(bundle)),
        ("Distribution du jeu", lambda: graphiques.figureDistribution(bundle)),
        ("Risque selon le Cp", lambda: graphiques.figureRisqueCp(bundle)),
    ]
    if bundle["res"]["thermique_actif"]:
        constructeurs.append(("Effet thermique", lambda: graphiques.figureEffetThermique(bundle)))
    if bundle["jeuT"] is not None:
        constructeurs.append(("Jeu selon la température", lambda: graphiques.figureJeuTemperature(bundle)))
    constructeurs.append(("Sensibilité (indices de Sobol)", lambda: graphiques.figureSensibilite(bundle)))
    if any(m["derive"] != 0 for m in bundle["res"]["maillons"]):
        constructeurs.append(("Dérive et re-réglage", lambda: _figureDerive(bundle)))
    return [(titre, *construire()) for titre, construire in constructeurs]


def _figureDerive(bundle: dict) -> tuple[object, str]:
    """Figure de dérive avec l'horizon et le seuil par défaut de la page Calcul."""
    p = bundle["probleme"]
    inter = deriveSerie(p, 1000, 1000, seuilPpm=SEUIL_PPM_DERIVE)["intervalleRecalage"]
    horizon = max(int(1.5 * inter) if inter else PIECES_PAR_DEFAUT, 100)
    serie = deriveSerie(p, horizon, max(1, horizon // 200), seuilPpm=SEUIL_PPM_DERIVE)
    return graphiques.figureDerive(bundle, serie, SEUIL_PPM_DERIVE)


def _exporterPng(figures: list) -> list[bytes | None]:
    """Images PNG des figures (un seul démarrage du navigateur) ; None pour toutes si l'export est impossible."""
    try:
        import kaleido
    except ImportError:
        return [None] * len(figures)
    with _VERROU:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                kaleido.start_sync_server(silence_warnings=True)
                try:
                    return [pio.to_image(f, format="png", width=LARGEUR_PX, scale=2) for f in figures]
                finally:
                    kaleido.stop_sync_server()
        except Exception:  # noqa: BLE001 : kaleido lève des erreurs variées (navigateur absent, délai dépassé…)
            return [None] * len(figures)


def graphiquesDossier(bundle: dict, avecImages: bool = True) -> list[dict]:
    """Graphiques d'un calcul prêts à être mis dans un dossier de validation.

    Entrées : bundle (sortie de calculerChaine), avecImages (False : pas d'export PNG, plus rapide).
    Sortie : liste de dict titre, legende (textes), fig (figure Plotly) et png (bytes, ou None si l'export d'image
    est impossible : kaleido ou navigateur absent). Compter environ 3 s pour une dizaine d'images.
    Erreur : KeyError si bundle n'est pas une sortie de calculerChaine.
    """
    brut = _figures(bundle)
    images = _exporterPng([f for _, f, _ in brut]) if avecImages else [None] * len(brut)
    return [
        {"titre": titre, "legende": legende, "fig": fig, "png": png}
        for (titre, fig, legende), png in zip(brut, images, strict=True)
    ]
