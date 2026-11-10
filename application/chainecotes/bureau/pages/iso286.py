"""Page « Tables ISO 286 » : calculatrice d'écarts, tableau des IT, écarts fondamentaux et règles de lecture.

Toutes les valeurs viennent de data/iso286.json (par chainecotes.core.iso286 et chargerJson), aucune n'est recopiée.
"""

import pandas as pd

from chainecotes.bureau.widgets import Page, Zone
from chainecotes.core.donnees import chargerJson
from chainecotes.core.errors import ErreurChaine
from chainecotes.core.iso286 import (
    COTES_USUELLES,
    LETTRES_ALESAGE,
    LETTRES_ARBRE,
    QUALITES,
    USAGE_QUALITE,
    libellesPlages,
    lireDesignation,
)
from chainecotes.plots._common import fr

AUTRE_COTE = "Autre valeur…"


def afficherEcarts(z: Zone, r: dict, titre: str) -> None:
    """Affiche les écarts d'une désignation lue (écart supérieur, inférieur, IT, plage).

    Entrées : z (zone), r (sortie de lireDesignation), titre (texte au-dessus des valeurs). Sortie : aucune.
    """
    sup, inf = ("ES", "EI") if r["type"] == "alésage" else ("es", "ei")
    z.texte(f"**{titre}**")
    z.metriques(
        [
            (f"{sup} (mm)", fr(r["es"], "g"), "Écart supérieur : cote maxi = cote + écart."),
            (f"{inf} (mm)", fr(r["ei"], "g"), "Écart inférieur : cote mini = cote + écart."),
            ("IT (µm)", fr(r["IT"], "g"), "Intervalle de tolérance de la qualité."),
        ],
        3,
    )
    z.legende(
        f"{r['designation']} ({r['type']}) : cote de {fr(r['cote'] + r['ei'], 'g')} à {fr(r['cote'] + r['es'], 'g')} "
        f"mm ; plage de la table : {r['plage']}."
    )


