"""Page d'Accueil : ce que fait l'application, méthodes de calcul, limites d'usage, guide en 5 étapes et liens."""

from PySide6.QtWidgets import QApplication

from chainecotes.bureau import widgets
from chainecotes.bureau.widgets import Page, Zone
from chainecotes.core.materiaux import nomsMateriaux


class PageAccueil(Page):
    def rendre(self, z: Zone) -> None:
        z.titre("Bienvenue dans Chaînes de cotes 1D")
        z.texte("Vérifiez qu'un **jeu entre deux pièces reste dans ses limites**, au pire des cas comme en statistique.")
        c1, c2, c3 = z.colonnes(3)
        c1.bouton("Partir d'un exemple", lambda: self.aller("exemples"), primaire=True,
                  aide="Une étude toute prête, calculable tout de suite.")  # fmt: skip
        c2.bouton("Créer une étude guidée", lambda: self.aller("parcours"), primaire=True,
                  aide="Cinq étapes, du jeu à garantir jusqu'au dossier.")  # fmt: skip
        c3.bouton("Ouvrir une étude", self.fenetre.ouvrir, aide="Un fichier .json enregistré par l'application.")

        def theme() -> None:
            widgets.appliquerTheme(QApplication.instance())

        c1, c2 = z.colonnes(2)
        c1.case("Thème sombre", "sombre", apres=theme)
        c2.case("Contraste élevé des graphiques", "contraste",
                aide="Graphiques plus lisibles : traits plus épais, aires plus colorées, textes plus marqués.")  # fmt: skip

        plus = z.repliable("En savoir plus : méthodes, outils, limites")
        plus.texte(
            "Cette application calcule des **chaînes de cotes à une dimension**. Une chaîne de cotes relie une **cote "
            "condition** (un jeu, un serrage, un dépassement : la grandeur qui doit rester entre un minimum Jmin et un "
            "maximum Jmax pour que le mécanisme fonctionne) aux **maillons** qui la fabriquent : les cotes des pièces, "
            "chacune avec sa valeur nominale, son sens (« + » si elle agrandit la cote condition, « − » si elle la "
            "réduit) et sa **tolérance** (écarts ES / EI en mm ou désignation ISO 286 comme « 40 h7 »)."
        )
        plus.texte(
            "L'application donne le jeu obtenu par trois méthodes, qui répondent à trois questions différentes :\n\n"
            "- **Pire des cas** : toutes les cotes au plus mauvais en même temps. Le jeu est garanti à 100 %, mais les "
            "tolérances demandées sont serrées, donc chères.\n"
            "- **Statistique (RSS ± kσ)** : les cotes se répartissent au hasard autour de leur milieu ; leurs écarts se "
            "compensent. On accepte un petit taux de pièces hors tolérance (Cp, Cpk, ppm) contre des tolérances plus "
            "larges. Chaque intervalle de tolérance vaut 2kσ (k = 3 par défaut).\n"
            "- **Monte-Carlo** : 200 000 assemblages tirés au hasard vérifient le calcul statistique et donnent le taux "
            "de rebut simulé, même quand les lois sont uniformes.\n\n"
            "L'**effet thermique** est pris en compte : chaque maillon peut recevoir un matériau (ou un coefficient α) "
            "et une température de service ; l'application calcule le jeu dilaté et son évolution avec la température."
        )
        plus.sousTitre("Tous les outils")
        for page, libelle in (
            ("parcours", "Démarrer une étude pas à pas (parcours guidé)"),
            ("calcul", "Analyser une chaîne de cotes (pire cas, statistique, Monte-Carlo)"),
            ("inverse", "Répartir les tolérances pour tenir un jeu (parts égales, ISO ou coût minimal)"),
            ("optimisation", "Comparer deux scénarios ou un lot de fichiers"),
            ("mecanisme", "Calculer plusieurs chaînes d'un même mécanisme"),
            ("ajustement", "Choisir un ajustement ISO 286 selon sa fonction"),
            ("exemples", "Partir d'un exemple tout prêt"),
            ("iso286", "Lire une tolérance ISO 286 (H7, h6, js7…)"),
            ("materiaux", "Consulter les matériaux et leur dilatation"),
        ):
            plus.lien(page, libelle)

        plus.repliable("Comment faire : une chaîne de cotes en 5 étapes").texte(
            "Pas sûr de la chaîne ? L'**Assistant de chaîne** la construit depuis vos pièces et leurs contacts.\n\n"
            "1. **Cote condition** : donnez-lui un nom et ses limites Jmin et Jmax en mm (laissez vide le côté sans "
            "limite).\n"
            "2. **Maillons** : ajoutez une ligne par cote de la chaîne, avec son sens « + » ou « − », sa cote nominale "
            "et sa tolérance (ES / EI ou désignation ISO), puis si besoin la loi, le matériau et la température.\n"
            "3. **Schéma** : vérifiez sur le schéma que les flèches se suivent bien et que la chaîne se referme. La "
            "flèche de la cote condition est verte si le pire cas tient les limites, rouge sinon.\n"
            "4. **Calculer** : cliquez sur « Calculer » (F5) et lisez le verdict en haut de page (vert : conforme au "
            "pire des cas ; orange : en statistique seulement ; rouge : non conforme), puis le Pareto pour savoir "
            "quelles cotes pèsent le plus.\n"
            "5. **Dossier de validation** : enregistrez le dossier ; il refait chaque calcul à la main et le compare "
            "au solveur, à joindre à votre note de calcul."
        )

        plus.sousTitre("Fonctions de l'application")
        plus.texte(
            "- Calcul de la cote condition au pire des cas, en statistique (RSS ± kσ et ± 6σ) et par Monte-Carlo.\n"
            "- Capabilités Cp et Cpk, taux hors tolérance en ppm, risque selon le Cp.\n"
            "- Contributions de chaque maillon (Pareto) et curseurs de sensibilité en direct.\n"
            "- Tolérances ISO 286 complètes (IT1 à IT18, positions a à zc et A à ZC).\n"
            f"- Effet thermique : {len(nomsMateriaux()) - 1} matériaux avec courbes de dilatation, mode uniforme ou "
            "température par cote.\n"
            "- Étude en cours, trois modes : **Analyser** (calcul et résultats), **Répartir les tolérances** (égale, "
            "proportionnelle, qualité ISO ou coût minimal selon les procédés de fabrication) et **Comparer** (deux "
            "scénarios, ou un lot de fichiers).\n"
            "- Nouvelle étude : parcours guidé en cinq étapes, du jeu à garantir au dossier, avec un verdict en langage "
            "courant ; révisions datées de l'étude et comparaison de deux états.\n"
            "- Assistant de chaîne : des pièces, leurs surfaces et leurs contacts à la chaîne minimale (une cote par "
            "pièce), avec plan et envoi vers le calcul.\n"
            "- Mécanisme : plusieurs chaînes d'un même assemblage calculées et comparées ensemble.\n"
            "- Assistant d'ajustement : classement des ajustements ISO 286 selon la fonction (glissant, serré, etc.), "
            "jeux calculés d'après la table ISO.\n"
            "- Options de calcul : loi triangulaire, décentrage du procédé, dérive d'un maillon, indices de "
            "sensibilité, mesures de l'atelier (σ et moyenne), statistique majorée de Bender, tolérancement inertiel "
            "(Pillet).\n"
            "- Tolérances géométriques ISO 1101 (planéité, parallélisme, position, coaxialité, maximum de matière).\n"
            "- Contrôles de cohérence du problème, tableau de cotation (Excel, CSV) et dossier de calcul PDF.\n"
            "- Explications du calcul pas à pas, dossier de validation HTML, exports JSON, Excel et CSV."
        )
        plus.repliable("Limites d'usage").texte(
            "- **Une dimension seulement** : une chaîne suit un axe ; un facteur (levier) et un angle donnent un "
            "coefficient libre, mais il n'y a ni chaîne 2D ou 3D, ni basculement.\n"
            "- **Lois normale, uniforme ou triangulaire, indépendantes** : aucune corrélation entre maillons n'est "
            "prise en compte.\n"
            "- **Thermique linéaire par courbes** : dilatation libre lue sur les courbes ε(T) des matériaux ; ni "
            "gradient, ni contrainte thermique, ni déformation mécanique.\n"
            "- **Géométrie simplifiée** : une tolérance géométrique ISO 1101 est une zone ajoutée comme maillon dans "
            "le sens de la chaîne (± t/2, bonus au maximum de matière) ; pas d'analyse 3D des zones.\n"
            "- **Résultats à vérifier** avant tout usage réel, avec le dossier de validation."
        )
        z.legende(
            "Outil pédagogique et d'aide à la cotation. Les résultats ne remplacent ni une note de calcul certifiée ni "
            "les normes en vigueur et doivent être vérifiés avant tout usage réel."
        )

