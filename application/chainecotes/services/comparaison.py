"""Comparaison de scénarios (deux calculs) et synthèse d'un lot de fichiers de problèmes déposés ensemble."""

from chainecotes.core.errors import ErreurChaine
from chainecotes.core.montecarlo import GRAINE_DEFAUT, N_DEFAUT
from chainecotes.services.scenarios import comparerScenarios  # noqa: F401 : nom historique de ce module
from chainecotes.services.mecanisme import (
    TIRAGES_PAR_CHAINE_MINI,
    TIRAGES_TOTAUX_MAX,
    calculerMecanisme,
    importerMecanisme,
)

MAX_FICHIERS = 20  # fichiers comparés en une fois : borne la mémoire et le temps de calcul d'un clic


def comparerFichiers(textes_json, n: int = N_DEFAUT, graine: int = GRAINE_DEFAUT) -> dict:
    """Tableau de synthèse de plusieurs fichiers déposés en lot ; un fichier invalide ne bloque pas les autres.

    Entrées : textes_json (dict {nom de fichier: texte JSON}, ou liste de textes nommés « Fichier 1 »…),
    n (tirages Monte-Carlo), graine (entier). Un fichier peut être un problème ou un mécanisme (une ligne par chaîne).
    Sortie : dict lignes (une par chaîne, clés de calculerMecanisme avec en plus « fichier ») et erreurs (liste de
    {fichier, message} pour les fichiers illisibles). Une chaîne dont le calcul échoue garde une ligne avec erreur.
    """
    if isinstance(textes_json, dict):
        elements = list(textes_json.items())
    else:
        elements = [(f"Fichier {i}", t) for i, t in enumerate(textes_json, start=1)]
    ignores = elements[MAX_FICHIERS:]
    elements = elements[:MAX_FICHIERS]
    n = min(n, max(TIRAGES_PAR_CHAINE_MINI, TIRAGES_TOTAUX_MAX // max(1, len(elements))))  # tirages partagés
    lignes = []
    erreurs = [
        {"fichier": f, "message": f"ignoré : au plus {MAX_FICHIERS} fichiers sont comparés à la fois."}
        for f, _ in ignores
    ]
    for fichier, texte in elements:
        try:
            r = calculerMecanisme(importerMecanisme(texte), n, graine)
        except ErreurChaine as e:
            erreurs.append({"fichier": fichier, "message": e.message})
            continue
        lignes.extend({**ligne, "fichier": fichier} for ligne in r["lignes"])
    return {"lignes": lignes, "erreurs": erreurs}
