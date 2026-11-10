"""Figures Plotly du site (schéma vivant de la chaîne, graphiques des résultats), sans dépendance à Streamlit."""

from chainecotes.plots.graphiques import (
    figureComparaison,
    figureDistribution,
    figureEffetThermique,
    figureJeuTemperature,
    figureMonteCarlo,
    figurePareto,
    figureRisqueCp,
)
from chainecotes.plots.schema import figureSchema

__all__ = [
    "figureComparaison",
    "figureDistribution",
    "figureEffetThermique",
    "figureJeuTemperature",
    "figureMonteCarlo",
    "figurePareto",
    "figureRisqueCp",
    "figureSchema",
]
