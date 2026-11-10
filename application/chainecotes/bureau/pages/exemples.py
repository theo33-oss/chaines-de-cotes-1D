"""Page « Bibliothèque d'exemples » : une carte par exemple (maillons, cote condition, aperçu, schéma) à charger."""

import math

import pandas as pd

from chainecotes.bureau import state
from chainecotes.bureau.widgets import Page, Zone
from chainecotes.plots._common import fr, intervalle
from chainecotes.plots.schema import figureSchema
from chainecotes.services.calcul import apercuChaine
from chainecotes.services.exemples import chargerExemple, listeExemples


def tableauMaillons(probleme: dict, apercu: dict) -> pd.DataFrame:
    """Tableau de présentation des maillons d'un problème (écarts lus dans l'aperçu calculé s'il existe).

    Entrées : probleme (dict condition, reglages, maillons), apercu (sortie de apercuChaine).
    Sortie : DataFrame Maillon, Sens, Cote (mm), ISO, ES (mm), EI (mm), Loi, Matériau, T service (°C).
    """
    calcules = apercu["res"]["maillons"] if "res" in apercu else probleme["maillons"]
    return pd.DataFrame(
        [
            {
                "Maillon": m["nom"],
                "Sens": "−" if m["sens"] == "-" else "+",
                "Cote (mm)": m["cote"],
                "ISO": m["iso"] or "",
                "ES (mm)": m["es"],
                "EI (mm)": m["ei"],
                "Loi": m["loi"],
                "Matériau": m["materiau"] or "",
                "T service (°C)": m["tservice"],
            }
            for m in calcules
        ]
    )


def texteCondition(condition: dict) -> str:
    """Cote condition écrite en clair : nom et intervalle [Jmin ; Jmax] en mm (côté sans limite ouvert).

    Entrée : condition (dict nom, jmin, jmax en mm ou None). Sortie : texte.
    """
    jmin = -math.inf if condition.get("jmin") is None else condition["jmin"]
    jmax = math.inf if condition.get("jmax") is None else condition["jmax"]
    return f"{condition['nom']} attendu dans {intervalle(jmin, jmax)} mm"


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
