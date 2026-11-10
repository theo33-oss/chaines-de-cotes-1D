"""Page « À propos » : auteur, sources et confidentialité de l'application de bureau."""

from chainecotes.bureau.widgets import Page, Zone


class PageAPropos(Page):
    def rendre(self, z: Zone) -> None:
        z.titre("À propos")
        z.texte(
            "Application de **Théo Brun**, portage de son application MATLAB de chaînes de cotes.\n\n"
            "- ISO 286-1 et ISO 286-2 : tolérances et écarts fondamentaux (table reprise de MecaStruct RdM Pro).\n"
            "- Classeur des coefficients de dilatation de l'application MATLAB : sources citées page « Matériaux et "
            "dilatation » (NIST, Eurocodes, fiches de fabricants).\n"
            "- Cotation fonctionnelle classique : méthodes du pire des cas et statistique (RSS)."
        )
        z.sousTitre("Confidentialité")
        z.texte(
            "Tout est calculé sur cet ordinateur : aucune cote n'est envoyée sur Internet. Vos études restent dans les "
            "fichiers que vous enregistrez."
        )
        z.sousTitre("Limites")
        z.texte(
            "Outil pédagogique et d'aide à la cotation, fourni sans garantie. Les résultats ne remplacent ni une note "
            "de calcul certifiée ni les normes en vigueur et doivent être vérifiés avant tout usage réel."
        )
