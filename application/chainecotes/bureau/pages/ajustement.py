"""Page « Assistant d'ajustement » : classe les ajustements ISO 286 selon la fonction souhaitée (core/ajustement.py).

Les jeux et les écarts sont calculés par chainecotes.core (jamais saisis ici). Le bouton « Utiliser dans la chaîne
courante » ajoute l'alésage et l'arbre à la fin des maillons du problème courant, sans toucher aux autres maillons.
"""

import copy

import pandas as pd

from chainecotes.bureau import state
from chainecotes.bureau.widgets import Page, Zone
from chainecotes.core.ajustement import choisirAjustement, fonctionsDisponibles, maillonsAjustement, pieces
from chainecotes.core.donnees import chargerJson
from chainecotes.core.errors import ErreurChaine
from chainecotes.core.iso286 import COTES_USUELLES
from chainecotes.plots._common import fr
from chainecotes.plots.ajustement import figureZones

AUTRE_COTE = "Autre valeur…"
SYSTEMES = {"alesage": "Alésage normal (H)", "arbre": "Arbre normal (h)"}
CLE_MESSAGE = "ajust.message"


def ajouterALaChaine(designation: str, cote: float) -> None:
    """Ajoute l'alésage (sens +) puis l'arbre (sens −) comme maillons du problème courant.

    Entrées : designation (« H7/g6 »), cote (mm). Sortie : aucune ; les maillons existants ne sont pas modifiés, le
    résultat du dernier calcul est oublié. Erreur : ErreurChaine si la désignation est illisible.
    """
    nouveau = copy.deepcopy(state.probleme())
    tref = (nouveau.get("reglages") or {}).get("tref")
    nouveau["maillons"] += maillonsAjustement(
        designation, cote, {m["nom"] for m in nouveau["maillons"]}, 20.0 if tref is None else float(tref)
    )
    state.definirProbleme(nouveau)
    state.effacerResultat()


def tableauCandidats(candidats: list[dict]) -> pd.DataFrame:
    """Tableau classé des ajustements candidats.

    Entrée : candidats (sortie de choisirAjustement). Sortie : DataFrame Rang, Ajustement, Jeu mini (mm),
    Jeu maxi (mm), Nature, IT alésage (µm), IT arbre (µm), Usage.
    """
    return pd.DataFrame(
        {
            "Rang": [c["rang"] for c in candidats],
            "Ajustement": [c["designation"] for c in candidats],
            "Jeu mini (mm)": [fr(c["jeuMini"], ".4f") for c in candidats],
            "Jeu maxi (mm)": [fr(c["jeuMaxi"], ".4f") for c in candidats],
            "Nature": [c["nature"] for c in candidats],
            "IT alésage (µm)": [fr(c["ITAlesage"], "g") for c in candidats],
            "IT arbre (µm)": [fr(c["ITArbre"], "g") for c in candidats],
            "Usage": [c["usage"] for c in candidats],
        }
    )


