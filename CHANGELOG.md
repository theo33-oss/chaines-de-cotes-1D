# Journal des changements

Le numéro de version est celui de `application/chainecotes/__init__.py`. Le site suit toujours la dernière version ;
l'installateur Windows de chaque version est dans les [Releases](https://github.com/theo33-oss/chaines-de-cotes-1D/releases).

## Non publié

Comparer plusieurs chaînes et plusieurs cotes condition (site)
- Page Comparer : un comparatif de 12 chaînes au plus, côte à côte. Une colonne = une chaîne avec sa cote condition, venue de l'étude en cours (deux colonnes si elle a deux cotes condition), de « Mes études », d'un exemple ou d'un fichier ; « Nouvelle CF sur ces maillons » crée une autre cote condition sur les mêmes cotes (sens +, − ou exclu au choix).
- Tableau comparatif (limites, jeu au pire des cas, statistique, Cp, Cpk, ppm, maillon dominant…), meilleure valeur en évidence, écart à la colonne de référence, lignes identiques masquables ; trois graphiques (plages de jeu face aux limites, Cpk, distributions Monte-Carlo) ; copie vers Excel, CSV, enregistrement et réouverture de la comparaison (.json), impression. Une colonne en erreur n'empêche pas les autres.
- « Mes études » (accueil et page Étude) : copies nommées gardées dans le navigateur, favoris, renommer, dupliquer, supprimer, export et import JSON (`schema_version`).
- La comparaison de deux scénarios (A/B) reste dans un volet de la même page. Le calcul ne change pas.
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
