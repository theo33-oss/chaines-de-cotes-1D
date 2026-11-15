"""Classeur Excel complet : la feuille de chaîne à formules et, à côté, toutes les valeurs calculées par l'application.

Les formules refont le calcul dans Excel et le comparent au résultat de l'application ; les feuilles de valeurs
(Synthèse, Maillons, Contributions, Monte-Carlo) gardent ce que l'application a calculé, pour valider les calculs.
Ce module n'importe ni streamlit ni plotly.
"""

import io

from openpyxl import load_workbook

from chainecotes.services.feuille_chaine import exporterFeuilleChaine
from chainecotes.services.projet_io import exporterResultatsXlsx


def exporterClasseurComplet(probleme: dict, bundle: dict) -> bytes:
    """Classeur Excel de l'étude : feuille « Chaîne » (formules), puis les feuilles de valeurs du calcul.

    Entrées : probleme (dict condition, reglages, maillons ; le cartouche est repris), bundle (sortie de calculerChaine).
    Sortie : contenu du fichier .xlsx (bytes). Erreur : ErreurChaine si le problème est invalide.
    """
    classeur = load_workbook(io.BytesIO(exporterFeuilleChaine(probleme, bundle)))
    valeurs = load_workbook(io.BytesIO(exporterResultatsXlsx(bundle)))
    for rang, feuille in enumerate(valeurs.worksheets, start=1):  # juste après « Chaîne », avant le mode d'emploi
        copie = classeur.create_sheet(feuille.title, rang)
        for ligne in feuille.iter_rows():
            for c in ligne:
                if c.value is not None:
                    copie.cell(c.row, c.column, c.value).number_format = c.number_format
        for lettre, dim in feuille.column_dimensions.items():
            copie.column_dimensions[lettre].width = dim.width
    tampon = io.BytesIO()
    classeur.save(tampon)
    return tampon.getvalue()