class PageAjustement(Page):
    def construire(self) -> None:
        self.gauche, self.droite = self.deuxPanneaux(self._tete, self._saisie, self._visuel)

    def tout(self) -> None:
        self.gauche.rafraichir()
        self.droite.rafraichir()

    def _tete(self, z: Zone) -> None:
        z.titre("Assistant d'ajustement")
        z.texte(
            "Choisissez la cote, la fonction attendue et le système (alésage normal ou arbre normal) : les ajustements "
            "ISO 286 recommandés sont classés du mieux adapté au moins adapté, avec leurs jeux calculés à cette cote. "
            "« Utiliser dans la chaîne courante » ajoute l'alésage et l'arbre à l'étude en cours."
        )

    def _utiliser(self, designation: str, cote: float) -> None:
        try:
            ajouterALaChaine(designation, cote)
        except ErreurChaine as e:
            state.v[CLE_MESSAGE] = ("erreur", e.message)
        else:
            state.v[CLE_MESSAGE] = (
                "succes",
                f"{designation} ajouté à la chaîne courante (alésage en sens +, arbre en sens −). Ouvrez la page "
                "Calcul : la chaîne doit se fermer, ajustez les autres maillons si besoin.",
            )
        self.gauche.rafraichir()

    def _saisie(self, z: Zone) -> None:
        bornes = chargerJson("iso286.json")["bornes"]
        fonctions = fonctionsDisponibles()
        choixCote = z.liste(
            "Cote nominale (mm)", COTES_USUELLES + [AUTRE_COTE], "ajust.cote.liste",
            format=lambda c: c if c == AUTRE_COTE else fr(c, "g"), defaut=50, apres=self.tout,
            aide="Cotes usuelles de 1 à 3 150 mm. « Autre valeur… » permet de taper n'importe quelle cote.",
        )  # fmt: skip
        if choixCote == AUTRE_COTE:
            cote = z.nombre("Cote (mm)", "ajust.cote", 50.0, mini=0.001, maxi=bornes[-1], apres=self.tout)
        else:
            cote = choixCote
        fonction = z.liste("Fonction souhaitée", list(fonctions), "ajust.fonction", format=fonctions.get,
                           defaut=list(fonctions)[2], apres=self.tout)  # fmt: skip
        systeme = z.radio(
            "Système", list(SYSTEMES), "ajust.systeme", format=SYSTEMES.get, apres=self.tout,
            aide="Alésage normal : alésage H, l'arbre fait varier l'ajustement. Arbre normal : arbre h, c'est "
            "l'alésage.",
        )  # fmt: skip
        erreurCote = None
        try:
            candidats = choisirAjustement(float(cote), fonction, systeme)
        except ErreurChaine as e:
            candidats, erreurCote = [], e.message
            z.erreur(e.message)
        self.choisi, self.cote = None, float(cote)
        if candidats:
            z.sousTitre("Ajustements candidats")
            z.tableau(tableauCandidats(candidats))
            noms = [c["designation"] for c in candidats]
            nomChoisi = z.liste("Ajustement à détailler", noms, f"ajust.choix.{cote:g}.{fonction}.{systeme}",
                                apres=self.tout,
                                aide="Le premier de la liste est le mieux adapté à la fonction.")  # fmt: skip
            self.choisi = candidats[noms.index(nomChoisi)]
        elif erreurCote is None:
            z.info("Aucun ajustement recommandé pour cette fonction à cette cote : essayez l'autre système.")
        choisi = self.choisi
        if choisi:
            z.sousTitre(f"Détail de {choisi['designation']}")
            trou, arbre = pieces(choisi["designation"], self.cote)
            for piece, titre in ((trou, "Alésage"), (arbre, "Arbre")):
                sup, inf = ("ES", "EI") if piece["type"] == "alésage" else ("es", "ei")
                z.metriques(
                    [(f"{titre} {sup} (mm)", fr(piece["es"], "g")), (f"{titre} {inf} (mm)", fr(piece["ei"], "g")),
                     (f"{titre} IT (µm)", fr(piece["IT"], "g"))],
                    3,
                )  # fmt: skip
            z.texte(choisi["description"])
            z.legende(f"Usage : {choisi['usage']} Risque : {choisi['risque']}")
            if choisi["avertissement"]:
                z.avertissement(choisi["avertissement"])
            z.bouton("Utiliser dans la chaîne courante", lambda: self._utiliser(choisi["designation"], self.cote),
                     primaire=True)  # fmt: skip
        z.messageGarde(CLE_MESSAGE)

    def _visuel(self, z: Zone) -> None:
        choisi = self.choisi
        if choisi:
            z.figure(*figureZones(choisi["designation"], self.cote))
            z.metriques(
                [("Jeu mini", f"{fr(choisi['jeuMini'], '.4f')} mm"), ("Jeu maxi", f"{fr(choisi['jeuMaxi'], '.4f')} mm")],
                2,
            )
            z.legende(f"Nature à cette cote : {choisi['nature']}.")
        else:
            z.legende("Choisissez une cote et une fonction pour voir le schéma de l'ajustement.")
