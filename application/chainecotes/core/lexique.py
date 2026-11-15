"""Bulles d'aide des termes du calcul (Cp, Cpk, ppm, IT, ES, EI…) : les mêmes textes que le site.

La liste reprend LEXIQUE de docs/app.js ; tests/test_lexique.py vérifie qu'elles restent identiques.
Ce module n'importe ni streamlit ni plotly.
"""

import re

LEXIQUE = (
    (re.compile(r"^Pire des cas|pire cas\)", re.I),
     "Toutes les cotes à leur limite la plus défavorable en même temps : le jeu est garanti à 100 %, mais les tolérances demandées sont serrées."),
    (re.compile(r"Bender"),
     "Statistique prudente : la dispersion est multipliée par 1,5 pour couvrir des procédés mal centrés."),
    (re.compile(r"^RSS"),
     "Calcul statistique : les écarts des cotes se compensent en partie. Presque tous les assemblages ont leur jeu dans cet intervalle (moyenne ± k écarts-types σ)."),
    (re.compile(r"^Monte-Carlo"),
     "Des assemblages tirés au hasard par l'ordinateur, pour vérifier le calcul statistique."),
    (re.compile(r"Cpk"),
     "Capabilité réelle : marge entre le jeu moyen et la limite la plus proche, divisée par 3σ. Elle baisse si le jeu est décentré. On vise 1,33 ou plus."),
    (re.compile(r"^Cpi"),
     "Capabilité inertielle (Pillet) : inertie maxi divisée par l'inertie du jeu. Il faut 1 ou plus."),
    (re.compile(r"^Cp$"),
     "Capabilité potentielle : largeur de l'intervalle exigé (Jmax − Jmin) divisée par 6σ. Elle ne regarde pas le centrage."),
    (re.compile(r"^ppm"),
     "Parties par million : nombre d'assemblages hors limites sur un million fabriqués."),
    (re.compile(r"^IT inertiel"),
     "Intervalle de tolérance que le maillon pourrait avoir en tolérancement inertiel."),
    (re.compile(r"^IT "),
     "Intervalle de tolérance : ES − EI, la largeur permise autour de la cote."),
    (re.compile(r"^ES"),
     "Écart supérieur : cote maxi − cote nominale."),
    (re.compile(r"^EI"),
     "Écart inférieur : cote mini − cote nominale."),
    (re.compile(r"^C moy"),
     "Cote moyenne : le milieu de l'intervalle de tolérance."),
    (re.compile(r"^Jeu nominal"),
     "Jeu obtenu avec toutes les cotes à leur valeur nominale."),
    (re.compile(r"^Jeu moyen"),
     "Jeu obtenu avec toutes les cotes au milieu de leur tolérance."),
    (re.compile(r"^Jeu mini$|^Jeu maxi$"),
     "Limite du jeu au pire des cas : toutes les cotes au plus défavorable."),
    (re.compile(r"^Jeu mini|^Jeu maxi"),
     "Plus petit ou plus grand jeu possible, selon la méthode de la ligne."),
    (re.compile(r"^Verdict"),
     "Vert : le jeu reste dans ses limites. Orange : en statistique seulement. Rouge : il en sort."),
    (re.compile(r"^Écart-type|^σ \("),
     "Écart-type σ : la dispersion habituelle autour de la moyenne. Environ 99,7 % des valeurs sont à moins de 3σ de la moyenne."),
    (re.compile(r"^α"),
     "Coefficient de dilatation : allongement en µm, par mètre de longueur et par degré."),
    (re.compile(r"^Part pire cas"),
     "Poids du maillon dans la dispersion du jeu au pire des cas."),
    (re.compile(r"^Part statistique|Sobol"),
     "Part de la variance du jeu due à ce maillon : le plus gros est celui à resserrer en premier."),
    (re.compile(r"^Inertie maxi"),
     "Inertie à ne pas dépasser : (Jmax − Jmin) / 6."),
    (re.compile(r"^Inertie"),
     "Inertie (Pillet) : elle réunit la dispersion et le décentrage en un seul nombre, √(σ² + écart²)."),
    (re.compile(r"^Décalage thermique"),
     "Variation du jeu moyen entre la température de référence et la température de service."),
    (re.compile(r"^Quantile"),
     "Valeur du jeu sous laquelle se trouve ce pourcentage des assemblages simulés."),
    (re.compile(r"si resserré"),
     "Valeur obtenue si l'on resserre ce seul maillon à la moitié de son IT."),
    (re.compile(r"^Sensibilité$"),
     "Quels maillons pèsent le plus sur le jeu, et ce que l'on gagne à en resserrer un."),
    (re.compile(r"^Statistiques$"),
     "Tirage Monte-Carlo et tolérancement inertiel."),
    (re.compile(r"^Graphiques$"),
     "Schéma, histogramme du jeu et Pareto des maillons."),
    (re.compile(r"^Explications du calcul$"),
     "Le calcul refait pas à pas, formule par formule."),
)


def aideTerme(texte: str) -> str:
    """Explication d'un terme du calcul d'après son libellé (le premier motif trouvé), « » si le terme est inconnu.

    Entrée : texte (en-tête de colonne, libellé de grandeur ou nom d'onglet). Sortie : texte d'aide.
    """
    t = str(texte).strip()
    return next((aide for motif, aide in LEXIQUE if motif.search(t)), "")
