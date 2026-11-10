# Chaînes de cotes 1D

Calcul de chaînes de cotes à une dimension : le jeu entre deux pièces reste-t-il dans ses limites ?
Pire des cas, statistique (RSS ± kσ), Monte-Carlo, capabilités Cp et Cpk, effet thermique, tolérances ISO 286.
Portage en Python de l'application MATLAB de Théo Brun.

Deux façons de l'utiliser :

| | Version navigateur | Application de bureau (Windows) |
|---|---|---|
| Où | Page GitHub Pages du dépôt (Chrome, Firefox, Edge, Safari) | Dossier `application/` |
| Contenu | Analyse : exemples, saisie, verdict, schéma, Pareto, Monte-Carlo | Tout : répartition des tolérances, comparaison, mécanisme, assistants, dossiers PDF / Word / HTML, enregistrement des études |
| Installation | Aucune. Premier chargement de 10 à 30 s, Internet nécessaire | Python 3.11 ou plus, installé au premier lancement (environ 1 Go) |

Dans les deux cas, tout est calculé sur votre ordinateur : aucune cote n'est envoyée sur Internet.

## Version navigateur

Le dossier `docs/` est la page publiée par GitHub Pages (Settings → Pages → Branch `main`, dossier `/docs`).
Elle exécute dans le navigateur, avec [Pyodide](https://pyodide.org), le même code Python de calcul que l'application
de bureau : mêmes résultats, mêmes exemples.

Essai en local :

```bash
python -m http.server 8000 --directory docs
```

puis ouvrir <http://localhost:8000>. Après toute modification de `application/chainecotes` ou de `application/data`,
reconstruire le calcul de la page :

```bash
python construire_web.py
```

## Application de bureau

Double-cliquer sur `1_Ouvrir_application.bat` (voir `LISEZ-MOI.txt`). Pour les tests :

```bash
cd application
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt pytest pytest-qt
.venv/Scripts/python -m pytest -q tests
```

## Limites d'usage

Outil pédagogique et d'aide à la cotation, fourni sans garantie. Une dimension seulement, lois normale, uniforme ou
triangulaire indépendantes, thermique linéaire. Les résultats ne remplacent ni une note de calcul certifiée ni les
normes en vigueur et doivent être vérifiés avant tout usage réel.

## Licence

[PolyForm Noncommercial 1.0.0](LICENSE) : usage non commercial autorisé ; usage commercial sur autorisation écrite
préalable de l'auteur. © 2026 Théo Brun.
