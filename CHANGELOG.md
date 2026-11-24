# Journal des changements

Le numéro de version est celui de `application/chainecotes/__init__.py`. Le site suit toujours la dernière version ;
l'installateur Windows de chaque version est dans les [Releases](https://github.com/theo33-oss/chaines-de-cotes-1D/releases).

## Non publié

Site : mise en page de l'étude
- Séparateur à glisser entre le tableau des maillons et le schéma (flèches, double-clic ou « Moitié-moitié » pour 50 / 50), en temps réel ; le choix est gardé.
- « Deux cotes condition » : la deuxième cote condition part des mêmes maillons et des mêmes limites que la première (plus de chaîne vide ni de « il faut au moins deux maillons »).
- Bouton « Calculer » toujours visible dans la barre collante du haut.
- « Demander à une IA » se range sur le bord gauche en languette « IA » ; elle s'ouvre au survol et un clic la remet en place.

## 1.1.0 (24 novembre 2026)

Comparer plusieurs chaînes et plusieurs cotes condition (site)
- Page Comparer : un comparatif de 12 chaînes au plus, côte à côte. Une colonne = une chaîne avec sa cote condition, venue de l'étude en cours (deux colonnes si elle a deux cotes condition), de « Mes études », d'un exemple ou d'un fichier ; « Nouvelle CF sur ces maillons » crée une autre cote condition sur les mêmes cotes (sens +, − ou exclu au choix).
- Tableau comparatif (limites, jeu au pire des cas, statistique, Cp, Cpk, ppm, maillon dominant…), meilleure valeur en évidence, écart à la colonne de référence, lignes identiques masquables ; trois graphiques (plages de jeu face aux limites, Cpk, distributions Monte-Carlo) ; copie vers Excel, CSV, enregistrement et réouverture de la comparaison (.json), impression. Une colonne en erreur n'empêche pas les autres.
- « Mes études » (accueil et page Étude) : copies nommées gardées dans le navigateur, favoris, renommer, dupliquer, supprimer, export et import JSON (`schema_version`).
- La comparaison de deux scénarios (A/B) reste dans un volet de la même page. Le calcul ne change pas.
- Reporté de MecaStruct (site) : recherche globale (touche « / » ou Ctrl+K) ; bouton « Partager », manifeste et icônes iPhone ; bouton « Réessayer » si le calcul ne se charge pas ; résultat ancien grisé avec « Recalculer » quand l'étude change après un calcul ; chiffres clés sous le verdict et « Aller à la cause » ; valeurs au-delà de 10^18 refusées et erreurs de calcul écrites en français ; exports « Exporter (.csv) » des tableaux et « Image vectorielle (SVG) » des graphiques ; accessibilité (un seul verdict annoncé, graphiques nommés, focus sur le titre de la page, champs à 16 px au doigt).
- Chargement : le menu et l'accueil s'affichent sans attendre Plotly et Pyodide (chargés en parallèle, avec empreinte `integrity` vérifiée par la CI) ; secondes écoulées affichées.
- Pyodide 0.28.3 devient 314.0.8 (Python 3.14, numpy 2.4, scipy 1.18) : les 9 exemples donnent les mêmes résultats qu'avant à 10⁻⁹ près (aperçu, calcul, texte de l'étude), et le dossier, l'Excel, le comparatif et le mécanisme fonctionnent. Un navigateur récent est nécessaire.
- Finitions (revérification complète) : verdict « conforme en statistique seulement » distinct dans le comparatif, écarts relatifs énormes écrits en facteur, texte de l'étude pour l'IA complété (α, température de service, décalage thermique, levier, absence de limite, définitions de Cp, Cpk, ppm), messages d'erreur plus clairs (« reçu : rien (champ vide) », fichier JSON illisible, « du bloc »), pied de page sans séparateurs orphelins, « Mes études » qui signale un stockage abîmé, onglets de résultats reliés au panneau (ARIA), zones tactiles de 40 px, barre d'outils Plotly masquée au doigt, silhouettes du schéma en clair à l'impression ; bureau : exposants ·10ⁿ dans les tableaux, liens lisibles en thème clair, pas de flash blanc dans les figures, auto-vérification du texte de l'étude.
- Correctif : « Actualiser le site » et le service worker ne touchent plus aux caches des autres projets de la même adresse github.io (MecaStruct).

Confort d'utilisation et forme, reportés de MecaStruct RdM. Le calcul et ses résultats ne changent pas.

Site et bureau
- Nombres lisibles : 2,487·10⁷ au lieu de 2,487e+07.
- Retour visible des actions : le bouton passe au vert avec une coche (au rouge avec une croix si l'action échoue) pendant
  2 s, et un message s'affiche en bas de la fenêtre. Sur le site, rebond et secousse, sans animation si le système demande
  moins de mouvement.
- « Copier l'image » au-dessus des figures, des tableaux, du schéma et des résultats : l'image va dans le presse-papiers
  (sur le site, elle est téléchargée si le navigateur refuse la copie).
- « Demander à une IA » : copie une consigne et toute l'étude (données, résultats, conclusion, démarche) ; l'IA présente le
  problème, puis on lui pose ses questions. Liens Claude et ChatGPT ; rien n'est envoyé automatiquement.
- Export « Bloc-notes (.txt) » de l'étude.
- Noms accessibles pour lecteur d'écran sur les champs du bureau.

Site
- Schéma et contrôles à droite, à gauche, au-dessus ou en dessous du tableau des maillons (bouton ou glisser-déposer de la
  poignée) ; le choix est gardé.
- Chargement plus rapide : zip et pont téléchargés pendant le démarrage de Python, numpy, scipy et plotly chargés ensemble ;
  durées dans `App.mesures` (console).
- Téléphone : en-tête compact, menus qui défilent avec fondu, zones tactiles de 40 px. Impression en clair, sans barres ni
  boutons.
- Usage hors ligne (service worker), numéro de build dans le pied de page, bouton « Actualiser le site » et bandeau quand une
  version plus récente est en ligne.
- Lien « Aller au contenu » et onglets de résultats au clavier (flèches, Début, Fin).
- `construire_web.py` : zip conservé s'il est inchangé, empreintes identiques sous Windows et Linux ; la CI vérifie que
  `docs/` est à jour.

Bureau
- `main.py --captures dossier` : une image par page et par onglet pour contrôler la forme ;
  `CHAINECOTES_THEME=clair` ou `sombre` force le thème.

## 1.0.0 (16 novembre 2026)

- Première version numérotée : site, application de bureau et installateur Windows (plus besoin d'installer Python).
- Calcul d'une chaîne de cotes 1D au pire des cas, en statistique (RSS ± kσ) et par Monte-Carlo, avec effet thermique
  (93 matériaux), tolérances ISO 286, décentrage et sensibilité.
- Étude guidée en cinq étapes, optimisation des tolérances, comparaison de scénarios, mécanisme à plusieurs chaînes,
  assistant de chaîne, exemples, ajustements, tables ISO 286.
- Dossier de validation (HTML sur le site ; HTML, PDF et Word sur le bureau) et export Excel à formules.
- Site et bureau aux couleurs de MecaStruct RdM Pro ; fichier d'étude commun aux deux versions.