class PageIso286(Page):
    def rendre(self, z: Zone) -> None:
        self.table = chargerJson("iso286.json")
        table = self.table
        self.plages = libellesPlages(table["bornes"])
        z.titre("Tables ISO 286")
        z.texte(
            "Écarts et intervalles de tolérance de l'ISO 286 (qualités IT1 à IT18, positions a à zc pour les arbres et "
            f"A à ZC pour les alésages, cotes jusqu'à {fr(table['bornes'][-1], 'g')} mm). Les écarts sont donnés en mm dans la "
            "calculatrice et en µm dans les tables."
        )
        z.sousTitre("Calculatrice")
        self.calculatrice = z.section(self._calculatrice)
        z.sousTitre("Intervalles de tolérance IT (µm)")
        z.legende("Une ligne par plage de cote nominale (mm), une colonne par qualité ; case vide : qualité non définie.")
        z.tableau(pd.DataFrame({f"IT{q}": table["it"][str(q)] for q in QUALITES}, index=self.plages), index=True)
        z.sousTitre("Écarts fondamentaux (µm)")
        z.legende(
            "Écart le plus proche de la ligne zéro, tel que la table le donne : écart supérieur es (a à h) ou inférieur "
            "ei (j à zc) des arbres ; écart inférieur EI (A à H) ou supérieur ES avant correction Δ (J à ZC) des "
            "alésages."
        )
        self.fondamentaux = z.section(self._fondamentaux)
        z.sousTitre("Règles de lecture")
        z.texte(
            "- **Arbre** de a à h : la table donne es, puis ei = es − IT. De j à zc : la table donne ei, puis "
            "es = ei + IT.\n"
            "- **Alésage** de A à H : la table donne EI, puis ES = EI + IT. De J à ZC : la table donne ES, corrigé de Δ "
            "pour K, M, N en qualités 3 à 8 et pour P à ZC en qualités 3 à 7, puis EI = ES − IT.\n"
            "- **js et JS** : écarts symétriques ± IT/2. Pour les qualités 7 à 11, l'ISO 286-1 ramène un IT impair au "
            "pair inférieur avant de diviser par deux. L'application MATLAB de référence garde ± IT/2 exactement : la "
            "calcul de la chaîne suit MATLAB et affiche un avertissement quand les deux valeurs diffèrent."
        )
        z.repliable(
            "Correction Δ des alésages (µm)",
            rendu=lambda s: s.tableau(
                pd.DataFrame({f"Δ qualité {q}": v for q, v in table["delta"].items()}, index=self.plages), index=True
            ),
        )
        z.legende(table["Source"])

    def _calculatrice(self, z: Zone) -> None:
        relance = lambda: self.calculatrice.rafraichir()  # noqa: E731
        mode = z.radio("Saisie", ["Cote, position et qualité", "Désignation"], "iso286.mode", apres=relance,
                       aide="Listes : choisissez chaque élément. Désignation : texte comme « 40 h7 » ou « 25 JS6 ».")  # fmt: skip
        if mode == "Désignation":
            texte = z.saisie(
                "Désignation ISO 286", "iso286.designation", "50 H7", apres=relance,
                aide="Cote en mm puis position et qualité : minuscule pour un arbre (h7), majuscule pour un alésage (H7).",
            )  # fmt: skip
        else:
            c1, c2, c3, c4 = z.colonnes(4)
            choixCote = c1.liste(
                "Cote nominale (mm)", COTES_USUELLES + [AUTRE_COTE], "iso286.cote.liste",
                format=lambda c: c if c == AUTRE_COTE else fr(c, "g"), defaut=50, apres=relance,
                aide="Cotes usuelles de 1 à 3 150 mm. « Autre valeur… » permet de taper n'importe quelle cote.",
            )  # fmt: skip
            if choixCote == AUTRE_COTE:
                cote = c1.nombre("Cote (mm)", "iso286.cote", 50.0, mini=0.001, maxi=self.table["bornes"][-1], apres=relance)
            else:
                cote = choixCote
            genre = c2.liste("Pièce", ["Alésage", "Arbre"], "iso286.genre", apres=relance)
            lettres = LETTRES_ALESAGE if genre == "Alésage" else LETTRES_ARBRE
            lettre = c3.liste("Position", lettres, f"iso286.lettre.{genre}", defaut="H" if genre == "Alésage" else "h",
                              apres=relance)  # fmt: skip
            qualite = c4.liste(
                "Qualité IT", QUALITES, "iso286.qualite", defaut=7, apres=relance,
                format=lambda q: f"IT{q}" + (f" · {USAGE_QUALITE[q]}" if q in USAGE_QUALITE else ""),
            )  # fmt: skip
            texte = f"{cote:g} {lettre}{qualite}"
        try:
            matlab = lireDesignation(texte, arrondiJs=False)
            norme = lireDesignation(texte, arrondiJs=True)
        except ErreurChaine as e:
            z.erreur(e.message)
            return
        if (matlab["es"], matlab["ei"]) == (norme["es"], norme["ei"]):
            afficherEcarts(z, matlab, f"{matlab['designation']} : valeur normalisée, identique à l'application MATLAB")
        else:
            z.avertissement(matlab["avertissement"])
            gauche, droite = z.colonnes(2)
            afficherEcarts(gauche, matlab, "Valeur de l'application MATLAB (utilisée par le calcul de la chaîne)")
            afficherEcarts(droite, norme, "Valeur normalisée ISO 286-1")

    def _fondamentaux(self, z: Zone) -> None:
        relance = lambda: self.fondamentaux.rafraichir()  # noqa: E731
        cA, cB = z.colonnes(2)
        piece = cA.radio("Pièce", ["Arbre", "Alésage"], "iso286.fond.piece", apres=relance)
        colonnes = self.table["arbre"] if piece == "Arbre" else self.table["alesage"]
        choix = cB.liste(
            "Position (colonne de la table)", list(colonnes), f"iso286.fond.{piece}",
            defaut="h" if piece == "Arbre" else "H", apres=relance,
            aide="j5-6, j7, j8, J6, J7, J8 : par qualité ; k4-7 : qualités 4 à 7 ; K<=8, M<=8, N<=8 : qualités jusqu'à 8.",
        )  # fmt: skip
        z.tableau(pd.DataFrame({f"{choix} (µm)": colonnes[choix]}, index=self.plages), index=True)
