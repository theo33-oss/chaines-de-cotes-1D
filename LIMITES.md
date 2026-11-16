# Limites connues

Chaînes de cotes 1D est un outil pédagogique et d'aide à la cotation, fourni sans garantie. Les résultats ne
remplacent ni une note de calcul certifiée ni les normes en vigueur et doivent être vérifiés avant tout usage réel.
Cette page dit ce que l'outil ne traite pas, et ce qui a été vérifié.

## Ce que l'outil ne traite pas

- **Une dimension seulement** : une chaîne suit un axe. Un facteur (levier) et un angle donnent un coefficient libre,
  mais il n'y a ni chaîne 2D ou 3D, ni basculement.
- **Lois normale, uniforme ou triangulaire, indépendantes** : aucune corrélation entre maillons n'est prise en compte.
- **Thermique linéaire par courbes** : dilatation libre lue sur les courbes ε(T) des matériaux ; ni gradient, ni
  contrainte thermique, ni déformation mécanique.
- **Géométrie simplifiée** : une tolérance géométrique ISO 1101 est une zone ajoutée comme maillon dans le sens de la
  chaîne (± t/2, bonus au maximum de matière) ; pas d'analyse 3D des zones.

## Ce qui est vérifié

- Plus de 4 400 tests automatiques. Les exemples, les tables ISO 286 et les matériaux sont comparés aux valeurs de
  l'application MATLAB d'origine (`application/tests/golden/`).
- Le dossier de validation refait chaque grandeur à la main puis la compare au solveur (32 contrôles sur l'exemple du
  réducteur). Il prouve que le calcul est cohérent avec ses formules, pas que ces formules conviennent à votre cas.

## Sources des données

- Tolérances ISO 286 (IT1 à IT18, positions a à zc et A à ZC) : table reprise de MecaStruct RdM Pro.
- Coefficients de dilatation des 93 matériaux : sources citées dans la page Matériaux (NIST, Eurocodes, fiches de
  fabricants).

## Entre le site et le bureau

Un fichier d'étude enregistré dans l'une des versions s'ouvre dans l'autre. Les champs que le site ne modifie pas
(dérive, mesures d'atelier, levier, angle, géométrie) sont conservés et réenregistrés tels quels.
