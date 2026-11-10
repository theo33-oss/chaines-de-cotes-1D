"""Page « Bibliothèque d'exemples » : une carte par exemple (maillons, cote condition, aperçu, schéma) à charger."""

import pandas as pd

from chainecotes.bureau import state
from chainecotes.bureau.widgets import Page, Zone
from chainecotes.plots._common import fr
from chainecotes.plots.schema import figureSchema
from chainecotes.services.calcul import apercuChaine
from chainecotes.services.exemples import chargerExemple, lignesMaillons, listeExemples, texteCondition


def tableauMaillons(probleme: dict, apercu: dict) -> pd.DataFrame:
    """Tableau de présentation des maillons d'un problème (voir services.exemples.lignesMaillons)."""
    return pd.DataFrame(lignesMaillons(probleme, apercu))


class PageExemples(Page):
    def rendre(self, z: Zone) -> None:
        z.titre("Bibliothèque d'exemples")
        z.texte(
            "Les six premiers exemples viennent de l'application MATLAB d'origine ou de son aide (leurs résultats sont "
            "vérifiés contre MATLAB). Les suivants sont des exemples pédagogiques, à plusieurs pièces. « Charger cet "
            "exemple » en fait l'étude en cours (il remplace la chaîne ouverte) ; vous pourrez ensuite le modifier "
            "librement. L'aperçu donne le jeu au pire des cas, sans Monte-Carlo."
        )
        for ex in listeExemples():
            self._carte(z.cadre(), ex)

    def _charger(self, identifiant: str) -> None:
        if not self.fenetre.confirmerAbandon():
            return
        state.definirProbleme(chargerExemple(identifiant))
        state.definirRevisions([])
        state.nouvelleEtude()
        state.effacerResultat()
        self.aller("calcul")

    def _carte(self, z: Zone, ex: dict) -> None:
        probleme = chargerExemple(ex["id"])
        apercu = apercuChaine(probleme)
        z.sousTitre(ex["titre"])
        z.texte(ex["description"])
        z.legende(f"Source : {ex['source']}")
        if ex.get("methodologie"):
            z.repliable(f"Méthodologie : {ex['titre']}").texte(
                "\n".join(f"{i}. {etape}" for i, etape in enumerate(ex["methodologie"], start=1))
            )
        z.texte(f"**Cote condition** : {texteCondition(probleme['condition'])}")
        z.tableau(tableauMaillons(probleme, apercu))
        if "erreur" in apercu:
            z.avertissement(f"Aperçu impossible : {apercu['erreur']}")
        else:
            pire = apercu["verdicts"]["pireCas"]
            z.metriques([("Jeu mini (pire cas)", f"{fr(pire['min'])} mm"), ("Jeu maxi (pire cas)", f"{fr(pire['max'])} mm")], 2)
            if pire["ok"]:
                z.succes("Conforme au pire des cas.")
            else:
                z.erreur("Non conforme au pire des cas : chargez l'exemple pour voir le calcul statistique.")
        # schéma bâti à l'ouverture : une vue Plotly par exemple alourdirait toute la page
        z.repliable(f"Schéma : {ex['titre']}", rendu=lambda s: s.figure(*figureSchema(probleme, apercu)))
        z.bouton("Charger cet exemple", lambda: self._charger(ex["id"]), primaire=True)
